import logging
from datetime import datetime

import httpx

from app.config import settings
from app.models.database import async_session
from app.models.schemas import FireRisk

logger = logging.getLogger(__name__)

DWD_FIRE_INDEX_URL = "https://opendata.dwd.de/climate_environment/health/alerts/s31fg.json"
NASA_FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

WAHNER_HEIDE_BBOX = {
    "min_lat": 50.83,
    "max_lat": 50.91,
    "min_lon": 7.10,
    "max_lon": 7.20,
}


async def collect_fire_risk():
    logger.info("Collecting fire risk data...")
    results = []

    async with httpx.AsyncClient() as client:
        dwd_results = await _fetch_dwd_fire_index(client)
        results.extend(dwd_results)

        satellite_results = await _fetch_nasa_firms(client)
        results.extend(satellite_results)

    async with async_session() as session:
        for data in results:
            entry = FireRisk(**data)
            session.add(entry)
        await session.commit()

    logger.info(f"Collected {len(results)} fire risk entries")
    return results


async def _fetch_dwd_fire_index(client: httpx.AsyncClient) -> list:
    results = []
    try:
        resp = await client.get(DWD_FIRE_INDEX_URL, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        relevant_regions = ["rhein-sieg", "köln", "bonn", "troisdorf", "nordrhein"]
        for entry in data if isinstance(data, list) else [data]:
            region = entry.get("region", entry.get("name", "")).lower()
            if any(r in region for r in relevant_regions):
                results.append({
                    "region": entry.get("region", entry.get("name", "NRW")),
                    "risk_index": entry.get("value", entry.get("index", 1)),
                    "temperature": entry.get("temperature"),
                    "humidity": entry.get("humidity"),
                    "wind_speed": entry.get("wind_speed"),
                    "wind_direction": entry.get("wind_direction"),
                    "rain_last_24h": entry.get("precipitation_24h"),
                    "source": "dwd_fire_index",
                    "timestamp": datetime.utcnow(),
                    "raw_data": entry,
                })
    except Exception as e:
        logger.warning(f"Error fetching DWD fire index: {e}")
        results.append({
            "region": settings.region,
            "risk_index": 0,
            "source": "dwd_fire_index",
            "timestamp": datetime.utcnow(),
            "raw_data": {"error": str(e)},
        })

    return results


async def _fetch_nasa_firms(client: httpx.AsyncClient) -> list:
    results = []
    try:
        bbox = WAHNER_HEIDE_BBOX
        area = f"{bbox['min_lon']},{bbox['min_lat']},{bbox['max_lon']},{bbox['max_lat']}"
        extended_bbox = {
            "min_lat": settings.center_lat - 0.5,
            "max_lat": settings.center_lat + 0.5,
            "min_lon": settings.center_lon - 0.5,
            "max_lon": settings.center_lon + 0.5,
        }
        area_wide = f"{extended_bbox['min_lon']},{extended_bbox['min_lat']},{extended_bbox['max_lon']},{extended_bbox['max_lat']}"

        url = f"{NASA_FIRMS_URL}/VIIRS_SNPP_NRT/{area_wide}/1"
        resp = await client.get(url, timeout=30)

        hotspots = []
        if resp.status_code == 200 and resp.text.strip():
            lines = resp.text.strip().split("\n")
            if len(lines) > 1:
                headers = lines[0].split(",")
                for line in lines[1:]:
                    vals = line.split(",")
                    if len(vals) >= len(headers):
                        spot = dict(zip(headers, vals))
                        hotspots.append(spot)

        if hotspots:
            wahner_heide_spots = [
                s for s in hotspots
                if (bbox["min_lat"] <= float(s.get("latitude", 0)) <= bbox["max_lat"]
                    and bbox["min_lon"] <= float(s.get("longitude", 0)) <= bbox["max_lon"])
            ]

            results.append({
                "region": f"{settings.region} (Satellit)",
                "risk_index": min(5, len(hotspots) + 1),
                "satellite_hotspots": hotspots,
                "source": "nasa_firms",
                "timestamp": datetime.utcnow(),
                "raw_data": {
                    "total_hotspots": len(hotspots),
                    "wahner_heide_hotspots": len(wahner_heide_spots),
                },
            })
    except Exception as e:
        logger.warning(f"Error fetching NASA FIRMS data: {e}")

    return results
