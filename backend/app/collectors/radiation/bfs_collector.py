import logging
from datetime import datetime

import httpx

from app.models.database import async_session
from app.models.schemas import RadiationReading

logger = logging.getLogger(__name__)

TROISDORF_LAT = 50.8159
TROISDORF_LON = 7.1533

LAT_MIN = 50.5
LAT_MAX = 51.1
LON_MIN = 6.8
LON_MAX = 7.5

ELEVATED_THRESHOLD_NSV = 300

REQUEST_TIMEOUT = 30


def _is_in_region(lat: float, lon: float) -> bool:
    return LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX


async def _fetch_odl_json(client: httpx.AsyncClient) -> list[dict]:
    results = []
    try:
        url = "https://odlinfo.bfs.de/json/stat.json"
        resp = await client.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        for station_id, station_data in data.items():
            if not isinstance(station_data, dict):
                continue

            lat = station_data.get("lat")
            lon = station_data.get("lon")
            if lat is None or lon is None:
                continue
            if not _is_in_region(lat, lon):
                continue

            mw = station_data.get("mw")
            if mw is None:
                continue

            # BfS reports in uSv/h, convert to nSv/h
            gamma_nsv = mw * 1000

            ts = station_data.get("t")
            timestamp = datetime.utcnow()
            if ts:
                try:
                    timestamp = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).replace(tzinfo=None)
                except (ValueError, AttributeError):
                    pass

            results.append({
                "station_id": station_id,
                "station_name": station_data.get("name", station_id),
                "lat": lat,
                "lon": lon,
                "gamma_dose_rate": gamma_nsv,
                "is_elevated": gamma_nsv > ELEVATED_THRESHOLD_NSV,
                "timestamp": timestamp,
                "source": "bfs_odl",
                "raw_data": station_data,
            })
    except Exception as e:
        logger.error(f"Error fetching BfS ODL JSON data: {e}")
    return results


async def _fetch_wfs(client: httpx.AsyncClient) -> list[dict]:
    results = []
    try:
        url = "https://www.imis.bfs.de/ogc/opendata/ows"
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeName": "opendata:odlinfo_odl_1h_latest",
            "outputFormat": "application/json",
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
            if not _is_in_region(lat, lon):
                continue

            mw = props.get("value") or props.get("mw") or props.get("value_cosmic")
            if mw is None:
                continue

            gamma_nsv = float(mw) * 1000

            ts = props.get("end_measure") or props.get("timestamp")
            timestamp = datetime.utcnow()
            if ts:
                try:
                    timestamp = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).replace(tzinfo=None)
                except (ValueError, AttributeError):
                    pass

            sid = props.get("kenn") or props.get("id") or feature.get("id", "")

            results.append({
                "station_id": str(sid),
                "station_name": props.get("name", str(sid)),
                "lat": lat,
                "lon": lon,
                "gamma_dose_rate": gamma_nsv,
                "is_elevated": gamma_nsv > ELEVATED_THRESHOLD_NSV,
                "timestamp": timestamp,
                "source": "bfs_wfs",
                "raw_data": feature,
            })
    except Exception as e:
        logger.error(f"Error fetching BfS WFS data: {e}")
    return results


async def collect_radiation():
    logger.info("Collecting radiation data...")
    results = []

    async with httpx.AsyncClient() as client:
        results = await _fetch_odl_json(client)

        if not results:
            logger.info("ODL JSON returned no results, trying WFS fallback...")
            results = await _fetch_wfs(client)

    elevated = [r for r in results if r["is_elevated"]]
    if elevated:
        for r in elevated:
            logger.warning(
                f"ELEVATED RADIATION: {r['station_name']} ({r['station_id']}) "
                f"at {r['gamma_dose_rate']:.0f} nSv/h (threshold: {ELEVATED_THRESHOLD_NSV} nSv/h)"
            )

    async with async_session() as session:
        for data in results:
            entry = RadiationReading(**data)
            session.add(entry)
        await session.commit()

    logger.info(f"Collected {len(results)} radiation readings ({len(elevated)} elevated)")
    return results
