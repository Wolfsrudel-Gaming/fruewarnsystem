import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, and_

from app.config import settings
from app.models.database import async_session
from app.models.schemas import (
    Alert, AlertCategory, AlertThreshold, RiskScore,
    WaterLevel, WeatherData, FireRisk, AirQuality, NewsItem,
    OfficialWarning, TrafficEvent, EarthquakeEvent, RadiationReading,
    ICUCapacity, GridStatus, RiverShippingWarning, EventCalendar,
)

logger = logging.getLogger(__name__)


def _escalation_level_for_score(score: float) -> int:
    """Push >=1, Telegram >=2, SMS >=3, Voice/Email >=4 (siehe notifier)."""
    if score >= 85:
        return 4
    if score >= 75:
        return 3
    if score >= 60:
        return 2
    return 1


def _contrib(source: str, source_type: str, value, points: float, reason: str, ts=None) -> dict:
    entry = {
        "source": source,
        "source_type": source_type,
        "value": value,
        "points": round(points, 1),
        "reason": reason,
    }
    if ts:
        entry["timestamp"] = ts.isoformat() if isinstance(ts, datetime) else str(ts)
    return entry


async def calculate_risk_scores() -> dict:
    scores = {}
    async with async_session() as session:
        scores["water"] = await _calc_water_score(session)
        scores["weather"] = await _calc_weather_score(session)
        scores["fire"] = await _calc_fire_score(session, drought_indicator=scores["water"].get("drought_indicator", 0))
        scores["air_quality"] = await _calc_air_quality_score(session)
        scores["traffic"] = await _calc_traffic_score(session)
        scores["official_warning"] = await _calc_warning_score(session)
        scores["news"] = await _calc_news_score(session)
        scores["seismic"] = await _calc_seismic_score(session)
        scores["radiation"] = await _calc_radiation_score(session)
        scores["health"] = await _calc_health_score(session)
        scores["power"] = await _calc_power_score(session)
        scores["events"] = await _calc_events_score(session)
        scores["shipping"] = await _calc_shipping_score(session)

        total = sum(s["score"] * s.get("weight", 1.0) for s in scores.values())
        total_weight = sum(s.get("weight", 1.0) for s in scores.values())
        overall = total / total_weight if total_weight > 0 else 0

        overall_contributions = []
        for cat_name, cat_data in scores.items():
            w = cat_data.get("weight", 1.0)
            overall_contributions.append(_contrib(
                source=cat_name,
                source_type="category_score",
                value=cat_data["score"],
                points=cat_data["score"] * w / total_weight if total_weight > 0 else 0,
                reason=f"{cat_data['detail']} (Gewicht {w}x)",
            ))
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

    scores["overall"] = {
        "score": min(100, overall),
        "contributions": overall_contributions,
    }
    return scores


async def check_thresholds_and_alert(scores: dict):
    new_alerts = []
    async with async_session() as session:
        stmt = select(AlertThreshold).where(AlertThreshold.is_enabled == True)
        result = await session.execute(stmt)
        thresholds = result.scalars().all()

        for threshold in thresholds:
            cat = threshold.category.value
            if cat not in scores:
                continue

            score_data = scores[cat]
            current_score = score_data["score"]
            condition = threshold.condition or {}
            min_score = condition.get("min_score", 50)

            required_type = condition.get("type")
            if required_type:
                actual_condition = score_data.get("primary_condition", "")
                if required_type != actual_condition:
                    continue

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
                    escalation_level=_escalation_level_for_score(current_score),
                )
                session.add(alert)
                new_alerts.append(alert)
                logger.warning(f"ALERT: {threshold.name} - Score {current_score:.0f}")

        await session.commit()

    # Nach dem Commit: Kanäle benachrichtigen + WebSocket-Clients (App!) informieren.
    # Fehler hier dürfen den Collector-Lauf nicht abbrechen.
    for alert in new_alerts:
        try:
            from app.services.notification.notifier import send_alert_notifications
            sent = await send_alert_notifications(alert)
            logger.info(f"Alert {alert.id}: Benachrichtigungen gesendet via {sent or 'keine Kanäle'}")
        except Exception as e:
            logger.error(f"Alert {alert.id}: Benachrichtigung fehlgeschlagen: {e}")

        try:
            from app.api.websocket.manager import ws_manager
            await ws_manager.broadcast({
                "type": "alert",
                "alert": {
                    "id": alert.id,
                    "category": alert.category.value,
                    "score": alert.score,
                    "title": alert.title,
                    "description": alert.description,
                    "escalation_level": alert.escalation_level,
                    "acknowledged": alert.acknowledged or False,
                    "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
                },
            })
        except Exception as e:
            logger.error(f"Alert {alert.id}: WebSocket-Broadcast fehlgeschlagen: {e}")


