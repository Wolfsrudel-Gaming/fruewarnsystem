import logging
from datetime import datetime

import httpx

from app.models.database import async_session
from app.models.schemas import GridStatus

logger = logging.getLogger(__name__)

SMARD_BASE = "https://www.smard.de/app/chart_data"
FILTER_GENERATION = 1001
FILTER_CONSUMPTION = 410
RESOLUTION = "quarterhour"


async def collect_grid_status():
    logger.info("Collecting grid status from SMARD...")
    results = []

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            generation_mw = await _fetch_latest_value(client, FILTER_GENERATION)
            consumption_mw = await _fetch_latest_value(client, FILTER_CONSUMPTION)

            if generation_mw is not None and consumption_mw is not None:
                balance_mw = generation_mw - consumption_mw
                renewable_share = None
                is_stressed = consumption_mw > generation_mw * 0.95 or balance_mw < 0
                stress_indicator = None

                if is_stressed:
                    indicators = []
                    if balance_mw < 0:
                        indicators.append(f"negative balance: {balance_mw:.0f} MW")
                    if consumption_mw > generation_mw * 0.95:
                        indicators.append(
                            f"consumption at {consumption_mw / generation_mw * 100:.1f}% of generation"
                        )
                    stress_indicator = "; ".join(indicators)
                    logger.warning(f"Grid stress detected: {stress_indicator}")

                result = {
                    "region": "DE",
                    "generation_mw": generation_mw,
                    "consumption_mw": consumption_mw,
                    "balance_mw": balance_mw,
                    "renewable_share": renewable_share,
                    "is_stressed": is_stressed,
                    "stress_indicator": stress_indicator,
                    "timestamp": datetime.utcnow(),
                    "source": "smard_bundesnetzagentur",
                    "raw_data": {
                        "generation_mw": generation_mw,
                        "consumption_mw": consumption_mw,
                        "balance_mw": balance_mw,
                        "resolution": RESOLUTION,
                    },
                }
                results.append(result)
            else:
                logger.warning("Could not retrieve generation or consumption data from SMARD")
        except Exception as e:
            logger.error(f"Error collecting grid status: {e}")

    async with async_session() as session:
        for data in results:
            entry = GridStatus(**data)
            session.add(entry)
        await session.commit()

    logger.info(f"Collected {len(results)} grid status readings")
    return results


async def _fetch_latest_value(client: httpx.AsyncClient, filter_id: int) -> float | None:
    try:
        index_url = f"{SMARD_BASE}/{filter_id}/DE/index_{RESOLUTION}.json"
        resp = await client.get(index_url)
        resp.raise_for_status()
        index_data = resp.json()

        timestamps = index_data.get("timestamps", [])
        if not timestamps:
            return None

        latest_ts = timestamps[-1]
        data_url = f"{SMARD_BASE}/{filter_id}/DE/{filter_id}_DE_{RESOLUTION}_{latest_ts}.json"
        resp = await client.get(data_url)
        resp.raise_for_status()
        series = resp.json().get("series", [])

        for entry in reversed(series):
            if isinstance(entry, list) and len(entry) >= 2 and entry[1] is not None:
                return float(entry[1])

        return None
    except Exception as e:
        logger.error(f"Error fetching SMARD data for filter {filter_id}: {e}")
        return None
