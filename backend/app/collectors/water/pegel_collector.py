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
    "BONN": {"uuid": "593647aa-9fea-43ec-a7d6-6476a76ae868", "river": "Rhein"},
    "SIEGBURG": {"uuid": None, "river": "Sieg", "search": "SIEGBURG"},
    "TROISDORF": {"uuid": None, "river": "Agger", "search": "TROISDORF"},
}

RIVER_THRESHOLDS = {
    "rhein": {
        "low_extreme": 80,   # Schifffahrt eingestellt
        "low_warning": 150,  # Niedrigwasser-Warnung
        "low_normal": 200,   # Unterer Normalbereich
        "high_normal": 600,  # Oberer Normalbereich
        "high_warning": 700, # Hochwasser-Warnung
        "high_extreme": 850, # Extremhochwasser
    },
    "sieg": {
        "low_extreme": 15,
        "low_warning": 30,
        "low_normal": 50,
        "high_normal": 300,
        "high_warning": 400,
        "high_extreme": 500,
    },
    "agger": {
        "low_extreme": 10,
        "low_warning": 20,
        "low_normal": 35,
        "high_normal": 200,
        "high_warning": 280,
        "high_extreme": 350,
    },
    "pleisbach": {
        "low_extreme": 5,
        "low_warning": 10,
        "low_normal": 20,
        "high_normal": 100,
        "high_warning": 150,
        "high_extreme": 200,
    },
    "swistbach": {
        "low_extreme": 5,
        "low_warning": 10,
        "low_normal": 20,
        "high_normal": 80,
        "high_warning": 120,
        "high_extreme": 160,
    },
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


def classify_water_level(level_cm: Optional[float], river: str) -> dict:
    if level_cm is None:
        return {"warning_level": "unknown", "condition": "no_data", "deviation": 0}

    river_key = river.lower()
    thresholds = None
    for key in RIVER_THRESHOLDS:
        if key in river_key:
            thresholds = RIVER_THRESHOLDS[key]
            break

    if not thresholds:
        thresholds = RIVER_THRESHOLDS.get("sieg")

    if level_cm <= thresholds["low_extreme"]:
        return {"warning_level": "extreme_low", "condition": "drought", "deviation": (thresholds["low_extreme"] - level_cm) / thresholds["low_normal"]}
    elif level_cm <= thresholds["low_warning"]:
        return {"warning_level": "low", "condition": "niedrigwasser", "deviation": (thresholds["low_warning"] - level_cm) / thresholds["low_normal"]}
    elif level_cm <= thresholds["low_normal"]:
        return {"warning_level": "below_normal", "condition": "unterdurchschnittlich", "deviation": 0}
    elif level_cm <= thresholds["high_normal"]:
        return {"warning_level": "normal", "condition": "normal", "deviation": 0}
    elif level_cm <= thresholds["high_warning"]:
        return {"warning_level": "high", "condition": "hochwasser", "deviation": (level_cm - thresholds["high_normal"]) / thresholds["high_normal"]}
    elif level_cm <= thresholds["high_extreme"]:
        return {"warning_level": "very_high", "condition": "starkes_hochwasser", "deviation": (level_cm - thresholds["high_normal"]) / thresholds["high_normal"]}
    else:
        return {"warning_level": "extreme_high", "condition": "extremhochwasser", "deviation": (level_cm - thresholds["high_normal"]) / thresholds["high_normal"]}


async def collect_water_levels():
    logger.info("Collecting water levels...")
    results = []

    async with httpx.AsyncClient() as client:
        for station_id, station_info in STATIONS.items():
            data = await fetch_pegelonline_station(client, station_id, station_info)
            if data:
                classification = classify_water_level(data.get("level_cm"), data.get("river", ""))
                data["classification"] = classification
                if classification["condition"] in ("drought", "niedrigwasser"):
                    logger.warning(
                        f"NIEDRIGWASSER: {data['station_name']} ({data['river']}) "
                        f"bei {data['level_cm']} cm - {classification['condition']}"
                    )
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
                            level_val = cm.get("value")
                            river_name = water.title()
                            classification = classify_water_level(level_val, river_name)
                            entry = {
                                "station_id": station.get("shortname", "UNKNOWN"),
                                "station_name": station.get("longname", ""),
                                "river": river_name,
                                "level_cm": level_val,
                                "trend": _parse_trend(cm.get("trend")),
                                "timestamp": _parse_timestamp(cm.get("timestamp")),
                                "source": "pegelonline",
                                "raw_data": station,
                                "classification": classification,
                            }
                            if classification["condition"] in ("drought", "niedrigwasser"):
                                logger.warning(
                                    f"NIEDRIGWASSER: {entry['station_name']} ({river_name}) "
                                    f"bei {level_val} cm - {classification['condition']}"
                                )
                            results.append(entry)
        except Exception as e:
            logger.warning(f"Error fetching additional stations: {e}")

    async with async_session() as session:
        for data in results:
            entry = WaterLevel(**data)
            session.add(entry)
        await session.commit()

    logger.info(f"Collected {len(results)} water level readings")
    return results
