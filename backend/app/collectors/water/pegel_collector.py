import logging
from datetime import datetime
from typing import Optional

import httpx

from app.config import settings
from app.models.database import async_session
from app.models.schemas import WaterLevel

logger = logging.getLogger(__name__)

PEGELONLINE_BASE = "https://www.pegelonline.wsv.de/webservices/rest-api/v2"

STATIONS = {
    "KOELN": {"uuid": "a6ee8177-107b-47dd-bcfd-30960ccc6e9c", "river": "Rhein"},
    "BONN": {"uuid": "ecbe8429-93dd-4f07-8a2b-3e18b5c9a49a", "river": "Rhein"},
    "SIEGBURG": {"uuid": None, "river": "Sieg", "search": "SIEGBURG"},
    "TROISDORF": {"uuid": None, "river": "Agger", "search": "TROISDORF"},
}

LANUV_BASE = "https://luadb.it.nrw.de/LUA/hygon/pegel.php"


async def fetch_pegelonline_station(client: httpx.AsyncClient, station_id: str, station_info: dict) -> Optional[dict]:
    try:
        if station_info.get("uuid"):
            url = f"{PEGELONLINE_BASE}/stations/{station_info['uuid']}/W/currentmeasurement.json"
        else:
            url = f"{PEGELONLINE_BASE}/stations.json?waters={station_info['river']}&includeCurrentMeasurement=true"

        resp = await client.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, list):
            for s in data:
                if station_info.get("search", "").lower() in s.get("longname", "").lower():
                    cm = s.get("currentMeasurement", {})
                    return {
                        "station_id": station_id,
                        "station_name": s.get("longname", station_id),
                        "river": station_info["river"],
                        "level_cm": cm.get("value"),
                        "trend": _parse_trend(cm.get("trend")),
                        "timestamp": _parse_timestamp(cm.get("timestamp")),
                        "source": "pegelonline",
                        "raw_data": s,
                    }
            return None

        return {
            "station_id": station_id,
            "station_name": station_id,
            "river": station_info["river"],
            "level_cm": data.get("value"),
            "trend": _parse_trend(data.get("trend")),
            "timestamp": _parse_timestamp(data.get("timestamp")),
            "source": "pegelonline",
            "raw_data": data,
        }
    except Exception as e:
        logger.error(f"Error fetching pegel for {station_id}: {e}")
        return None


def _parse_trend(trend_val) -> str:
    if trend_val is None:
        return "unknown"
    if isinstance(trend_val, (int, float)):
        if trend_val > 0:
            return "rising"
        elif trend_val < 0:
            return "falling"
        return "stable"
    return str(trend_val).lower()


def _parse_timestamp(ts_str) -> datetime:
    if not ts_str:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return datetime.utcnow()


async def collect_water_levels():
    logger.info("Collecting water levels...")
    results = []

    async with httpx.AsyncClient() as client:
        for station_id, station_info in STATIONS.items():
            data = await fetch_pegelonline_station(client, station_id, station_info)
            if data:
                results.append(data)

        try:
            all_stations_url = f"{PEGELONLINE_BASE}/stations.json?includeCurrentMeasurement=true"
            resp = await client.get(all_stations_url, timeout=30)
            resp.raise_for_status()
            all_stations = resp.json()

            rhein_sieg_rivers = ["sieg", "agger", "pleisbach", "swistbach"]
            for station in all_stations:
                water = station.get("water", {}).get("longname", "").lower()
                if water in rhein_sieg_rivers:
                    existing = [r for r in results if r["station_id"] == station.get("shortname")]
                    if not existing:
                        cm = station.get("currentMeasurement", {})
                        if cm:
                            results.append({
                                "station_id": station.get("shortname", "UNKNOWN"),
                                "station_name": station.get("longname", ""),
                                "river": water.title(),
                                "level_cm": cm.get("value"),
                                "trend": _parse_trend(cm.get("trend")),
                                "timestamp": _parse_timestamp(cm.get("timestamp")),
                                "source": "pegelonline",
                                "raw_data": station,
                            })
        except Exception as e:
            logger.warning(f"Error fetching additional stations: {e}")

    async with async_session() as session:
        for data in results:
            entry = WaterLevel(**data)
            session.add(entry)
        await session.commit()

    logger.info(f"Collected {len(results)} water level readings")
    return results
