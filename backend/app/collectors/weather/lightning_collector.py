import logging
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2

import httpx

from app.models.database import async_session
from app.models.schemas import LightningData

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

TROISDORF_LAT = 50.8159
TROISDORF_LON = 7.1533
MAX_DISTANCE_KM = 50

REQUEST_TIMEOUT = 30


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return r * 2 * atan2(sqrt(a), sqrt(1 - a))


async def collect_lightning():
    logger.info("Collecting lightning data...")
    results = []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            params = {
                "latitude": TROISDORF_LAT,
                "longitude": TROISDORF_LON,
                "minutely_15": "lightning_potential",
                "current": "weather_code",
                "timezone": "Europe/Berlin",
                "forecast_days": 1,
            }
            resp = await client.get(OPEN_METEO_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

            minutely = data.get("minutely_15", {})
            times = minutely.get("time", [])
            potentials = minutely.get("lightning_potential", [])

            current = data.get("current", {})
            weather_code = current.get("weather_code", 0)
            is_thunderstorm = weather_code in (95, 96, 99)

            for i, (t, p) in enumerate(zip(times, potentials)):
                if p is None or p <= 0:
                    continue

                try:
                    timestamp = datetime.fromisoformat(t)
                except ValueError:
                    timestamp = datetime.utcnow()

                results.append({
                    "lat": TROISDORF_LAT,
                    "lon": TROISDORF_LON,
                    "amplitude": p,
                    "distance_km": 0,
                    "timestamp": timestamp,
                    "source": "open_meteo_lightning",
                })

            if is_thunderstorm and not results:
                results.append({
                    "lat": TROISDORF_LAT,
                    "lon": TROISDORF_LON,
                    "amplitude": None,
                    "distance_km": 0,
                    "timestamp": datetime.utcnow(),
                    "source": "open_meteo_thunderstorm",
                })
                logger.warning(f"THUNDERSTORM: Weather code {weather_code} near Troisdorf")

        except Exception as e:
            logger.error(f"Error fetching lightning data: {e}")

    if results:
        high_activity = [r for r in results if r.get("amplitude") and r["amplitude"] > 50]
        if high_activity:
            logger.warning(
                f"HIGH LIGHTNING ACTIVITY: {len(high_activity)} readings with "
                f"potential > 50 near Troisdorf"
            )

    async with async_session() as session:
        for data in results:
            entry = LightningData(**data)
            session.add(entry)
        await session.commit()

    logger.info(f"Collected {len(results)} lightning readings")
    return results
