import logging
from datetime import datetime

import httpx

from app.config import settings
from app.models.database import async_session
from app.models.schemas import AirQuality

logger = logging.getLogger(__name__)

UBA_API = "https://www.umweltbundesamt.de/api/air_data/v3/measures/json"

STATIONS_NRW = {
    "BONN": {"id": "DENW081", "name": "Bonn-Auerberg"},
    "KOELN": {"id": "DENW005", "name": "Köln-Chorweiler"},
}


async def collect_air_quality():
    logger.info("Collecting air quality data...")
    results = []

    async with httpx.AsyncClient() as client:
        uba_data = await _fetch_uba(client)
        results.extend(uba_data)

        openaq_data = await _fetch_openaq(client)
        results.extend(openaq_data)

    async with async_session() as session:
        for data in results:
            entry = AirQuality(**data)
            session.add(entry)
        await session.commit()

    logger.info(f"Collected {len(results)} air quality readings")
    return results


async def _fetch_uba(client: httpx.AsyncClient) -> list:
    results = []
    try:
        now = datetime.utcnow()
        params = {
            "date_from": now.strftime("%Y-%m-%d"),
            "time_from": max(1, now.hour - 2),
            "date_to": now.strftime("%Y-%m-%d"),
            "time_to": now.hour + 1,
        }
        resp = await client.get(UBA_API, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "data" in data:
                for station_id, measurements in data["data"].items():
                    for station_key, station_info in STATIONS_NRW.items():
                        if station_info["id"] in station_id:
                            results.append({
                                "station_id": station_key,
                                "station_name": station_info["name"],
                                "pm10": measurements.get("1"),
                                "ozone": measurements.get("3"),
                                "no2": measurements.get("5"),
                                "pm25": measurements.get("9"),
                                "aqi": _calc_aqi(measurements),
                                "timestamp": now,
                                "source": "umweltbundesamt",
                                "raw_data": measurements,
                            })
    except Exception as e:
        logger.warning(f"Error fetching UBA data: {e}")

    return results


async def _fetch_openaq(client: httpx.AsyncClient) -> list:
    results = []
    try:
        url = "https://api.openaq.org/v2/latest"
        params = {
            "coordinates": f"{settings.center_lat},{settings.center_lon}",
            "radius": 30000,
            "limit": 10,
        }
        resp = await client.get(url, params=params, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            for result in data.get("results", []):
                location = result.get("location", "Unknown")
                measurements = result.get("measurements", [])

                pm25 = next((m["value"] for m in measurements if m["parameter"] == "pm25"), None)
                pm10 = next((m["value"] for m in measurements if m["parameter"] == "pm10"), None)
                no2 = next((m["value"] for m in measurements if m["parameter"] == "no2"), None)
                o3 = next((m["value"] for m in measurements if m["parameter"] == "o3"), None)

                results.append({
                    "station_id": f"openaq_{result.get('id', 'unknown')}",
                    "station_name": location,
                    "pm25": pm25,
                    "pm10": pm10,
                    "no2": no2,
                    "ozone": o3,
                    "aqi": _simple_aqi(pm25, pm10),
                    "timestamp": datetime.utcnow(),
                    "source": "openaq",
                    "raw_data": result,
                })
    except Exception as e:
        logger.warning(f"Error fetching OpenAQ data: {e}")

    return results


def _calc_aqi(measurements: dict) -> int:
    values = [v for v in measurements.values() if isinstance(v, (int, float)) and v > 0]
    return int(max(values)) if values else 0


def _simple_aqi(pm25, pm10) -> int:
    aqi = 0
    if pm25 and pm25 > 0:
        if pm25 <= 12:
            aqi = max(aqi, int(pm25 / 12 * 50))
        elif pm25 <= 35:
            aqi = max(aqi, int(50 + (pm25 - 12) / 23 * 50))
        else:
            aqi = max(aqi, int(100 + (pm25 - 35) / 20 * 50))
    if pm10 and pm10 > 0:
        if pm10 <= 54:
            aqi = max(aqi, int(pm10 / 54 * 50))
        else:
            aqi = max(aqi, int(50 + (pm10 - 54) / 100 * 50))
    return min(500, aqi)
