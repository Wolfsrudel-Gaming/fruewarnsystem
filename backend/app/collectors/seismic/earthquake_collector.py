import logging
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2

import httpx
from sqlalchemy import select

from app.models.database import async_session
from app.models.schemas import EarthquakeEvent

logger = logging.getLogger(__name__)

TROISDORF_LAT = 50.8159
TROISDORF_LON = 7.1533

NRW_BBOX = "6.5,50.3,7.8,51.2"
REGION_BOUNDS = {
    "minlat": 50.0, "maxlat": 51.5,
    "minlon": 6.5, "maxlon": 8.0,
}

REQUEST_TIMEOUT = 30


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return r * 2 * atan2(sqrt(a), sqrt(1 - a))


def _parse_timestamp(ts) -> datetime:
    if not ts:
        return datetime.utcnow()
    if isinstance(ts, (int, float)):
        return datetime.utcfromtimestamp(ts / 1000 if ts > 1e12 else ts)
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return datetime.utcnow()


async def _fetch_nrw(client: httpx.AsyncClient) -> list[dict]:
    results = []
    try:
        collections_url = "https://ogc-api.nrw.de/erdbebenereignisse/v1/collections"
        resp = await client.get(collections_url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        collections_data = resp.json()

        collection_id = "erdbebenereignisse"
        for coll in collections_data.get("collections", []):
            if "erdbeben" in coll.get("id", "").lower():
                collection_id = coll["id"]
                break

        items_url = f"https://ogc-api.nrw.de/erdbebenereignisse/v1/collections/{collection_id}/items"
        resp = await client.get(items_url, params={"f": "json", "bbox": NRW_BBOX}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        geojson = resp.json()

        for feature in geojson.get("features", []):
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [])
            if len(coords) < 2:
                continue

            lon, lat = coords[0], coords[1]
            depth = coords[2] if len(coords) > 2 else None
            magnitude = props.get("magnitude") or props.get("mag") or props.get("staerke")

            results.append({
                "event_id": f"nrw_{feature.get('id', props.get('id', ''))}",
                "magnitude": float(magnitude) if magnitude is not None else None,
                "depth_km": float(depth) if depth is not None else None,
                "lat": lat,
                "lon": lon,
                "location": props.get("ort") or props.get("location") or props.get("title", ""),
                "region": "NRW",
                "event_time": _parse_timestamp(props.get("zeit") or props.get("datetime") or props.get("time")),
                "felt_reports": props.get("felt") or props.get("gespuert"),
                "source": "nrw_gd",
                "raw_data": feature,
            })
    except Exception as e:
        logger.error(f"Error fetching NRW earthquake data: {e}")
    return results


async def _fetch_emsc(client: httpx.AsyncClient) -> list[dict]:
    results = []
    try:
        url = "https://www.seismicportal.eu/fdsnws/event/1/query"
        params = {
            "format": "json",
            "minlat": REGION_BOUNDS["minlat"],
            "maxlat": REGION_BOUNDS["maxlat"],
            "minlon": REGION_BOUNDS["minlon"],
            "maxlon": REGION_BOUNDS["maxlon"],
            "minmag": 1.5,
            "orderby": "time",
            "limit": 20,
        }
        resp = await client.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        for eq in data.get("features", []):
            props = eq.get("properties", {})
            geom = eq.get("geometry", {})
            coords = geom.get("coordinates", [])
            if len(coords) < 2:
                continue

            lon, lat = coords[0], coords[1]
            depth = coords[2] if len(coords) > 2 else None

            results.append({
                "event_id": f"emsc_{props.get('source_id', props.get('unid', eq.get('id', '')))}",
                "magnitude": props.get("mag"),
                "depth_km": float(depth) if depth is not None else None,
                "lat": lat,
                "lon": lon,
                "location": props.get("flynn_region", ""),
                "region": props.get("flynn_region", ""),
                "event_time": _parse_timestamp(props.get("time")),
                "felt_reports": props.get("felt"),
                "source": "emsc",
                "raw_data": eq,
            })
    except Exception as e:
        logger.error(f"Error fetching EMSC earthquake data: {e}")
    return results


async def _fetch_usgs(client: httpx.AsyncClient) -> list[dict]:
    results = []
    try:
        url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
        params = {
            "format": "geojson",
            "minlatitude": REGION_BOUNDS["minlat"],
            "maxlatitude": REGION_BOUNDS["maxlat"],
            "minlongitude": REGION_BOUNDS["minlon"],
            "maxlongitude": REGION_BOUNDS["maxlon"],
            "minmagnitude": 2,
            "orderby": "time",
            "limit": 20,
        }
        resp = await client.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        geojson = resp.json()

        for feature in geojson.get("features", []):
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [])
            if len(coords) < 2:
                continue

            lon, lat = coords[0], coords[1]
            depth = coords[2] if len(coords) > 2 else None

            results.append({
                "event_id": f"usgs_{feature.get('id', '')}",
                "magnitude": props.get("mag"),
                "depth_km": float(depth) if depth is not None else None,
                "lat": lat,
                "lon": lon,
                "location": props.get("place", ""),
                "region": props.get("place", ""),
                "event_time": _parse_timestamp(props.get("time")),
                "felt_reports": props.get("felt"),
                "source": "usgs",
                "raw_data": feature,
            })
    except Exception as e:
        logger.error(f"Error fetching USGS earthquake data: {e}")
    return results


async def collect_earthquakes():
    logger.info("Collecting earthquake data...")
    all_events = []

    async with httpx.AsyncClient() as client:
        nrw_events = await _fetch_nrw(client)
        emsc_events = await _fetch_emsc(client)
        usgs_events = await _fetch_usgs(client)

    all_events.extend(nrw_events)
    all_events.extend(emsc_events)
    all_events.extend(usgs_events)

    seen_ids = set()
    unique_events = []
    for event in all_events:
        eid = event["event_id"]
        if eid not in seen_ids:
            seen_ids.add(eid)
            unique_events.append(event)

    for event in unique_events:
        mag = event.get("magnitude")
        if mag is not None and mag >= 3.0:
            dist = _haversine_km(TROISDORF_LAT, TROISDORF_LON, event["lat"], event["lon"])
            logger.warning(
                f"EARTHQUAKE M{mag:.1f} at {event['location']} "
                f"({dist:.0f} km from Troisdorf, depth {event.get('depth_km')} km) "
                f"source={event['source']}"
            )

    async with async_session() as session:
        existing_ids_result = await session.execute(
            select(EarthquakeEvent.event_id).where(
                EarthquakeEvent.event_id.in_([e["event_id"] for e in unique_events])
            )
        )
        existing_ids = {row[0] for row in existing_ids_result}

        new_events = [e for e in unique_events if e["event_id"] not in existing_ids]
        for data in new_events:
            entry = EarthquakeEvent(**data)
            session.add(entry)
        await session.commit()

    logger.info(f"Collected {len(unique_events)} earthquake events ({len(new_events)} new)")
    return unique_events
