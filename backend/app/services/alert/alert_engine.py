import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, and_

from app.config import settings
from app.models.database import async_session
from app.models.schemas import (
    Alert, AlertCategory, AlertThreshold, RiskScore,
    WaterLevel, WeatherData, FireRisk, AirQuality, NewsItem,
    OfficialWarning, TrafficEvent,
)

logger = logging.getLogger(__name__)


async def calculate_risk_scores() -> dict:
    scores = {}
    async with async_session() as session:
        scores["water"] = await _calc_water_score(session)
        scores["weather"] = await _calc_weather_score(session)
        scores["fire"] = await _calc_fire_score(session)
        scores["air_quality"] = await _calc_air_quality_score(session)
        scores["traffic"] = await _calc_traffic_score(session)
        scores["official_warning"] = await _calc_warning_score(session)
        scores["news"] = await _calc_news_score(session)

        total = sum(s["score"] * s.get("weight", 1.0) for s in scores.values())
        total_weight = sum(s.get("weight", 1.0) for s in scores.values())
        overall = total / total_weight if total_weight > 0 else 0

        for cat_name, cat_data in scores.items():
            try:
                cat_enum = AlertCategory(cat_name)
            except ValueError:
                continue
            risk = RiskScore(
                category=cat_enum,
                score=cat_data["score"],
                components=cat_data,
            )
            session.add(risk)

        await session.commit()

    scores["overall"] = {"score": min(100, overall), "components": scores}
    return scores


