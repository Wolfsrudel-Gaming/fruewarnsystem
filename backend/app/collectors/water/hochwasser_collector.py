import logging
from datetime import datetime
from typing import Optional

import httpx

from app.config import settings
from app.models.database import async_session
from app.models.schemas import FloodWarningLevel

logger = logging.getLogger(__name__)

HOCHWASSER_LAGEPEGEL_URL = "https://www.hochwasserzentralen.de/webservices/get_lagepegel.php"
HOCHWASSER_INFOS_URL = "https://www.hochwasserzentralen.de/webservices/get_infosbundesland.php"

RELEVANT_RIVERS = {"rhein", "sieg", "agger"}

REQUEST_TIMEOUT = 30


async def _fetch_lagepegel(client: httpx.AsyncClient) -> list[dict]:
    results = []
    try:
        resp = await client.post(HOCHWASSER_LAGEPEGEL_URL, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", data) if isinstance(data, dict) else data
        if not isinstance(features, list):
            features = [features]

        for feature in features:
            props = feature.get("properties", feature) if isinstance(feature, dict) else {}
            river = (props.get("gewaesser") or props.get("river") or props.get("gewässer") or "").strip()
            if not river or river.lower() not in RELEVANT_RIVERS:
                continue

            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", []) if isinstance(geom, dict) else []

            station_id = str(props.get("pgnr") or props.get("messstelle_nr") or props.get("id", ""))
            warning_level = _parse_warning_level(props.get("lage") or props.get("warnstufe") or props.get("level"))

            results.append({
                "station_id": station_id,
                "station_name": props.get("name") or props.get("messstelle") or station_id,
                "river": river,
                "warning_level": warning_level,
                "level_cm": _parse_float(props.get("wasserstand") or props.get("W") or props.get("value")),
                "trend": _parse_trend(props.get("tendenz") or props.get("trend")),
                "state": "NW",
                "timestamp": _parse_timestamp(props.get("zeitpunkt") or props.get("datum") or props.get("time")),
                "source": "hochwasserzentralen",
                "raw_data": feature,
            })
    except Exception as e:
        logger.error(f"Error fetching Lagepegel data: {e}")
    return results


async def _fetch_nrw_info(client: httpx.AsyncClient) -> list[dict]:
    results = []
    try:
        resp = await client.post(
            HOCHWASSER_INFOS_URL,
            data={"id": "NW"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        pegel_list = data.get("pegel", data.get("data", []))
        if isinstance(pegel_list, dict):
            pegel_list = pegel_list.get("features", [pegel_list])

        for pegel in pegel_list if isinstance(pegel_list, list) else []:
            props = pegel.get("properties", pegel) if isinstance(pegel, dict) else {}
            river = (props.get("gewaesser") or props.get("river") or "").strip()
            if not river or river.lower() not in RELEVANT_RIVERS:
                continue

            station_id = str(props.get("pgnr") or props.get("id", ""))
            warning_level = _parse_warning_level(props.get("lage") or props.get("warnstufe"))

            results.append({
                "station_id": f"nw_{station_id}",
                "station_name": props.get("name") or props.get("messstelle") or station_id,
                "river": river,
                "warning_level": warning_level,
                "level_cm": _parse_float(props.get("wasserstand") or props.get("W")),
                "trend": _parse_trend(props.get("tendenz") or props.get("trend")),
                "state": "NW",
                "timestamp": _parse_timestamp(props.get("zeitpunkt") or props.get("datum")),
                "source": "hochwasserzentralen_nw",
                "raw_data": pegel,
            })
    except Exception as e:
        logger.error(f"Error fetching NRW flood info: {e}")
    return results


def _parse_warning_level(value) -> int:
    if value is None:
        return 0
    try:
        level = int(value)
        return max(0, min(4, level))
    except (ValueError, TypeError):
        return 0


def _parse_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_trend(value) -> Optional[str]:
    if not value:
        return None
    mapping = {
        "steigend": "rising",
        "fallend": "falling",
        "gleichbleibend": "stable",
        "stagnierend": "stable",
    }
    val_lower = str(value).lower().strip()
    return mapping.get(val_lower, val_lower)


def _parse_timestamp(ts) -> datetime:
    if not ts:
        return datetime.utcnow()
    if isinstance(ts, (int, float)):
        return datetime.utcfromtimestamp(ts / 1000 if ts > 1e12 else ts)
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        pass
    for fmt in ("%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(ts), fmt)
        except ValueError:
            continue
    return datetime.utcnow()


async def collect_flood_warnings():
    logger.info("Collecting flood warnings...")
    all_results = []

    async with httpx.AsyncClient() as client:
        lagepegel = await _fetch_lagepegel(client)
        all_results.extend(lagepegel)

        nrw_info = await _fetch_nrw_info(client)
        all_results.extend(nrw_info)

    seen_ids = set()
    unique_results = []
    for r in all_results:
        sid = r["station_id"]
        if sid not in seen_ids:
            seen_ids.add(sid)
            unique_results.append(r)

    for r in unique_results:
        if r["warning_level"] >= 2:
            logger.warning(
                f"HOCHWASSER Warnstufe {r['warning_level']}: "
                f"{r['station_name']} ({r['river']}) - {r.get('level_cm')} cm"
            )

    async with async_session() as session:
        for data in unique_results:
            entry = FloodWarningLevel(**data)
            session.add(entry)
        await session.commit()

    logger.info(f"Collected {len(unique_results)} flood warning readings")
    return unique_results
