import logging
from datetime import datetime

import httpx

from app.models.database import async_session
from app.models.schemas import DroughtData

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

TROISDORF_LAT = 50.8159
TROISDORF_LON = 7.1533

DROUGHT_CLASSES = [
    (0.05, "D4", "Ausnahmedürre"),
    (0.10, "D3", "Extreme Dürre"),
    (0.20, "D2", "Schwere Dürre"),
    (0.30, "D1", "Moderate Dürre"),
    (0.40, "D0", "Abnormale Trockenheit"),
]

REQUEST_TIMEOUT = 30


async def collect_drought_data():
    logger.info("Collecting drought/soil moisture data...")
    results = []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            params = {
                "latitude": TROISDORF_LAT,
                "longitude": TROISDORF_LON,
                "hourly": "soil_moisture_0_to_1cm,soil_moisture_1_to_3cm,soil_moisture_3_to_9cm,soil_moisture_9_to_27cm,soil_moisture_27_to_81cm",
                "timezone": "Europe/Berlin",
                "forecast_days": 1,
            }
            resp = await client.get(OPEN_METEO_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

            hourly = data.get("hourly", {})
            times = hourly.get("time", [])

            sm_0_1 = hourly.get("soil_moisture_0_to_1cm", [])
            sm_1_3 = hourly.get("soil_moisture_1_to_3cm", [])
            sm_3_9 = hourly.get("soil_moisture_3_to_9cm", [])
            sm_9_27 = hourly.get("soil_moisture_9_to_27cm", [])
            sm_27_81 = hourly.get("soil_moisture_27_to_81cm", [])

            if not times:
                logger.warning("No soil moisture data returned")
                return results

            latest_idx = len(times) - 1
            for i in range(len(times) - 1, -1, -1):
                vals = [
                    sm_0_1[i] if i < len(sm_0_1) else None,
                    sm_1_3[i] if i < len(sm_1_3) else None,
                    sm_3_9[i] if i < len(sm_3_9) else None,
                ]
                if any(v is not None for v in vals):
                    latest_idx = i
                    break

            topsoil_values = [
                v for v in [
                    sm_0_1[latest_idx] if latest_idx < len(sm_0_1) else None,
                    sm_1_3[latest_idx] if latest_idx < len(sm_1_3) else None,
                    sm_3_9[latest_idx] if latest_idx < len(sm_3_9) else None,
                ] if v is not None
            ]
            deep_values = [
                v for v in [
                    sm_9_27[latest_idx] if latest_idx < len(sm_9_27) else None,
                    sm_27_81[latest_idx] if latest_idx < len(sm_27_81) else None,
                ] if v is not None
            ]

            topsoil = sum(topsoil_values) / len(topsoil_values) if topsoil_values else None
            deep = sum(deep_values) / len(deep_values) if deep_values else None

            smi = topsoil if topsoil is not None else deep
            drought_class = _classify_drought(smi) if smi is not None else None

            timestamp_str = times[latest_idx]
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
            except ValueError:
                timestamp = datetime.utcnow()

            result = {
                "region": "Troisdorf",
                "soil_moisture_index": round(smi, 4) if smi is not None else None,
                "drought_class": drought_class,
                "topsoil_moisture": round(topsoil, 4) if topsoil is not None else None,
                "deep_soil_moisture": round(deep, 4) if deep is not None else None,
                "timestamp": timestamp,
                "source": "open_meteo",
                "raw_data": {
                    "time": timestamp_str,
                    "sm_0_1": sm_0_1[latest_idx] if latest_idx < len(sm_0_1) else None,
                    "sm_1_3": sm_1_3[latest_idx] if latest_idx < len(sm_1_3) else None,
                    "sm_3_9": sm_3_9[latest_idx] if latest_idx < len(sm_3_9) else None,
                    "sm_9_27": sm_9_27[latest_idx] if latest_idx < len(sm_9_27) else None,
                    "sm_27_81": sm_27_81[latest_idx] if latest_idx < len(sm_27_81) else None,
                },
            }
            results.append(result)

            if drought_class and drought_class.startswith("D") and drought_class[1:].isdigit():
                level = int(drought_class[1])
                if level >= 2:
                    logger.warning(
                        f"DROUGHT: {drought_class} - Soil moisture index {smi:.4f} "
                        f"(topsoil: {topsoil}, deep: {deep})"
                    )

        except Exception as e:
            logger.error(f"Error fetching drought data: {e}")

    async with async_session() as session:
        for data in results:
            entry = DroughtData(**data)
            session.add(entry)
        await session.commit()

    logger.info(f"Collected {len(results)} drought readings")
    return results


def _classify_drought(smi: float) -> str | None:
    for threshold, cls, _ in DROUGHT_CLASSES:
        if smi <= threshold:
            return cls
    return None
