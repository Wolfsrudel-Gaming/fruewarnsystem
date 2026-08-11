"""Stromnetz-Status über SMARD (Bundesnetzagentur)."""
import logging
from datetime import datetime

import httpx

from app.models.database import async_session
from app.models.schemas import GridStatus

logger = logging.getLogger(__name__)

SMARD_BASE = "https://www.smard.de/app/chart_data"

# Verifizierte Filter-IDs (Stand 2026; alte 1001 ist tot)
FILTER_CONSUMPTION = 410       # Netzlast / Verbrauch
FILTER_GENERATION = 4359       # Realisierte Erzeugung gesamt
FILTER_RENEWABLES = {
    1223: "Biomasse",
    4066: "Wasserkraft",
    4067: "Wind Onshore",
    4068: "Photovoltaik",
    4069: "Sonstige Erneuerbare",
    4070: "Pumpspeicher",
    4169: "Wind Offshore",
}

RESOLUTION = "hour"
REQUEST_TIMEOUT = 30


async def collect_grid_status():
    logger.info("Collecting grid status from SMARD...")
    results = []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        try:
            generation_mw = await _fetch_latest_value(client, FILTER_GENERATION)
            consumption_mw = await _fetch_latest_value(client, FILTER_CONSUMPTION)

            renewable_parts = {}
            for fid, name in FILTER_RENEWABLES.items():
                val = await _fetch_latest_value(client, fid)
                if val is not None:
                    renewable_parts[name] = val

            renewable_mw = sum(renewable_parts.values()) if renewable_parts else None
            renewable_share = None
            if generation_mw and generation_mw > 0 and renewable_mw is not None:
                renewable_share = round(min(1.0, renewable_mw / generation_mw), 3)

            if generation_mw is not None and consumption_mw is not None:
                balance_mw = generation_mw - consumption_mw
                is_stressed = balance_mw < 0 or consumption_mw > generation_mw * 0.95
                stress_indicator = None
                if is_stressed:
                    parts = []
                    if balance_mw < 0:
                        parts.append(f"Importbedarf {abs(balance_mw):.0f} MW")
                    if generation_mw > 0 and consumption_mw > generation_mw * 0.95:
                        parts.append(
                            f"Last bei {consumption_mw / generation_mw * 100:.1f}% der Erzeugung"
                        )
                    stress_indicator = "; ".join(parts)
                    logger.warning("Grid stress detected: %s", stress_indicator)

                results.append({
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
                        "renewable_mw": renewable_mw,
                        "renewable_parts": renewable_parts,
                        "resolution": RESOLUTION,
                    },
                })
            else:
                logger.warning(
                    "Could not retrieve generation (%s) or consumption (%s) from SMARD",
                    generation_mw, consumption_mw,
                )
        except Exception as e:
            logger.error("Error collecting grid status: %s", e)

    async with async_session() as session:
        for data in results:
            session.add(GridStatus(**data))
        await session.commit()

    logger.info("Collected %s grid status readings", len(results))
    return results


async def _fetch_latest_value(client: httpx.AsyncClient, filter_id: int) -> float | None:
    try:
        index_url = f"{SMARD_BASE}/{filter_id}/DE/index_{RESOLUTION}.json"
        resp = await client.get(index_url)
        resp.raise_for_status()
        timestamps = resp.json().get("timestamps", [])
        if not timestamps:
            return None

        # Neueste Blöcke rückwärts, bis ein Wert da ist
        for ts in reversed(timestamps[-3:]):
            data_url = f"{SMARD_BASE}/{filter_id}/DE/{filter_id}_DE_{RESOLUTION}_{ts}.json"
            resp = await client.get(data_url)
            if resp.status_code != 200:
                continue
            series = resp.json().get("series", [])
            for entry in reversed(series):
                if isinstance(entry, list) and len(entry) >= 2 and entry[1] is not None:
                    return float(entry[1])
        return None
    except Exception as e:
        logger.error("Error fetching SMARD data for filter %s: %s", filter_id, e)
        return None
