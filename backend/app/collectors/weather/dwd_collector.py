import logging
import json
from datetime import datetime
from typing import Optional
from zipfile import ZipFile
from io import BytesIO

import httpx

from app.config import settings
from app.models.database import async_session
from app.models.schemas import WeatherData

logger = logging.getLogger(__name__)

DWD_WARNINGS_URL = "https://www.dwd.de/DWD/warnungen/warnapp/json/warnings.json"
DWD_OPEN_DATA = "https://opendata.dwd.de"
DWD_MOSMIX_BASE = f"{DWD_OPEN_DATA}/weather/local_forecasts/mos/MOSMIX_L/single_stations"
DWD_RADAR_BASE = f"{DWD_OPEN_DATA}/weather/radar/composite/px250_rw"

REGION_WARNCELL_IDS = [
    "105370000",  # Rhein-Sieg-Kreis
    "105315000",  # Bonn
    "105314000",  # Köln
]


async def collect_dwd_warnings():
    logger.info("Collecting DWD warnings...")
    results = []

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(DWD_WARNINGS_URL, timeout=30)
            resp.raise_for_status()
            text = resp.text

            if text.startswith("warnWetter.loadWarnings("):
                text = text[len("warnWetter.loadWarnings("):-2]

            data = json.loads(text)
            warnings = data.get("warnings", {})

            for warncell_id, warn_list in warnings.items():
                for warning in warn_list:
                    region_name = warning.get("regionName", "")
                    if _is_relevant_region(region_name, warncell_id):
                        result = {
                            "data_type": "warning",
                            "region": region_name,
                            "severity": _map_severity(warning.get("level", 0)),
                            "title": warning.get("headline", ""),
                            "description": warning.get("description", ""),
                            "parameters": {
                                "event": warning.get("event", ""),
                                "level": warning.get("level"),
                                "type": warning.get("type"),
                            },
                            "valid_from": _parse_dwd_time(warning.get("start")),
                            "valid_to": _parse_dwd_time(warning.get("end")),
                            "source": "dwd",
                            "raw_data": warning,
                        }
                        results.append(result)
        except Exception as e:
            logger.error(f"Error fetching DWD warnings: {e}")

    async with async_session() as session:
        for data in results:
            entry = WeatherData(**data)
            session.add(entry)
        await session.commit()

    logger.info(f"Collected {len(results)} DWD warnings")
    return results


async def collect_dwd_forecast():
    logger.info("Collecting DWD MOSMIX forecast...")
    results = []

    async with httpx.AsyncClient() as client:
        try:
            station_id = settings.dwd_station_id
            url = f"{DWD_MOSMIX_BASE}/{station_id}/kml/MOSMIX_L_LATEST_{station_id}.kmz"
            resp = await client.get(url, timeout=60)
            resp.raise_for_status()

            result = {
                "data_type": "forecast",
                "region": settings.city_name,
                "severity": 0,
                "title": f"MOSMIX Vorhersage {settings.city_name}",
                "description": "Punktvorhersage vom DWD",
                "parameters": {"station_id": station_id, "size_bytes": len(resp.content)},
                "valid_from": datetime.utcnow(),
                "source": "dwd_mosmix",
                "raw_data": {"status": "downloaded", "station": station_id},
            }
            results.append(result)
        except Exception as e:
            logger.error(f"Error fetching MOSMIX forecast: {e}")

    async with async_session() as session:
        for data in results:
            entry = WeatherData(**data)
            session.add(entry)
        await session.commit()

    logger.info(f"Collected {len(results)} forecast entries")
    return results


async def collect_radar_data():
    logger.info("Collecting radar data...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{DWD_RADAR_BASE}/", timeout=30)
            resp.raise_for_status()

            result = {
                "data_type": "radar",
                "region": "Deutschland",
                "severity": 0,
                "title": "Radarkomposit",
                "description": "DWD Radarkomposit Niederschlag",
                "parameters": {"type": "px250_rw"},
                "valid_from": datetime.utcnow(),
                "source": "dwd_radar",
            }

            async with async_session() as session:
                entry = WeatherData(**result)
                session.add(entry)
                await session.commit()

            return [result]
        except Exception as e:
            logger.error(f"Error fetching radar data: {e}")
            return []


def _is_relevant_region(region_name: str, warncell_id: str) -> bool:
    relevant_names = [
        "troisdorf", "siegburg", "rhein-sieg", "bonn", "köln",
        "sankt augustin", "lohmar", "niederkassel", "hennef",
    ]
    name_lower = region_name.lower()
    return (
        any(r in name_lower for r in relevant_names)
        or warncell_id in REGION_WARNCELL_IDS
    )


def _map_severity(level: int) -> int:
    mapping = {0: 0, 1: 20, 2: 40, 3: 60, 4: 80, 5: 100}
    return mapping.get(level, level * 20)


def _parse_dwd_time(ms_timestamp) -> Optional[datetime]:
    if ms_timestamp is None:
        return None
    try:
        return datetime.utcfromtimestamp(ms_timestamp / 1000)
    except (ValueError, TypeError, OSError):
        return None
