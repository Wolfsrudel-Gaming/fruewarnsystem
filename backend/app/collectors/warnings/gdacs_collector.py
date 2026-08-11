import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2
from typing import Optional

import httpx
from sqlalchemy import select

from app.models.database import async_session
from app.models.schemas import GDACAlert

logger = logging.getLogger(__name__)

GDACS_RSS_URL = "https://www.gdacs.org/xml/rss_24h.xml"

TROISDORF_LAT = 50.8159
TROISDORF_LON = 7.1533
MAX_DISTANCE_KM = 2000

REQUEST_TIMEOUT = 30

GDACS_NS = {
    "gdacs": "http://www.gdacs.org",
    "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return r * 2 * atan2(sqrt(a), sqrt(1 - a))


async def collect_gdacs_alerts():
    logger.info("Collecting GDACS global disaster alerts...")
    results = []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            resp = await client.get(GDACS_RSS_URL)
            resp.raise_for_status()

            root = ET.fromstring(resp.text)

            for item in root.findall(".//item"):
                title = _text(item, "title")
                description = _text(item, "description")
                link = _text(item, "link")
                pub_date = _text(item, "pubDate")

                lat = _float(_text(item, "geo:lat", GDACS_NS) or _text(item, "gdacs:lat", GDACS_NS))
                lon = _float(_text(item, "geo:long", GDACS_NS) or _text(item, "gdacs:long", GDACS_NS))

                if lat is None or lon is None:
                    continue

                distance = _haversine_km(TROISDORF_LAT, TROISDORF_LON, lat, lon)
                if distance > MAX_DISTANCE_KM:
                    continue

                alert_type = _text(item, "gdacs:eventtype", GDACS_NS) or _detect_type(title or "")
                severity = _text(item, "gdacs:severity", GDACS_NS) or _text(item, "gdacs:alertlevel", GDACS_NS) or "Unknown"
                country = _text(item, "gdacs:country", GDACS_NS) or ""

                alert_id_raw = _text(item, "gdacs:eventid", GDACS_NS) or _text(item, "guid")
                alert_id = f"gdacs_{alert_id_raw}" if alert_id_raw else f"gdacs_{hash(f'{title}_{pub_date}')}"

                event_time = _parse_datetime(pub_date)

                results.append({
                    "alert_id": alert_id,
                    "alert_type": alert_type,
                    "title": (title or "")[:500],
                    "description": (description or "")[:5000],
                    "severity": severity[:50],
                    "lat": lat,
                    "lon": lon,
                    "country": country[:100],
                    "distance_km": round(distance, 1),
                    "event_time": event_time,
                    "source": "gdacs",
                    "raw_data": {
                        "title": title, "description": description,
                        "link": link, "pubDate": pub_date,
                    },
                })

        except Exception as e:
            logger.error(f"Error fetching GDACS alerts: {e}")

    nearby = [r for r in results if r["distance_km"] < 500]
    if nearby:
        for r in nearby:
            logger.warning(
                f"GDACS ALERT: {r['alert_type']} - {r['title']} "
                f"({r['distance_km']:.0f} km, severity: {r['severity']})"
            )

    new_count = 0
    async with async_session() as session:
        existing_ids = set()
        if results:
            existing_result = await session.execute(
                select(GDACAlert.alert_id).where(
                    GDACAlert.alert_id.in_([r["alert_id"] for r in results])
                )
            )
            existing_ids = {row[0] for row in existing_result}

        for data in results:
            if data["alert_id"] not in existing_ids:
                entry = GDACAlert(**data)
                session.add(entry)
                new_count += 1
        await session.commit()

    logger.info(f"Collected {len(results)} GDACS alerts ({new_count} new)")
    return results


def _detect_type(title: str) -> str:
    t = title.lower()
    if "earthquake" in t or "erdbeben" in t:
        return "EQ"
    if "flood" in t or "hochwasser" in t:
        return "FL"
    if "cyclone" in t or "hurricane" in t or "storm" in t:
        return "TC"
    if "volcano" in t or "vulkan" in t:
        return "VO"
    if "drought" in t or "dürre" in t:
        return "DR"
    if "wildfire" in t or "waldbrand" in t:
        return "WF"
    return "OT"


def _text(element, tag: str, ns: dict = None) -> Optional[str]:
    child = element.find(tag, ns) if ns else element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return None


def _float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_datetime(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        pass
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(value).replace(tzinfo=None)
    except Exception:
        pass
    return None
