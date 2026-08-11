"""Open-Meteo: aktuelles Wetter, 24h-Vorhersage und 30-Tage-Rückblick.

Der Rückblick liefert Hitze-/Trockenheitsindikatoren (Hitzetage, Trockentage,
längste Trockenphase, Niederschlagssumme), die in die Waldbrand- und
Wetter-Risikobewertung einfließen.
"""
import logging
from datetime import datetime

import httpx

from app.config import settings
from app.models.database import async_session
from app.models.schemas import WeatherData

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

HISTORY_DAYS = 30
HOT_DAY_THRESHOLD = 30.0       # °C Tagesmaximum
VERY_HOT_DAY_THRESHOLD = 35.0  # °C Tagesmaximum
DRY_DAY_THRESHOLD_MM = 1.0     # weniger gilt als Trockentag


async def collect_openmeteo():
    logger.info("Collecting Open-Meteo weather (current + 24h + 30d history)...")

    params = {
        "latitude": settings.center_lat,
        "longitude": settings.center_lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                   "precipitation,weather_code,wind_speed_10m,wind_gusts_10m",
        "hourly": "temperature_2m,precipitation,precipitation_probability,"
                  "weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "past_days": HISTORY_DAYS,
        "forecast_days": 2,
        "timezone": "Europe/Berlin",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(OPEN_METEO_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

    current = data.get("current", {})
    hourly = data.get("hourly", {})
    daily = data.get("daily", {})

    # Nächste 24 Stunden ab jetzt herausschneiden
    now_iso = current.get("time", datetime.utcnow().strftime("%Y-%m-%dT%H:00"))
    times = hourly.get("time", [])
    start = next((i for i, t in enumerate(times) if t >= now_iso), 0)
    hourly_24h = {
        "time": times[start:start + 24],
        "temperature_2m": hourly.get("temperature_2m", [])[start:start + 24],
        "precipitation": hourly.get("precipitation", [])[start:start + 24],
        "precipitation_probability": hourly.get("precipitation_probability", [])[start:start + 24],
        "weather_code": hourly.get("weather_code", [])[start:start + 24],
        "wind_speed_10m": hourly.get("wind_speed_10m", [])[start:start + 24],
    }

    indicators = _compute_climate_indicators(daily)
    indicators.update(_compute_rain_indicators(daily, hourly_24h))

    forecast_row = WeatherData(
        data_type="forecast",
        region=settings.city_name,
        severity=0,
        title=f"Open-Meteo aktuell + 24h ({settings.city_name})",
        parameters={"current": current, "hourly_24h": hourly_24h},
        valid_from=datetime.utcnow(),
        source="open_meteo",
    )
    climate_row = WeatherData(
        data_type="climate_30d",
        region=settings.city_name,
        severity=indicators["heat_drought_level"],
        title=f"30-Tage-Rückblick ({settings.city_name})",
        description=indicators["summary"],
        parameters=indicators,
        valid_from=datetime.utcnow(),
        source="open_meteo",
        raw_data={
            "time": daily.get("time", [])[:HISTORY_DAYS],
            "temperature_2m_max": daily.get("temperature_2m_max", [])[:HISTORY_DAYS],
            "precipitation_sum": daily.get("precipitation_sum", [])[:HISTORY_DAYS],
        },
    )

    async with async_session() as session:
        session.add(forecast_row)
        session.add(climate_row)
        await session.commit()

    logger.info(
        f"Open-Meteo collected: {current.get('temperature_2m')}°C aktuell, "
        f"30d: {indicators['hot_days']} Hitzetage, {indicators['dry_days']} Trockentage, "
        f"{indicators['rain_sum_mm']}mm Regen"
    )
    return indicators


def _compute_rain_indicators(daily: dict, hourly_24h: dict) -> dict:
    """Regen als Überflutungs-Indikator: erwartete 24h-Menge und jüngster Rückblick."""
    fc_rain = [r for r in hourly_24h.get("precipitation", []) if r is not None]
    rain_next_24h = round(sum(fc_rain), 1)
    max_hourly = round(max(fc_rain), 1) if fc_rain else 0.0

    past_rain = [r for r in daily.get("precipitation_sum", [])[:HISTORY_DAYS] if r is not None]
    rain_last_24h = round(past_rain[-1], 1) if past_rain else 0.0
    rain_last_72h = round(sum(past_rain[-3:]), 1) if past_rain else 0.0

    return {
        "rain_next_24h_mm": rain_next_24h,
        "max_hourly_rain_mm": max_hourly,
        "rain_last_24h_mm": rain_last_24h,
        "rain_last_72h_mm": rain_last_72h,
    }


def _compute_climate_indicators(daily: dict) -> dict:
    tmax = [t for t in daily.get("temperature_2m_max", [])[:HISTORY_DAYS] if t is not None]
    rain = [r for r in daily.get("precipitation_sum", [])[:HISTORY_DAYS] if r is not None]

    hot_days = sum(1 for t in tmax if t >= HOT_DAY_THRESHOLD)
    very_hot_days = sum(1 for t in tmax if t >= VERY_HOT_DAY_THRESHOLD)
    dry_days = sum(1 for r in rain if r < DRY_DAY_THRESHOLD_MM)
    rain_sum = round(sum(rain), 1)

    # Längste zusammenhängende Trockenphase
    max_dry_streak = streak = 0
    for r in rain:
        streak = streak + 1 if r < DRY_DAY_THRESHOLD_MM else 0
        max_dry_streak = max(max_dry_streak, streak)

    # Längste zusammenhängende Hitzephase (Tmax >= 30)
    max_heat_streak = streak = 0
    for t in tmax:
        streak = streak + 1 if t >= HOT_DAY_THRESHOLD else 0
        max_heat_streak = max(max_heat_streak, streak)

    # Gesamteinstufung 0-4 (fließt als Boost in Waldbrand/Wetter ein)
    level = 0
    if hot_days >= 5 or max_dry_streak >= 7:
        level = 1
    if hot_days >= 10 or (dry_days >= 20 and rain_sum < 30):
        level = 2
    if hot_days >= 15 or (dry_days >= 24 and rain_sum < 20):
        level = 3
    if (hot_days >= 20 and rain_sum < 20) or (very_hot_days >= 5 and dry_days >= 25):
        level = 4

    level_labels = ["unauffällig", "leicht erhöht", "erhöht", "hoch", "extrem"]
    summary = (
        f"Letzte 30 Tage: {hot_days} Hitzetage (≥30°C), davon {very_hot_days} sehr heiß (≥35°C), "
        f"{dry_days} Trockentage, längste Trockenphase {max_dry_streak} Tage, "
        f"nur {rain_sum} mm Niederschlag. Hitze-/Dürre-Indikator: {level_labels[level]}."
    )

    return {
        "hot_days": hot_days,
        "very_hot_days": very_hot_days,
        "dry_days": dry_days,
        "max_dry_streak": max_dry_streak,
        "max_heat_streak": max_heat_streak,
        "rain_sum_mm": rain_sum,
        "avg_tmax": round(sum(tmax) / len(tmax), 1) if tmax else None,
        "heat_drought_level": level,
        "heat_drought_label": level_labels[level],
        "summary": summary,
        "days_analyzed": len(tmax),
    }