async def _calc_water_score(session) -> dict:
    from app.collectors.water.pegel_collector import classify_water_level

    cutoff = datetime.utcnow() - timedelta(hours=2)
    stmt = (
        select(WaterLevel)
        .where(WaterLevel.created_at > cutoff)
        .order_by(WaterLevel.created_at.desc())
    )
    result = await session.execute(stmt)
    levels = result.scalars().all()

    if not levels:
        return {"score": 0, "weight": 1.5, "detail": "Keine Daten", "stations": [],
                "contributions": [], "drought_indicator": 0}

    max_score = 0
    drought_indicator = 0
    low_water_stations = 0
    station_data = []
    contributions = []

    for level in levels:
        station_score = 0
        classification = classify_water_level(level.level_cm, level.river or "")
        condition = classification["condition"]
        reasons = []

        if condition == "extremhochwasser":
            station_score = 100
            reasons.append(f"Extremhochwasser bei {level.level_cm} cm")
        elif condition == "starkes_hochwasser":
            station_score = 70 + min(30, classification["deviation"] * 20)
            reasons.append(f"Starkes Hochwasser bei {level.level_cm} cm")
        elif condition == "hochwasser":
            station_score = 40 + min(30, classification["deviation"] * 30)
            reasons.append(f"Hochwasser bei {level.level_cm} cm")
            if level.trend == "rising":
                station_score += 15
                reasons.append("steigender Trend (+15)")
        elif condition == "drought":
            station_score = 60 + min(40, classification["deviation"] * 40)
            drought_indicator = max(drought_indicator, 1.0)
            low_water_stations += 1
            reasons.append(f"Extrem-Niedrigwasser bei {level.level_cm} cm - Dürre")
        elif condition == "niedrigwasser":
            station_score = 30 + min(30, classification["deviation"] * 30)
            drought_indicator = max(drought_indicator, 0.6)
            low_water_stations += 1
            reasons.append(f"Niedrigwasser bei {level.level_cm} cm")
        elif condition == "unterdurchschnittlich":
            drought_indicator = max(drought_indicator, 0.2)
            reasons.append(f"Unterdurchschnittlich bei {level.level_cm} cm")
        else:
            if level.trend == "rising":
                station_score += 10
                reasons.append(f"Normalpegel {level.level_cm} cm, steigend (+10)")

        if station_score > 0:
            contributions.append(_contrib(
                source=f"Pegelonline - {level.station_name or level.station_id}",
                source_type="pegel",
                value=f"{level.level_cm} cm ({level.river})",
                points=station_score,
                reason="; ".join(reasons),
                ts=level.timestamp,
            ))

        max_score = max(max_score, station_score)
        station_data.append({
            "station": level.station_name,
            "river": level.river,
            "level": level.level_cm,
            "trend": level.trend,
            "condition": condition,
            "warning_level": classification["warning_level"],
            "score": station_score,
        })

    if low_water_stations > 1:
        drought_indicator = min(1.0, drought_indicator * 1.2)
        contributions.append(_contrib(
            source="Querauswertung Niedrigwasser",
            source_type="cross_analysis",
            value=f"{low_water_stations} Stationen",
            points=0,
            reason=f"Dürreindikator um 20% erhöht wegen {low_water_stations} betroffener Stationen",
        ))

    high_water_score = 0
    low_water_score = 0
    for sd in station_data:
        cond = sd.get("condition", "")
        s = sd.get("score", 0)
        if cond in ("extremhochwasser", "starkes_hochwasser", "hochwasser"):
            high_water_score = max(high_water_score, s)
        elif cond in ("drought", "niedrigwasser", "unterdurchschnittlich"):
            low_water_score = max(low_water_score, s)

    if high_water_score >= low_water_score and high_water_score > 0:
        primary_condition = "high_water"
    elif low_water_score > 0:
        primary_condition = "low_water"
    else:
        primary_condition = "normal"

    # Regen-Querauswertung: erwarteter Starkregen ist ein Überflutungsindikator,
    # besonders wenn er auf bereits erhöhte Pegel oder gesättigte Böden trifft.
    climate = await _get_climate_30d(session)
    rain_next_24h = climate.get("rain_next_24h_mm", 0) or 0
    rain_last_72h = climate.get("rain_last_72h_mm", 0) or 0
    flood_points = 0
    flood_reasons = []
    if rain_next_24h >= 40:
        flood_points = 30
        flood_reasons.append(f"Starkregen erwartet ({rain_next_24h} mm/24h)")
    elif rain_next_24h >= 20:
        flood_points = 18
        flood_reasons.append(f"Ergiebiger Regen erwartet ({rain_next_24h} mm/24h)")
    elif rain_next_24h >= 10:
        flood_points = 8
        flood_reasons.append(f"Regen erwartet ({rain_next_24h} mm/24h)")
    if rain_last_72h >= 50:
        flood_points += 15
        flood_reasons.append(f"Böden gesättigt ({rain_last_72h} mm in 72h)")
    if flood_points > 0 and primary_condition == "high_water":
        flood_points = round(flood_points * 1.5)
        flood_reasons.append("trifft auf bereits erhöhte Pegel (x1,5)")
    if flood_points > 0:
        contributions.append(_contrib(
            source="Open-Meteo Regenprognose (Querauswertung)",
            source_type="cross_analysis",
            value=f"{rain_next_24h} mm/24h erwartet, {rain_last_72h} mm/72h gefallen",
            points=flood_points,
            reason="; ".join(flood_reasons),
        ))

    detail = "Pegelstände normal"
    if primary_condition == "low_water":
        if drought_indicator >= 0.6:
            detail = f"Niedrigwasser an {low_water_stations} Stationen - Dürregefahr"
        elif drought_indicator > 0:
            detail = "Pegelstände unterdurchschnittlich"
        else:
            detail = "Niedrigwasser"
    elif primary_condition == "high_water":
        detail = "Hochwasser"
    if flood_points > 0:
        detail += f" + Regenprognose {rain_next_24h} mm/24h"

    return {
        "score": min(100, max_score + flood_points),
        "weight": 1.5,
        "detail": detail,
        "stations": station_data,
        "contributions": contributions,
        "drought_indicator": drought_indicator,
        "low_water_stations": low_water_stations,
        "primary_condition": primary_condition,
        "high_water_score": high_water_score,
        "low_water_score": low_water_score,
        "flood_rain_boost": flood_points,
        "rain_next_24h_mm": rain_next_24h,
    }


