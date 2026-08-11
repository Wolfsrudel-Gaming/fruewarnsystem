import logging
from datetime import datetime

import httpx

from app.config import settings
from app.models.database import async_session
from app.models.schemas import TrafficEvent

logger = logging.getLogger(__name__)

AUTOBAHN_API_BASE = "https://verkehr.autobahn.de/o/autobahn"

RELEVANT_ROADS = ["A59", "A565", "A3", "A555", "A560", "A61"]


async def collect_traffic():
    logger.info("Collecting traffic data...")
    results = []

    async with httpx.AsyncClient() as client:
        for road in RELEVANT_ROADS:
            warnings = await _fetch_road_warnings(client, road)
            results.extend(warnings)

            closures = await _fetch_road_closures(client, road)
            results.extend(closures)

        rail_events = await _fetch_rail_disruptions(client)
        results.extend(rail_events)

    async with async_session() as session:
        for data in results:
            from sqlalchemy import select
            stmt = select(TrafficEvent).where(TrafficEvent.event_id == data["event_id"])
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                entry = TrafficEvent(**data)
                session.add(entry)
        await session.commit()

    logger.info(f"Collected {len(results)} traffic events")
    return results


async def _fetch_road_warnings(client: httpx.AsyncClient, road: str) -> list:
    results = []
    try:
        url = f"{AUTOBAHN_API_BASE}/{road}/services/warning"
        resp = await client.get(url, timeout=20)
        if resp.status_code != 200:
            return results

        data = resp.json()
        warnings = data.get("warning", [])

        for w in warnings:
            coord = w.get("coordinate", {})
            results.append({
                "event_id": f"ab_{road}_{w.get('identifier', w.get('extent', ''))}",
                "road": road,
                "event_type": _map_event_type(w.get("abnormalTrafficType", w.get("title", ""))),
                "title": w.get("title", w.get("subtitle", "")),
                "description": "\n".join(w.get("description", [])) if isinstance(w.get("description"), list) else w.get("description"),
                "lat": float(coord.get("lat", 0)) if coord.get("lat") else None,
                "lon": float(coord.get("long", 0)) if coord.get("long") else None,
                "severity": _estimate_severity(w),
                "is_active": True,
                "source": "autobahn_api",
                "started_at": _parse_time(w.get("startTimestamp")),
                "raw_data": w,
            })
    except Exception as e:
        logger.warning(f"Error fetching warnings for {road}: {e}")

    return results


async def _fetch_road_closures(client: httpx.AsyncClient, road: str) -> list:
    results = []
    try:
        url = f"{AUTOBAHN_API_BASE}/{road}/services/closure"
        resp = await client.get(url, timeout=20)
        if resp.status_code != 200:
            return results

        data = resp.json()
        closures = data.get("closure", [])

        for c in closures:
            coord = c.get("coordinate", {})
            results.append({
                "event_id": f"ab_closure_{road}_{c.get('identifier', '')}",
                "road": road,
                "event_type": "closure",
                "title": c.get("title", ""),
                "description": "\n".join(c.get("description", [])) if isinstance(c.get("description"), list) else c.get("description"),
                "lat": float(coord.get("lat", 0)) if coord.get("lat") else None,
                "lon": float(coord.get("long", 0)) if coord.get("long") else None,
                "severity": 60,
                "is_active": True,
                "source": "autobahn_api",
                "started_at": _parse_time(c.get("startTimestamp")),
                "ended_at": _parse_time(c.get("endTimestamp")),
                "raw_data": c,
            })
    except Exception as e:
        logger.warning(f"Error fetching closures for {road}: {e}")

    return results


async def _fetch_rail_disruptions(client: httpx.AsyncClient) -> list:
    results = []
    try:
        url = "https://www.bahn.de/web/api/reiseloesung/stoerungen"
        resp = await client.get(url, timeout=20, headers={"Accept": "application/json"})
        if resp.status_code != 200:
            return results

        data = resp.json()
        disruptions = data if isinstance(data, list) else data.get("disruptions", [])

        relevant_stations = ["köln", "bonn", "siegburg", "troisdorf"]
        for d in disruptions:
            text = str(d).lower()
            if any(s in text for s in relevant_stations):
                results.append({
                    "event_id": f"rail_{d.get('id', hash(str(d)))}",
                    "road": "Bahn",
                    "event_type": "rail_disruption",
                    "title": d.get("title", d.get("header", "Bahnstörung")),
                    "description": d.get("text", d.get("description", "")),
                    "severity": 30,
                    "is_active": True,
                    "source": "deutsche_bahn",
                    "started_at": datetime.utcnow(),
                    "raw_data": d,
                })
    except Exception as e:
        logger.warning(f"Error fetching rail disruptions: {e}")

    return results


def _map_event_type(text: str) -> str:
    text_lower = text.lower()
    if "unfall" in text_lower or "accident" in text_lower:
        return "accident"
    if "baustelle" in text_lower or "construction" in text_lower:
        return "construction"
    if "stau" in text_lower or "jam" in text_lower:
        return "jam"
    if "sperrung" in text_lower or "closure" in text_lower:
        return "closure"
    return "warning"


def _estimate_severity(warning: dict) -> int:
    title = str(warning.get("title", "")).lower()
    if any(w in title for w in ["unfall", "vollsperrung", "gefahrgut"]):
        return 80
    if any(w in title for w in ["stau", "sperrung"]):
        return 50
    return 30


def _parse_time(time_str) -> datetime:
    if not time_str:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(time_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return datetime.utcnow()
