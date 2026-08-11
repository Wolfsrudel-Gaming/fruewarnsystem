import logging
from datetime import datetime
from typing import Optional

import httpx

from app.config import settings
from app.models.database import async_session
from app.models.schemas import OfficialWarning

logger = logging.getLogger(__name__)

NINA_BASE = "https://nina.api.proxy.bund.dev/api31"
NINA_DASHBOARD = f"{NINA_BASE}/dashboard"

AGS_CODES = [
    "05382",  # Rhein-Sieg-Kreis
    "05314",  # Bonn
    "05315",  # Köln
]

KATWARN_URL = "https://warnung.bund.de/api31/katwarn/mapData.json"
MOWAS_URL = "https://warnung.bund.de/api31/mowas/mapData.json"
BIWAPP_URL = "https://warnung.bund.de/api31/biwapp/mapData.json"


async def collect_official_warnings():
    logger.info("Collecting official warnings (NINA/KATWARN/MoWaS)...")
    results = []

    async with httpx.AsyncClient() as client:
        nina_results = await _fetch_nina_warnings(client)
        results.extend(nina_results)

        for source_name, url in [("katwarn", KATWARN_URL), ("mowas", MOWAS_URL), ("biwapp", BIWAPP_URL)]:
            extra = await _fetch_bund_warnings(client, source_name, url)
            results.extend(extra)

    existing_ids = set()
    unique_results = []
    for r in results:
        if r["warning_id"] not in existing_ids:
            existing_ids.add(r["warning_id"])
            unique_results.append(r)

    async with async_session() as session:
        for data in unique_results:
            from sqlalchemy import select
            stmt = select(OfficialWarning).where(OfficialWarning.warning_id == data["warning_id"])
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                entry = OfficialWarning(**data)
                session.add(entry)
        await session.commit()

    logger.info(f"Collected {len(unique_results)} official warnings")
    return unique_results


async def _fetch_nina_warnings(client: httpx.AsyncClient) -> list:
    results = []
    try:
        for ags in AGS_CODES:
            url = f"{NINA_BASE}/warnings/{ags}.json"
            resp = await client.get(url, timeout=30, headers={"Accept": "application/json"})
            if resp.status_code != 200:
                continue

            warnings = resp.json()
            if not isinstance(warnings, list):
                warnings = [warnings]

            for w in warnings:
                info = w.get("info", [{}])
                if isinstance(info, list) and info:
                    info = info[0]

                area_desc = ""
                if "area" in info:
                    areas = info["area"]
                    if isinstance(areas, list):
                        area_desc = ", ".join(a.get("areaDesc", "") for a in areas)
                    else:
                        area_desc = areas.get("areaDesc", "")

                results.append({
                    "warning_id": w.get("identifier", w.get("id", "")),
                    "source_system": "nina",
                    "severity": info.get("severity", "Unknown"),
                    "urgency": info.get("urgency", "Unknown"),
                    "category": info.get("category", "Unknown"),
                    "headline": info.get("headline", ""),
                    "description": info.get("description", ""),
                    "instruction": info.get("instruction"),
                    "area_description": area_desc,
                    "area_geocode": info.get("area"),
                    "effective": _parse_time(info.get("effective") or w.get("sent")),
                    "expires": _parse_time(info.get("expires")),
                    "is_active": True,
                    "raw_data": w,
                })
    except Exception as e:
        logger.error(f"Error fetching NINA warnings: {e}")

    return results


async def _fetch_bund_warnings(client: httpx.AsyncClient, source: str, url: str) -> list:
    results = []
    try:
        resp = await client.get(url, timeout=30, headers={"Accept": "application/json"})
        if resp.status_code != 200:
            return results

        data = resp.json()
        if not isinstance(data, list):
            return results

        for w in data:
            if not _is_in_region(w):
                continue

            info = w.get("info", [{}])
            if isinstance(info, list) and info:
                info = info[0]

            results.append({
                "warning_id": f"{source}_{w.get('identifier', w.get('id', ''))}",
                "source_system": source,
                "severity": info.get("severity", w.get("severity", "Unknown")),
                "urgency": info.get("urgency", "Unknown"),
                "category": info.get("category", "Unknown"),
                "headline": info.get("headline", w.get("headline", "")),
                "description": info.get("description", w.get("description", "")),
                "instruction": info.get("instruction"),
                "area_description": info.get("areaDesc", ""),
                "effective": _parse_time(w.get("sent")),
                "expires": _parse_time(info.get("expires")),
                "is_active": True,
                "raw_data": w,
            })
    except Exception as e:
        logger.warning(f"Error fetching {source} warnings: {e}")

    return results


def _is_in_region(warning: dict) -> bool:
    relevant = ["troisdorf", "siegburg", "rhein-sieg", "bonn", "köln", "sankt augustin"]
    text = str(warning).lower()
    return any(r in text for r in relevant)


def _parse_time(time_str) -> Optional[datetime]:
    if not time_str:
        return None
    try:
        return datetime.fromisoformat(time_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None