async def check_thresholds_and_alert(scores: dict):
    async with async_session() as session:
        stmt = select(AlertThreshold).where(AlertThreshold.is_enabled == True)
        result = await session.execute(stmt)
        thresholds = result.scalars().all()

        for threshold in thresholds:
            cat = threshold.category.value
            if cat not in scores:
                continue

            current_score = scores[cat]["score"]
            condition = threshold.condition or {}
            min_score = condition.get("min_score", 50)

            if current_score >= min_score:
                existing = await session.execute(
                    select(Alert).where(
                        and_(
                            Alert.category == threshold.category,
                            Alert.is_active == True,
                            Alert.triggered_at > datetime.utcnow() - timedelta(hours=1),
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                alert = Alert(
                    category=threshold.category,
                    score=current_score,
                    title=f"{threshold.name}: Score {current_score:.0f}/100",
                    description=f"Schwellenwert {min_score} überschritten. Aktueller Score: {current_score:.1f}",
                    source_data=scores[cat],
                    threshold_config=threshold.condition,
                    is_active=True,
                    escalation_level=1,
                )
                session.add(alert)
                logger.warning(f"ALERT: {threshold.name} - Score {current_score:.0f}")

        await session.commit()


async def _calc_water_score(session) -> dict:
    cutoff = datetime.utcnow() - timedelta(hours=2)
    stmt = (
        select(WaterLevel)
        .where(WaterLevel.created_at > cutoff)
        .order_by(WaterLevel.created_at.desc())
    )
    result = await session.execute(stmt)
    levels = result.scalars().all()

    if not levels:
        return {"score": 0, "weight": 1.5, "detail": "Keine Daten", "stations": []}

    max_score = 0
    station_data = []
    for level in levels:
        station_score = 0
        if level.trend == "rising":
            station_score += 10

        if level.level_cm and level.river:
            river = level.river.lower()
            if "rhein" in river and level.level_cm > 600:
                station_score += min(60, (level.level_cm - 600) / 5)
            elif "sieg" in river and level.level_cm > 300:
                station_score += min(70, (level.level_cm - 300) / 3)
            elif level.level_cm > 200:
                station_score += min(50, (level.level_cm - 200) / 3)

        max_score = max(max_score, station_score)
        station_data.append({
            "station": level.station_name,
            "level": level.level_cm,
            "trend": level.trend,
            "score": station_score,
        })

    return {"score": min(100, max_score), "weight": 1.5, "detail": "Pegelstände", "stations": station_data}


async def _calc_weather_score(session) -> dict:
    cutoff = datetime.utcnow() - timedelta(hours=6)
    stmt = (
        select(WeatherData)
        .where(and_(WeatherData.data_type == "warning", WeatherData.created_at > cutoff))
        .order_by(WeatherData.severity.desc())
    )
    result = await session.execute(stmt)
    warnings = result.scalars().all()

    if not warnings:
        return {"score": 0, "weight": 1.2, "detail": "Keine Warnungen", "warnings": []}

    max_severity = max(w.severity for w in warnings)
    return {
        "score": min(100, max_severity),
        "weight": 1.2,
        "detail": f"{len(warnings)} Wetterwarnungen",
        "warnings": [{"title": w.title, "severity": w.severity} for w in warnings[:5]],
    }


async def _calc_fire_score(session) -> dict:
    cutoff = datetime.utcnow() - timedelta(hours=12)
    stmt = (
        select(FireRisk)
        .where(FireRisk.created_at > cutoff)
        .order_by(FireRisk.risk_index.desc())
    )
    result = await session.execute(stmt)
    risks = result.scalars().all()

    if not risks:
        return {"score": 0, "weight": 1.0, "detail": "Keine Daten"}

    max_index = max(r.risk_index or 0 for r in risks)
    has_hotspots = any(r.satellite_hotspots for r in risks)

    score = max_index * 20
    if has_hotspots:
        score += 30

    return {
        "score": min(100, score),
        "weight": 1.0,
        "detail": f"Index {max_index}/5" + (" + Hotspots!" if has_hotspots else ""),
    }


async def _calc_air_quality_score(session) -> dict:
    cutoff = datetime.utcnow() - timedelta(hours=3)
    stmt = (
        select(AirQuality)
        .where(AirQuality.created_at > cutoff)
        .order_by(AirQuality.created_at.desc())
    )
    result = await session.execute(stmt)
    readings = result.scalars().all()

    if not readings:
        return {"score": 0, "weight": 0.5, "detail": "Keine Daten"}

    max_aqi = max((r.aqi or 0) for r in readings)
    pm25_max = max((r.pm25 or 0) for r in readings)

    score = 0
    if max_aqi > 100:
        score = min(100, (max_aqi - 100) / 2)
    if pm25_max > 50:
        score = max(score, min(100, (pm25_max - 50) * 2))

    return {"score": score, "weight": 0.5, "detail": f"AQI {max_aqi}"}


async def _calc_traffic_score(session) -> dict:
    cutoff = datetime.utcnow() - timedelta(hours=2)
    stmt = (
        select(TrafficEvent)
        .where(and_(TrafficEvent.is_active == True, TrafficEvent.created_at > cutoff))
    )
    result = await session.execute(stmt)
    events = result.scalars().all()

    if not events:
        return {"score": 0, "weight": 0.8, "detail": "Keine Ereignisse"}

    max_severity = max(e.severity for e in events)
    accident_count = sum(1 for e in events if e.event_type == "accident")

    score = max_severity
    if accident_count > 2:
        score += 20

    return {
        "score": min(100, score),
        "weight": 0.8,
        "detail": f"{len(events)} Ereignisse, {accident_count} Unfälle",
    }


async def _calc_warning_score(session) -> dict:
    stmt = select(OfficialWarning).where(OfficialWarning.is_active == True)
    result = await session.execute(stmt)
    warnings = result.scalars().all()

    if not warnings:
        return {"score": 0, "weight": 2.0, "detail": "Keine Warnungen"}

    severity_map = {"minor": 20, "moderate": 40, "severe": 70, "extreme": 100}
    max_score = 0
    for w in warnings:
        s = severity_map.get(w.severity.lower() if w.severity else "", 30)
        max_score = max(max_score, s)

    return {
        "score": max_score,
        "weight": 2.0,
        "detail": f"{len(warnings)} aktive Warnungen",
    }


async def _calc_news_score(session) -> dict:
    cutoff = datetime.utcnow() - timedelta(hours=6)
    stmt = (
        select(NewsItem)
        .where(and_(NewsItem.is_relevant == True, NewsItem.created_at > cutoff))
        .order_by(NewsItem.relevance_score.desc())
    )
    result = await session.execute(stmt)
    news = result.scalars().all()

    if not news:
        return {"score": 0, "weight": 0.6, "detail": "Keine relevanten Nachrichten"}

    max_relevance = max(n.relevance_score for n in news)
    score = max_relevance * 80

    return {
        "score": min(100, score),
        "weight": 0.6,
        "detail": f"{len(news)} relevante Nachrichten",
    }


async def seed_default_thresholds():
    async with async_session() as session:
        existing = await session.execute(select(func.count(AlertThreshold.id)))
        if existing.scalar() > 0:
            return

        defaults = [
            AlertThreshold(
                category=AlertCategory.WATER,
                name="Hochwasser-Warnung",
                condition={"min_score": 40},
                score_contribution=30,
                notification_channels=["push", "telegram"],
                is_enabled=True,
            ),
            AlertThreshold(
                category=AlertCategory.WEATHER,
                name="Unwetter-Warnung",
                condition={"min_score": 50},
                score_contribution=25,
                notification_channels=["push", "telegram"],
                is_enabled=True,
            ),
            AlertThreshold(
                category=AlertCategory.FIRE,
                name="Waldbrand-Gefahr",
                condition={"min_score": 60},
                score_contribution=25,
                notification_channels=["push", "telegram"],
                is_enabled=True,
            ),
            AlertThreshold(
                category=AlertCategory.OFFICIAL_WARNING,
                name="Behördliche Warnung",
                condition={"min_score": 30},
                score_contribution=30,
                notification_channels=["push", "telegram", "sms"],
                is_enabled=True,
            ),
            AlertThreshold(
                category=AlertCategory.TRAFFIC,
                name="Schwerer Verkehrsunfall",
                condition={"min_score": 70},
                score_contribution=15,
                notification_channels=["push"],
                is_enabled=True,
            ),
        ]
        for t in defaults:
            session.add(t)
        await session.commit()
        logger.info("Seeded default alert thresholds")
