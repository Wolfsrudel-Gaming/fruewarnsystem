import logging
from datetime import datetime

import httpx

from app.config import settings
from app.models.database import async_session
from app.models.schemas import FuelStation

logger = logging.getLogger(__name__)

TANKERKOENIG_URL = "https://creativecommons.tankerkoenig.de/json/list.php"

TROISDORF_LAT = 50.8159
TROISDORF_LON = 7.1533
RADIUS_KM = 10

REQUEST_TIMEOUT = 30


async def collect_fuel_prices():
    if not settings.tankerkoenig_api_key:
        logger.debug("Tankerkönig API key not configured, skipping")
        return []

    logger.info("Collecting fuel prices...")
    results = []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            params = {
                "lat": TROISDORF_LAT,
                "lng": TROISDORF_LON,
                "rad": RADIUS_KM,
                "sort": "dist",
                "type": "all",
                "apikey": settings.tankerkoenig_api_key,
            }
            resp = await client.get(TANKERKOENIG_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

            if not data.get("ok"):
                logger.warning(f"Tankerkönig API error: {data.get('message', 'unknown')}")
                return results

            stations = data.get("stations", [])

            for station in stations:
                results.append({
                    "station_id": station.get("id", ""),
                    "name": station.get("name", station.get("brand", ""))[:300],
                    "lat": station.get("lat"),
                    "lon": station.get("lng"),
                    "diesel": _price(station.get("diesel")),
                    "e5": _price(station.get("e5")),
                    "e10": _price(station.get("e10")),
                    "is_open": station.get("isOpen", False),
                    "timestamp": datetime.utcnow(),
                    "source": "tankerkoenig",
                    "raw_data": station,
                })

        except Exception as e:
            logger.error(f"Error fetching fuel prices: {e}")

    closed_count = sum(1 for r in results if not r["is_open"])
    if results and closed_count > len(results) * 0.5:
        logger.warning(
            f"FUEL: {closed_count}/{len(results)} stations closed "
            f"({closed_count / len(results):.0%})"
        )

    async with async_session() as session:
        for data in results:
            entry = FuelStation(**data)
            session.add(entry)
        await session.commit()

    logger.info(f"Collected {len(results)} fuel stations")
    return results


def _price(value) -> float | None:
    if value is None:
        return None
    try:
        p = float(value)
        return p if 0 < p < 10 else None
    except (ValueError, TypeError):
        return None
