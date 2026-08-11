"""Schifffahrtsrelevante Rheinlagemeldungen über PEGELONLINE (GlW/HSW).

ELWIS-RSS/NtS ist tot; als belastbarer Ersatz dienen Wasserstände vs.
Gleichwert (GlW) und höchster Schifffahrtswasserstand (HSW) an den
Rheinpegeln Bonn/Köln.
"""
import logging
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy import select

from app.models.database import async_session
from app.models.schemas import RiverShippingWarning

logger = logging.getLogger(__name__)

# PEGELONLINE Stations-UUIDs
STATIONS = {
    "Bonn": "593647aa-9fea-43ec-a7d6-6476a76ae868",
    "Köln": "a6ee8177-107b-47dd-bcfd-30960ccc6e9c",
}

PEGELONLINE = "https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations"
REQUEST_TIMEOUT = 30


async def collect_shipping_warnings():
    logger.info("Collecting Rhine shipping warnings (PEGELONLINE)...")
    all_warnings = []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        for name, uuid in STATIONS.items():
            w = await _fetch_station(client, name, uuid)
            all_warnings.extend(w)

    new_count = 0
    async with async_session() as session:
        if all_warnings:
            existing = await session.execute(
                select(RiverShippingWarning.warning_id).where(
                    RiverShippingWarning.warning_id.in_([w["warning_id"] for w in all_warnings])
                )
            )
            existing_ids = {row[0] for row in existing}
        else:
            existing_ids = set()

        for data in all_warnings:
            if data["warning_id"] not in existing_ids:
                session.add(RiverShippingWarning(**data))
                new_count += 1
                if data["warning_type"] in ("closure", "high_water", "low_water"):
                    logger.warning("SHIPPING: %s (%s)", data["title"], data["river"])
        await session.commit()

    logger.info("Collected %s shipping warnings (%s new)", len(all_warnings), new_count)
    return all_warnings


async def _fetch_station(client: httpx.AsyncClient, name: str, uuid: str) -> list[dict]:
    results = []
    try:
        url = f"{PEGELONLINE}/{uuid}.json"
        resp = await client.get(
            url,
            params={
                "includeTimeseries": "true",
                "includeCurrentMeasurement": "true",
                "includeCharacteristicValues": "true",
            },
        )
        resp.raise_for_status()
        data = resp.json()

        w_ts = next((t for t in data.get("timeseries", []) if t.get("shortname") == "W"), None)
        if not w_ts:
            return results

        current = w_ts.get("currentMeasurement") or {}
        level = current.get("value")
        if level is None:
            return results

        chars = {c.get("shortname"): c.get("value") for c in w_ts.get("characteristicValues", [])}
        glw = chars.get("GlW")
        tuglw = chars.get("TuGLW")
        hsw = chars.get("HSW") or chars.get("MHW")
        timestamp = _parse_dt(current.get("timestamp")) or datetime.utcnow()
        day = timestamp.strftime("%Y-%m-%d")

        # Niedrigwasser: unter GlW → Einschränkung, deutlich darunter → kritisch
        if glw is not None and level < glw:
            severity = "low_water"
            title = f"Niedrigwasser Rhein Pegel {name}: {level:.0f} cm (unter GlW {glw:.0f} cm)"
            if tuglw is not None and level < tuglw * 0.6:
                title = f"Kritisches Niedrigwasser Rhein Pegel {name}: {level:.0f} cm"
            results.append(_warn(
                warning_id=f"pegelonline_{uuid}_low_{day}",
                section=name,
                warning_type=severity,
                title=title,
                description=(
                    f"Aktueller Wasserstand {level:.0f} cm. "
                    f"Gleichwert (GlW) {glw:.0f} cm"
                    + (f", TuGLW {tuglw:.0f} cm" if tuglw else "")
                    + ". Schifffahrt kann eingeschränkt sein."
                ),
                valid_from=timestamp,
                raw={"station": name, "uuid": uuid, "level": level, "chars": chars, "current": current},
            ))

        # Hochwasser: über HSW/MHW
        if hsw is not None and level >= hsw:
            results.append(_warn(
                warning_id=f"pegelonline_{uuid}_high_{day}",
                section=name,
                warning_type="high_water",
                title=f"Hochwasser Rhein Pegel {name}: {level:.0f} cm (über HSW/MHW {hsw:.0f} cm)",
                description=(
                    f"Aktueller Wasserstand {level:.0f} cm liegt über dem "
                    f"Schifffahrts-/Hochwasserrichtwert {hsw:.0f} cm."
                ),
                valid_from=timestamp,
                raw={"station": name, "uuid": uuid, "level": level, "chars": chars, "current": current},
            ))

    except Exception as e:
        logger.error("Error fetching PEGELONLINE shipping data for %s: %s", name, e)
    return results


def _warn(**kwargs) -> dict:
    return {
        "river": "Rhein",
        "is_active": True,
        "valid_to": None,
        "source": "pegelonline",
        "raw_data": kwargs.pop("raw", None),
        **kwargs,
    }


def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None
