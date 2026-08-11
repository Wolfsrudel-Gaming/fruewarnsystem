import logging
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy import select

from app.models.database import async_session
from app.models.schemas import TransitDisruption

logger = logging.getLogger(__name__)

KVB_ADDINFO_URL = "https://auskunft.kvb.koeln/auskunft/XML_ADDINFO_REQUEST"
VRS_EFA_URL = "https://www.vrs.de/mq/XML_ADDINFO_REQUEST"

RELEVANT_LINES = {
    "S12", "S13", "S19", "RB25", "RE8", "RE9",
    "66", "67",
    "S-Bahn", "Regionalbahn",
}

REQUEST_TIMEOUT = 30


async def collect_transit_disruptions():
    logger.info("Collecting transit disruptions...")
    all_disruptions = []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        kvb = await _fetch_kvb(client)
        all_disruptions.extend(kvb)

        vrs = await _fetch_vrs(client)
        all_disruptions.extend(vrs)

    new_count = 0
    async with async_session() as session:
        for data in all_disruptions:
            did = data.get("disruption_id")
            if did:
                existing = await session.execute(
                    select(TransitDisruption).where(TransitDisruption.disruption_id == did)
                )
                if existing.scalar_one_or_none():
                    continue

            entry = TransitDisruption(**data)
            session.add(entry)
            new_count += 1

            if data["disruption_type"] in ("cancellation", "closure"):
                logger.warning(f"TRANSIT: {data['title']} ({data['line']})")
        await session.commit()

    logger.info(f"Collected {len(all_disruptions)} transit disruptions ({new_count} new)")
    return all_disruptions


async def _fetch_kvb(client: httpx.AsyncClient) -> list[dict]:
    results = []
    try:
        params = {
            "outputFormat": "rapidJSON",
            "coordOutputFormat": "WGS84[DD.ddddd]",
        }
        resp = await client.get(KVB_ADDINFO_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        infos = data.get("additionalInformation", data.get("infos", []))
        if isinstance(infos, dict):
            infos = infos.get("current", []) + infos.get("planned", [])

        for info in infos if isinstance(infos, list) else []:
            _parse_disruption(info, "kvb", results)

    except Exception as e:
        logger.error(f"Error fetching KVB disruptions: {e}")
    return results


async def _fetch_vrs(client: httpx.AsyncClient) -> list[dict]:
    results = []
    try:
        params = {
            "outputFormat": "rapidJSON",
            "coordOutputFormat": "WGS84[DD.ddddd]",
        }
        resp = await client.get(VRS_EFA_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        infos = data.get("additionalInformation", data.get("infos", []))
        if isinstance(infos, dict):
            infos = infos.get("current", []) + infos.get("planned", [])

        for info in infos if isinstance(infos, list) else []:
            _parse_disruption(info, "vrs", results)

    except Exception as e:
        logger.error(f"Error fetching VRS disruptions: {e}")
    return results


def _parse_disruption(info: dict, source: str, results: list):
    title = info.get("title", info.get("subtitle", ""))
    description = info.get("description", info.get("content", ""))
    if isinstance(description, dict):
        description = description.get("text", str(description))

    lines = []
    for prop in info.get("properties", []):
        if prop.get("name") in ("line", "lines", "Linie"):
            val = prop.get("value", "")
            lines.extend(val.split(",") if isinstance(val, str) else [str(val)])

    affected = info.get("affectedLines", info.get("lines", []))
    if isinstance(affected, list):
        for line in affected:
            if isinstance(line, dict):
                lines.append(line.get("name", line.get("number", "")))
            elif isinstance(line, str):
                lines.append(line)

    line_str = ", ".join(l.strip() for l in lines if l.strip()) or "Unbekannt"

    disruption_type = _classify_type(title, description)
    valid_from = _parse_dt(info.get("validFrom") or info.get("validFromDateTime"))
    valid_to = _parse_dt(info.get("validTo") or info.get("validToDateTime"))

    did = info.get("id") or info.get("infoID")
    disruption_id = f"{source}_{did}" if did else None

    results.append({
        "disruption_id": disruption_id,
        "line": line_str[:100],
        "route": info.get("subtitle", "")[:500] if info.get("subtitle") else None,
        "disruption_type": disruption_type,
        "title": (title or "Störung")[:500],
        "description": (description or "")[:5000] if description else None,
        "is_active": True,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "source": source,
        "raw_data": info,
    })


def _classify_type(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    if "ausfall" in text or "fällt aus" in text:
        return "cancellation"
    if "sperrung" in text or "gesperrt" in text:
        return "closure"
    if "umleitung" in text:
        return "diversion"
    if "verspätung" in text or "verzögerung" in text:
        return "delay"
    if "bauarbeit" in text or "baustelle" in text:
        return "construction"
    if "einschränkung" in text or "beeinträchtigung" in text:
        return "restriction"
    return "general"


def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        pass
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(value), fmt)
        except (ValueError, TypeError):
            continue
    return None
