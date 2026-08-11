import logging
from datetime import datetime
from typing import Optional

import httpx

from app.models.database import async_session
from app.models.schemas import TrafficEvent

logger = logging.getLogger(__name__)

NRW_TRAFFIC_URL = "https://verkehr.nrw/web/api/its/trafficInformation/getAll"

TROISDORF_LAT = 50.8159
TROISDORF_LON = 7.1533
REGION_BBOX = {
    "min_lat": 50.6, "max_lat": 51.0,
    "min_lon": 6.9, "max_lon": 7.4,
}

RELEVANT_ROADS = {
    "A3", "A59", "A565", "A560", "A555",
    "B8", "B56", "B484",
    "L269", "L332", "L143",
}

REQUEST_TIMEOUT = 30


async def collect_nrw_traffic():
    logger.info("Collecting NRW traffic data...")
    results = []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            resp = await client.get(NRW_TRAFFIC_URL)
            resp.raise_for_status()
            data = resp.json()

            events = data if isinstance(data, list) else data.get("features", data.get("trafficInformation", data.get("data", [])))
            if not isinstance(events, list):
                events = [events] if events else []

            for event in events:
                props = event.get("properties", event) if isinstance(event, dict) else {}
                geom = event.get("geometry", {}) if isinstance(event, dict) else {}

                lat, lon = _extract_coords(geom)
                road = (props.get("road") or props.get("strasse") or props.get("strassenname") or "")
                road_upper = road.upper().replace(" ", "")

                in_bbox = lat is not None and lon is not None and _in_region(lat, lon)
                on_relevant_road = any(r in road_upper for r in RELEVANT_ROADS)

                if not in_bbox and not on_relevant_road:
                    continue

                event_type = _classify_event(props)
                severity = _map_severity(props)

                results.append({
                    "road": road[:200],
                    "event_type": event_type,
                    "title": (props.get("title") or props.get("titel") or props.get("description", ""))[:500],
                    "description": (props.get("description") or props.get("beschreibung") or "")[:2000],
                    "lat": lat,
                    "lon": lon,
                    "severity": severity,
                    "source": "verkehr_nrw",
                    "started_at": _parse_datetime(props.get("startTime") or props.get("beginn") or props.get("validFrom")),
                    "expected_end": _parse_datetime(props.get("endTime") or props.get("ende") or props.get("validTo")),
                    "is_active": True,
                    "raw_data": event,
                })

        except Exception as e:
            logger.error(f"Error fetching NRW traffic data: {e}")

    accidents = [r for r in results if r["event_type"] == "accident"]
    if len(accidents) > 3:
        logger.warning(f"NRW TRAFFIC: {len(accidents)} active accidents in region")

    async with async_session() as session:
        for data in results:
            entry = TrafficEvent(**data)
            session.add(entry)
        await session.commit()

    logger.info(f"Collected {len(results)} NRW traffic events")
    return results


def _in_region(lat: float, lon: float) -> bool:
    return (REGION_BBOX["min_lat"] <= lat <= REGION_BBOX["max_lat"] and
            REGION_BBOX["min_lon"] <= lon <= REGION_BBOX["max_lon"])


def _extract_coords(geom: dict) -> tuple[Optional[float], Optional[float]]:
    if not geom:
        return None, None

    coords = geom.get("coordinates", [])
    gtype = geom.get("type", "")

    if gtype == "Point" and len(coords) >= 2:
        return coords[1], coords[0]
    if gtype == "LineString" and coords:
        mid = coords[len(coords) // 2]
        if len(mid) >= 2:
            return mid[1], mid[0]
    if gtype == "MultiPoint" and coords:
        first = coords[0]
        if len(first) >= 2:
            return first[1], first[0]

    return None, None


def _classify_event(props: dict) -> str:
    event_type = (props.get("type") or props.get("typ") or props.get("eventType") or "").lower()
    desc = (props.get("description") or props.get("title") or "").lower()

    if "unfall" in desc or "accident" in event_type:
        return "accident"
    if "sperrung" in desc or "closure" in event_type or "gesperrt" in desc:
        return "closure"
    if "baustelle" in desc or "construction" in event_type:
        return "construction"
    if "stau" in desc or "congestion" in event_type:
        return "congestion"
    if "gefahr" in desc or "danger" in event_type:
        return "danger"
    return event_type or "general"


def _map_severity(props: dict) -> int:
    severity = props.get("severity") or props.get("schwere") or props.get("impact", "")
    if isinstance(severity, (int, float)):
        return int(min(100, max(0, severity)))

    severity_str = str(severity).lower()
    mapping = {
        "minor": 20, "gering": 20,
        "moderate": 40, "mittel": 40,
        "major": 70, "schwer": 70, "high": 70,
        "severe": 90, "critical": 100, "extrem": 100,
    }
    for key, val in mapping.items():
        if key in severity_str:
            return val
    return 30


def _parse_datetime(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        pass
    for fmt in ("%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(value), fmt)
        except (ValueError, TypeError):
            continue
    return None
