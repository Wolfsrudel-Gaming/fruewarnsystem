import logging
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy import select, and_

from app.models.database import async_session
from app.models.schemas import EventCalendar

logger = logging.getLogger(__name__)

KOELN_EVENTS_URL = "http://www.stadt-koeln.de/externe-dienste/open-data/events-od.php"
BONN_CKAN_URL = "https://opendata.bonn.de/api/3/action/package_show?id=veranstaltungen-veranstaltungkalender-bonn"

RISK_KEYWORDS = {
    0.8: ["marathon", "karneval", "karnevalszug", "zug"],
    0.7: ["stadion", "arena", "konzert", "festival"],
    0.5: ["demo", "demonstration"],
    0.3: ["markt", "fest"],
}


async def collect_events():
    logger.info("Collecting events...")
    results = []

    async with httpx.AsyncClient(timeout=30) as client:
        koeln_events = await _fetch_koeln_events(client)
        results.extend(koeln_events)

        bonn_events = await _fetch_bonn_events(client)
        results.extend(bonn_events)

    new_count = 0
    async with async_session() as session:
        for data in results:
            stmt = select(EventCalendar).where(
                and_(
                    EventCalendar.title == data["title"],
                    EventCalendar.starts_at == data.get("starts_at"),
                )
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                entry = EventCalendar(**data)
                session.add(entry)
                new_count += 1
        await session.commit()

    logger.info(f"Collected {len(results)} events, {new_count} new")
    return results


async def _fetch_koeln_events(client: httpx.AsyncClient) -> list:
    results = []
    try:
        resp = await client.get(KOELN_EVENTS_URL)
        resp.raise_for_status()
        events = resp.json()

        if not isinstance(events, list):
            events = events.get("items", events.get("events", []))

        for event in events:
            title = event.get("title", event.get("name", ""))
            description = event.get("description", event.get("text", ""))
            location = event.get("location", event.get("ort", ""))
            starts_at = _parse_datetime(
                event.get("start", event.get("begin", event.get("date")))
            )
            ends_at = _parse_datetime(event.get("end", event.get("ende")))

            if not title:
                continue

            results.append({
                "title": title,
                "description": description,
                "location": location if isinstance(location, str) else str(location),
                "lat": _safe_float(event.get("lat", event.get("latitude"))),
                "lon": _safe_float(event.get("lon", event.get("longitude"))),
                "risk_score": _calculate_risk(title, description),
                "starts_at": starts_at,
                "ends_at": ends_at,
                "source": "stadt_koeln",
                "is_manual": False,
                "raw_data": event,
            })
    except Exception as e:
        logger.error(f"Error fetching Koeln events: {e}")

    return results


async def _fetch_bonn_events(client: httpx.AsyncClient) -> list:
    results = []
    try:
        resp = await client.get(BONN_CKAN_URL)
        resp.raise_for_status()
        ckan_data = resp.json()

        if not ckan_data.get("success"):
            logger.warning("CKAN Bonn events request was not successful")
            return results

        resources = ckan_data.get("result", {}).get("resources", [])
        json_url = None
        for resource in resources:
            fmt = resource.get("format", "").upper()
            if fmt in ("JSON", "GEOJSON", "CSV"):
                json_url = resource.get("url")
                if fmt == "JSON":
                    break

        if not json_url:
            logger.warning("No suitable resource URL found in Bonn CKAN dataset")
            return results

        resp = await client.get(json_url)
        resp.raise_for_status()

        try:
            events = resp.json()
        except Exception:
            logger.warning("Could not parse Bonn events response as JSON")
            return results

        if isinstance(events, dict):
            events = events.get("records", events.get("result", events.get("data", [events])))

        if not isinstance(events, list):
            return results

        for event in events:
            title = event.get("title", event.get("Titel", event.get("name", "")))
            description = event.get("description", event.get("Beschreibung", ""))
            location = event.get("location", event.get("Ort", event.get("Veranstaltungsort", "")))
            starts_at = _parse_datetime(
                event.get("start", event.get("Beginn", event.get("Datum")))
            )
            ends_at = _parse_datetime(event.get("end", event.get("Ende")))

            if not title:
                continue

            results.append({
                "title": title,
                "description": description or "",
                "location": location if isinstance(location, str) else str(location),
                "lat": _safe_float(event.get("lat", event.get("latitude"))),
                "lon": _safe_float(event.get("lon", event.get("longitude"))),
                "risk_score": _calculate_risk(title, description or ""),
                "starts_at": starts_at,
                "ends_at": ends_at,
                "source": "stadt_bonn",
                "is_manual": False,
                "raw_data": event,
            })
    except Exception as e:
        logger.error(f"Error fetching Bonn events: {e}")

    return results


def _calculate_risk(title: str, description: str) -> float:
    text = f"{title} {description}".lower()
    for score, keywords in sorted(RISK_KEYWORDS.items(), reverse=True):
        if any(kw in text for kw in keywords):
            return score
    return 0.1


def _parse_datetime(value) -> Optional[datetime]:
    if value is None:
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


def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