async def _get_climate_30d(session) -> dict:
    """Neuester 30-Tage-Hitze/Trockenheits-Indikator (Open-Meteo), max. 24h alt."""
    cutoff = datetime.utcnow() - timedelta(hours=24)
    stmt = (
        select(WeatherData)
        .where(and_(WeatherData.data_type == "climate_30d", WeatherData.created_at > cutoff))
        .order_by(WeatherData.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalars().first()
    return row.parameters if row and row.parameters else {}


async def _calc_weather_score(session) -> dict:
    cutoff = datetime.utcnow() - timedelta(hours=6)
    stmt = (
        select(WeatherData)
        .where(and_(WeatherData.data_type == "warning", WeatherData.created_at > cutoff))
        .order_by(WeatherData.severity.desc())
    )
    result = await session.execute(stmt)
    warnings = result.scalars().all()

    climate = await _get_climate_30d(session)
    heat_level = climate.get("heat_drought_level", 0)
    heat_points = heat_level * 10  # 0-40

    contributions = []
    score = 0

    if warnings:
        max_severity = max(w.severity for w in warnings)
        score = max_severity
        for w in warnings:
            contributions.append(_contrib(
                source=f"DWD - {w.region or 'Unbekannt'}",
                source_type="dwd_warning",
                value=f"Severity {w.severity}",
                points=w.severity,
                reason=w.title or "Wetterwarnung",
                ts=w.created_at,
            ))

    if heat_points > 0:
        score += heat_points
        contributions.append(_contrib(
            source="Open-Meteo 30-Tage-Rückblick",
            source_type="climate_30d",
            value=f"{climate.get('hot_days', 0)} Hitzetage, {climate.get('rain_sum_mm', '?')} mm Regen/30d",
            points=heat_points,
            reason=climate.get("summary", "Anhaltende Hitze/Trockenheit der letzten 30 Tage"),
        ))

    details = []
    if warnings:
        details.append(f"{len(warnings)} Wetterwarnungen")
    else:
        details.append("Keine Warnungen")
    if heat_level > 0:
        details.append(f"30 Tage: {climate.get('heat_drought_label', '')} "
                       f"({climate.get('hot_days', 0)} Hitzetage)")

    return {
        "score": min(100, score),
        "weight": 1.2,
        "detail": " · ".join(details),
        "warnings": [{"title": w.title, "severity": w.severity} for w in warnings[:5]],
        "climate_30d": climate,
        "contributions": contributions,
    }


async def _calc_fire_score(session, drought_indicator: float = 0) -> dict:
    cutoff = datetime.utcnow() - timedelta(hours=12)
    stmt = (
        select(FireRisk)
        .where(FireRisk.created_at > cutoff)
        .order_by(FireRisk.risk_index.desc())
    )
    result = await session.execute(stmt)
    risks = result.scalars().all()

    if not risks and drought_indicator == 0:
        return {"score": 0, "weight": 1.0, "detail": "Keine Daten",
                "contributions": [], "drought_boost": 0}

    max_index = max((r.risk_index or 0 for r in risks), default=0)
    has_hotspots = any(r.satellite_hotspots for r in risks)
    contributions = []

    score = max_index * 20
    if max_index > 0:
        contributions.append(_contrib(
            source="DWD Waldbrandgefahrenindex",
            source_type="dwd_fire_index",
            value=f"Stufe {max_index}/5",
            points=max_index * 20,
            reason=f"Waldbrandgefahrenindex {max_index} von 5",
        ))

    if has_hotspots:
        score += 30
        hotspot_regions = [r.region for r in risks if r.satellite_hotspots]
        contributions.append(_contrib(
            source="NASA FIRMS Satellitendaten",
            source_type="satellite",
            value=f"Hotspots in {', '.join(hotspot_regions[:3])}",
            points=30,
            reason="Aktive Hitze-Anomalien per Satellit erkannt",
        ))

    drought_boost = 0
    if drought_indicator > 0:
        drought_boost = drought_indicator * 25
        score += drought_boost
        contributions.append(_contrib(
            source="Pegelstände (Querauswertung)",
            source_type="cross_analysis",
            value=f"Dürreindikator {drought_indicator:.1f}",
            points=drought_boost,
            reason="Niedrige Pegelstände deuten auf Dürre hin → erhöhte Waldbrandgefahr",
        ))

    climate = await _get_climate_30d(session)
    heat_level = climate.get("heat_drought_level", 0)
    heat_boost = heat_level * 7  # 0-28
    if heat_boost > 0:
        score += heat_boost
        contributions.append(_contrib(
            source="Open-Meteo 30-Tage-Rückblick",
            source_type="climate_30d",
            value=(f"{climate.get('hot_days', 0)} Hitzetage, "
                   f"{climate.get('max_dry_streak', 0)} Tage Trockenphase"),
            points=heat_boost,
            reason=climate.get("summary", "Anhaltende Hitze/Trockenheit erhöht die Waldbrandgefahr"),
        ))

    details = []
    if max_index > 0:
        details.append(f"Index {max_index}/5")
    if has_hotspots:
        details.append("Hotspots!")
    if drought_indicator >= 0.6:
        details.append("Niedrigwasser/Dürre erhöht Risiko")
    elif drought_indicator > 0:
        details.append("Trockene Bedingungen")
    if heat_level >= 2:
        details.append(f"30-Tage-Hitze: {climate.get('heat_drought_label', '')}")

    return {
        "score": min(100, score),
        "weight": 1.0,
        "detail": " + ".join(details) if details else "Keine Daten",
        "contributions": contributions,
        "drought_boost": drought_boost,
        "drought_indicator": drought_indicator,
        "heat_boost": heat_boost,
        "climate_30d": climate,
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
        return {"score": 0, "weight": 0.5, "detail": "Keine Daten", "contributions": []}

    max_aqi = max((r.aqi or 0) for r in readings)
    pm25_max = max((r.pm25 or 0) for r in readings)
    contributions = []

    score = 0
    if max_aqi > 100:
        aqi_score = min(100, (max_aqi - 100) / 2)
        score = aqi_score
        worst = max(readings, key=lambda r: r.aqi or 0)
        contributions.append(_contrib(
            source=f"{worst.source or 'Unbekannt'} - {worst.station_name or worst.station_id}",
            source_type="air_quality",
            value=f"AQI {max_aqi}",
            points=aqi_score,
            reason=f"AQI über 100 (Schwellenwert für ungesunde Luft)",
            ts=worst.timestamp,
        ))

    if pm25_max > 50:
        pm_score = min(100, (pm25_max - 50) * 2)
        if pm_score > score:
            score = pm_score
        worst_pm = max(readings, key=lambda r: r.pm25 or 0)
        contributions.append(_contrib(
            source=f"{worst_pm.source or 'Unbekannt'} - {worst_pm.station_name or worst_pm.station_id}",
            source_type="air_quality",
            value=f"PM2.5: {pm25_max} µg/m³",
            points=pm_score,
            reason=f"Feinstaub PM2.5 über 50 µg/m³",
            ts=worst_pm.timestamp,
        ))

    return {"score": score, "weight": 0.5, "detail": f"AQI {max_aqi}", "contributions": contributions}


async def _calc_traffic_score(session) -> dict:
    cutoff = datetime.utcnow() - timedelta(hours=2)
    stmt = (
        select(TrafficEvent)
        .where(and_(TrafficEvent.is_active == True, TrafficEvent.created_at > cutoff))
    )
    result = await session.execute(stmt)
    events = result.scalars().all()

    if not events:
        return {"score": 0, "weight": 0.8, "detail": "Keine Ereignisse", "contributions": []}

    max_severity = max(e.severity for e in events)
    accident_count = sum(1 for e in events if e.event_type == "accident")
    contributions = []

    for e in sorted(events, key=lambda x: x.severity, reverse=True)[:10]:
        contributions.append(_contrib(
            source=f"Autobahn-API - {e.road or 'Unbekannt'}",
            source_type="traffic",
            value=f"{e.event_type} (Severity {e.severity})",
            points=e.severity,
            reason=e.title or f"{e.event_type} auf {e.road}",
            ts=e.started_at or e.created_at,
        ))

    score = max_severity
    if accident_count > 2:
        score += 20
        contributions.append(_contrib(
            source="Querauswertung Unfälle",
            source_type="cross_analysis",
            value=f"{accident_count} Unfälle",
            points=20,
            reason=f"Mehr als 2 aktive Unfälle gleichzeitig (+20)",
        ))

    return {
        "score": min(100, score),
        "weight": 0.8,
        "detail": f"{len(events)} Ereignisse, {accident_count} Unfälle",
        "contributions": contributions,
    }


async def _calc_warning_score(session) -> dict:
    stmt = select(OfficialWarning).where(OfficialWarning.is_active == True)
    result = await session.execute(stmt)
    warnings = result.scalars().all()

    if not warnings:
        return {"score": 0, "weight": 2.0, "detail": "Keine Warnungen", "contributions": []}

    severity_map = {"minor": 20, "moderate": 40, "severe": 70, "extreme": 100}
    max_score = 0
    contributions = []

    for w in warnings:
        s = severity_map.get(w.severity.lower() if w.severity else "", 30)
        max_score = max(max_score, s)
        contributions.append(_contrib(
            source=f"{w.source_system or 'NINA'} - {w.area_description or 'Unbekannt'}",
            source_type="official_warning",
            value=f"Severity: {w.severity}",
            points=s,
            reason=w.headline or "Behördliche Warnung",
            ts=w.effective,
        ))

    return {
        "score": max_score,
        "weight": 2.0,
        "detail": f"{len(warnings)} aktive Warnungen",
        "contributions": contributions,
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
        return {"score": 0, "weight": 0.6, "detail": "Keine relevanten Nachrichten", "contributions": []}

    max_relevance = max(n.relevance_score for n in news)
    score = max_relevance * 80
    contributions = []

    for n in news[:10]:
        ai = n.ai_analysis or {}
        article_points = n.relevance_score * 80
        reason_parts = []
        if ai.get("category"):
            reason_parts.append(f"Kategorie: {ai['category']}")
        if ai.get("escalation_potential") and ai["escalation_potential"] != "none":
            reason_parts.append(f"Eskalation: {ai['escalation_potential']}")
        if ai.get("drk_relevance"):
            reason_parts.append(ai["drk_relevance"][:120])

        method = "LLM+Keyword" if ai else "Keyword"
        contributions.append(_contrib(
            source=f"{n.source or 'Unbekannt'} ({method})",
            source_type="news_rss",
            value=f"Score {n.relevance_score:.2f}",
            points=article_points,
            reason="; ".join(reason_parts) if reason_parts else n.title[:100],
            ts=n.published_at or n.created_at,
        ))

    return {
        "score": min(100, score),
        "weight": 0.6,
        "detail": f"{len(news)} relevante Nachrichten",
        "contributions": contributions,
    }


async def _calc_seismic_score(session) -> dict:
    cutoff = datetime.utcnow() - timedelta(hours=24)
    stmt = (
        select(EarthquakeEvent)
        .where(EarthquakeEvent.created_at > cutoff)
        .order_by(EarthquakeEvent.created_at.desc())
    )
    result = await session.execute(stmt)
    events = result.scalars().all()

    if not events:
        return {"score": 0, "weight": 0.8, "detail": "Keine Erdbeben", "contributions": []}

    max_mag = max((e.magnitude or 0) for e in events)
    contributions = []

    for e in events:
        mag = e.magnitude or 0
        if mag < 2.0:
            continue
        score = 0
        if mag >= 5.0:
            score = 100
        elif mag >= 4.0:
            score = 70
        elif mag >= 3.0:
            score = 40
        elif mag >= 2.5:
            score = 15
        else:
            score = 5

        contributions.append(_contrib(
            source=f"{e.source} - {e.location or 'Unbekannt'}",
            source_type="seismic",
            value=f"M{mag:.1f} (Tiefe: {e.depth_km} km)",
            points=score,
            reason=f"Erdbeben M{mag:.1f} bei {e.location}",
            ts=e.event_time,
        ))

    best = max((c["points"] for c in contributions), default=0)
    return {
        "score": min(100, best),
        "weight": 0.8,
        "detail": f"{len(events)} Erdbeben, max M{max_mag:.1f}" if max_mag > 0 else "Keine relevanten Erdbeben",
        "contributions": contributions,
    }


async def _calc_radiation_score(session) -> dict:
    cutoff = datetime.utcnow() - timedelta(hours=6)
    stmt = (
        select(RadiationReading)
        .where(RadiationReading.created_at > cutoff)
        .order_by(RadiationReading.created_at.desc())
    )
    result = await session.execute(stmt)
    readings = result.scalars().all()

    if not readings:
        return {"score": 0, "weight": 1.0, "detail": "Keine Daten", "contributions": []}

    elevated = [r for r in readings if r.is_elevated]
    max_dose = max((r.gamma_dose_rate or 0) for r in readings)
    contributions = []

    for r in elevated:
        dose = r.gamma_dose_rate or 0
        score = min(100, (dose - 300) / 7)
        contributions.append(_contrib(
            source=f"BfS ODL - {r.station_name or r.station_id}",
            source_type="radiation",
            value=f"{dose:.0f} nSv/h",
            points=score,
            reason=f"Erhöhte Gamma-Dosisleistung (Schwelle: 300 nSv/h)",
            ts=r.timestamp,
        ))

    best = max((c["points"] for c in contributions), default=0)
    return {
        "score": min(100, best),
        "weight": 1.0,
        "detail": f"Max {max_dose:.0f} nSv/h, {len(elevated)} erhöht" if elevated else f"Normal ({max_dose:.0f} nSv/h)",
        "contributions": contributions,
    }


async def _calc_health_score(session) -> dict:
    cutoff = datetime.utcnow() - timedelta(hours=24)
    stmt = (
        select(ICUCapacity)
        .where(ICUCapacity.created_at > cutoff)
        .order_by(ICUCapacity.created_at.desc())
    )
    result = await session.execute(stmt)
    readings = result.scalars().all()

    if not readings:
        return {"score": 0, "weight": 0.5, "detail": "Keine Daten", "contributions": []}

    seen_regions = set()
    latest = []
    for r in readings:
        if r.region_id not in seen_regions:
            seen_regions.add(r.region_id)
            latest.append(r)

    max_occupancy = max((r.occupancy_rate or 0) for r in latest)
    contributions = []

    for r in latest:
        occ = r.occupancy_rate or 0
        if occ < 0.8:
            continue
        score = min(100, (occ - 0.8) * 500)
        contributions.append(_contrib(
            source=f"DIVI - {r.region_name or r.region_id}",
            source_type="icu",
            value=f"{occ:.0%} belegt ({r.beds_free} frei)",
            points=score,
            reason=f"ICU-Auslastung über 80%",
            ts=r.timestamp,
        ))

    best = max((c["points"] for c in contributions), default=0)
    return {
        "score": min(100, best),
        "weight": 0.5,
        "detail": f"Max. ICU-Auslastung {max_occupancy:.0%}",
        "contributions": contributions,
    }


async def _calc_power_score(session) -> dict:
    cutoff = datetime.utcnow() - timedelta(hours=6)
    stmt = (
        select(GridStatus)
        .where(GridStatus.created_at > cutoff)
        .order_by(GridStatus.created_at.desc())
        .limit(5)
    )
    result = await session.execute(stmt)
    readings = result.scalars().all()

    if not readings:
        return {"score": 0, "weight": 0.7, "detail": "Keine Daten", "contributions": []}

    contributions = []
    stressed = [r for r in readings if r.is_stressed]

    for r in stressed:
        balance = r.balance_mw or 0
        score = 0
        if balance < -5000:
            score = 90
        elif balance < -1000:
            score = 60
        elif balance < 0:
            score = 30
        else:
            score = 15

        contributions.append(_contrib(
            source=f"SMARD Bundesnetzagentur - {r.region}",
            source_type="grid",
            value=f"Balance {balance:.0f} MW",
            points=score,
            reason=r.stress_indicator or "Netzbelastung",
            ts=r.timestamp,
        ))

    best = max((c["points"] for c in contributions), default=0)
    latest = readings[0]
    detail = f"Balance {latest.balance_mw:.0f} MW" if latest.balance_mw else "Keine Belastung"
    if stressed:
        detail = f"Netzstress: {len(stressed)} Meldungen"

    return {
        "score": min(100, best),
        "weight": 0.7,
        "detail": detail,
        "contributions": contributions,
    }


async def _calc_events_score(session) -> dict:
    cutoff = datetime.utcnow() - timedelta(hours=48)
    stmt = (
        select(EventCalendar)
        .where(EventCalendar.created_at > cutoff)
        .order_by(EventCalendar.risk_score.desc())
    )
    result = await session.execute(stmt)
    events = result.scalars().all()

    if not events:
        return {"score": 0, "weight": 0.4, "detail": "Keine Veranstaltungen", "contributions": []}

    high_risk = [e for e in events if (e.risk_score or 0) >= 0.5]
    contributions = []

    for e in high_risk[:10]:
        score = (e.risk_score or 0) * 80
        contributions.append(_contrib(
            source=f"{e.source or 'Unbekannt'} - {e.location or ''}",
            source_type="event",
            value=f"Risiko {e.risk_score:.1f}",
            points=score,
            reason=e.title or "Veranstaltung",
            ts=e.starts_at,
        ))

    best = max((c["points"] for c in contributions), default=0)
    return {
        "score": min(100, best),
        "weight": 0.4,
        "detail": f"{len(events)} Veranstaltungen, {len(high_risk)} mit erhöhtem Risiko",
        "contributions": contributions,
    }


async def _calc_shipping_score(session) -> dict:
    stmt = select(RiverShippingWarning).where(RiverShippingWarning.is_active == True)
    result = await session.execute(stmt)
    warnings = result.scalars().all()

    if not warnings:
        return {"score": 0, "weight": 0.3, "detail": "Keine Warnungen", "contributions": []}

    contributions = []
    type_scores = {"closure": 60, "high_water": 50, "low_water": 40, "ice": 50, "construction": 10, "general": 15}

    for w in warnings:
        score = type_scores.get(w.warning_type, 15)
        contributions.append(_contrib(
            source=f"ELWIS - {w.river or 'Unbekannt'}",
            source_type="shipping",
            value=f"{w.warning_type}",
            points=score,
            reason=w.title or "Schifffahrtswarnung",
            ts=w.valid_from or w.created_at,
        ))

    best = max((c["points"] for c in contributions), default=0)
    closures = sum(1 for w in warnings if w.warning_type == "closure")
    detail = f"{len(warnings)} Warnungen"
    if closures:
        detail += f", {closures} Sperrungen"

    return {
        "score": min(100, best),
        "weight": 0.3,
        "detail": detail,
        "contributions": contributions,
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
                condition={"min_score": 40, "type": "high_water"},
                score_contribution=30,
                notification_channels=["push", "telegram"],
                is_enabled=True,
            ),
            AlertThreshold(
                category=AlertCategory.WATER,
                name="Niedrigwasser / Dürre",
                condition={"min_score": 30, "type": "low_water"},
                score_contribution=20,
                notification_channels=["push"],
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
            AlertThreshold(
                category=AlertCategory.SEISMIC,
                name="Erdbeben-Warnung",
                condition={"min_score": 40},
                score_contribution=20,
                notification_channels=["push", "telegram"],
                is_enabled=True,
            ),
            AlertThreshold(
                category=AlertCategory.RADIATION,
                name="Erhöhte Strahlung",
                condition={"min_score": 20},
                score_contribution=30,
                notification_channels=["push", "telegram", "sms"],
                is_enabled=True,
            ),
            AlertThreshold(
                category=AlertCategory.HEALTH,
                name="ICU-Kapazitätsengpass",
                condition={"min_score": 50},
                score_contribution=15,
                notification_channels=["push"],
                is_enabled=True,
            ),
            AlertThreshold(
                category=AlertCategory.POWER,
                name="Stromnetz-Belastung",
                condition={"min_score": 60},
                score_contribution=20,
                notification_channels=["push", "telegram"],
                is_enabled=True,
            ),
            AlertThreshold(
                category=AlertCategory.EVENTS,
                name="Großveranstaltung",
                condition={"min_score": 50},
                score_contribution=10,
                notification_channels=["push"],
                is_enabled=True,
            ),
            AlertThreshold(
                category=AlertCategory.SHIPPING,
                name="Schifffahrts-Sperrung",
                condition={"min_score": 40},
                score_contribution=10,
                notification_channels=["push"],
                is_enabled=True,
            ),
        ]
        for t in defaults:
            session.add(t)
        await session.commit()
        logger.info("Seeded default alert thresholds")
