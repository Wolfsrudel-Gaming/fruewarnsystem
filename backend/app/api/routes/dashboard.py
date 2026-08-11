from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.schemas import (
    WaterLevel, WeatherData, FireRisk, AirQuality, NewsItem,
    OfficialWarning, TrafficEvent, EventCalendar, Alert,
    RiskScore, AlertCategory, AlertThreshold, LightningData,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview")
async def get_overview(db: AsyncSession = Depends(get_db)):
    cutoff = datetime.utcnow() - timedelta(hours=6)

    risk_stmt = (
        select(RiskScore)
        .order_by(desc(RiskScore.calculated_at))
        .limit(10)
    )
    risk_result = await db.execute(risk_stmt)
    risk_scores = risk_result.scalars().all()

    scores_by_cat = {}
    for r in risk_scores:
        cat = r.category.value
        if cat not in scores_by_cat:
            scores_by_cat[cat] = {
                "score": r.score,
                "components": r.components,
                "calculated_at": r.calculated_at.isoformat() if r.calculated_at else None,
            }

    alert_stmt = select(Alert).where(Alert.is_active == True).order_by(desc(Alert.score))
    alert_result = await db.execute(alert_stmt)
    active_alerts = [
        {
            "id": a.id,
            "category": a.category.value,
            "score": a.score,
            "title": a.title,
            "description": a.description,
            "escalation_level": a.escalation_level,
            "acknowledged": a.acknowledged,
            "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
        }
        for a in alert_result.scalars().all()
    ]

    overall = 0
    if scores_by_cat:
        total = sum(s["score"] for s in scores_by_cat.values())
        overall = min(100, total / len(scores_by_cat))

    return {
        "overall_score": overall,
        "risk_scores": scores_by_cat,
        "active_alerts": active_alerts,
        "last_updated": datetime.utcnow().isoformat(),
    }


@router.get("/water")
async def get_water_levels(
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    stmt = (
        select(WaterLevel)
        .where(WaterLevel.created_at > cutoff)
        .order_by(WaterLevel.station_id, desc(WaterLevel.timestamp))
    )
    result = await db.execute(stmt)
    levels = result.scalars().all()

    stations = {}
    for l in levels:
        if l.station_id not in stations:
            stations[l.station_id] = {
                "station_id": l.station_id,
                "station_name": l.station_name,
                "river": l.river,
                "current_level": l.level_cm,
                "trend": l.trend,
                "last_update": l.timestamp.isoformat() if l.timestamp else None,
                "history": [],
            }
        stations[l.station_id]["history"].append({
            "level_cm": l.level_cm,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
            "trend": l.trend,
        })

    return {"stations": list(stations.values())}


@router.get("/weather")
async def get_weather(
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    stmt = (
        select(WeatherData)
        .where(WeatherData.created_at > cutoff)
        .order_by(desc(WeatherData.created_at))
    )
    result = await db.execute(stmt)
    data = result.scalars().all()

    warnings = []
    forecasts = []
    radar = []
    for d in data:
        item = {
            "id": d.id,
            "type": d.data_type,
            "region": d.region,
            "severity": d.severity,
            "title": d.title,
            "description": d.description,
            "parameters": d.parameters,
            "valid_from": d.valid_from.isoformat() if d.valid_from else None,
            "valid_to": d.valid_to.isoformat() if d.valid_to else None,
            "source": d.source,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        if d.data_type == "warning":
            warnings.append(item)
        elif d.data_type == "forecast":
            forecasts.append(item)
        elif d.data_type == "radar":
            radar.append(item)

    return {"warnings": warnings, "forecasts": forecasts, "radar": radar}


@router.get("/fire")
async def get_fire_risk(db: AsyncSession = Depends(get_db)):
    cutoff = datetime.utcnow() - timedelta(hours=24)
    stmt = (
        select(FireRisk)
        .where(FireRisk.created_at > cutoff)
        .order_by(desc(FireRisk.created_at))
    )
    result = await db.execute(stmt)
    risks = result.scalars().all()

    return {
        "risks": [
            {
                "id": r.id,
                "region": r.region,
                "risk_index": r.risk_index,
                "temperature": r.temperature,
                "humidity": r.humidity,
                "wind_speed": r.wind_speed,
                "wind_direction": r.wind_direction,
                "rain_last_24h": r.rain_last_24h,
                "satellite_hotspots": r.satellite_hotspots,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "source": r.source,
            }
            for r in risks
        ]
    }


@router.get("/air-quality")
async def get_air_quality(db: AsyncSession = Depends(get_db)):
    cutoff = datetime.utcnow() - timedelta(hours=24)
    stmt = (
        select(AirQuality)
        .where(AirQuality.created_at > cutoff)
        .order_by(desc(AirQuality.created_at))
    )
    result = await db.execute(stmt)
    readings = result.scalars().all()

    return {
        "readings": [
            {
                "id": r.id,
                "station_id": r.station_id,
                "station_name": r.station_name,
                "pm25": r.pm25,
                "pm10": r.pm10,
                "ozone": r.ozone,
                "no2": r.no2,
                "aqi": r.aqi,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in readings
        ]
    }


@router.get("/news")
async def get_news(
    relevant_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(NewsItem).order_by(desc(NewsItem.created_at)).limit(limit)
    if relevant_only:
        stmt = stmt.where(NewsItem.is_relevant == True)

    result = await db.execute(stmt)
    items = result.scalars().all()

    return {
        "items": [
            {
                "id": n.id,
                "title": n.title,
                "summary": n.summary,
                "url": n.url,
                "source": n.source,
                "category": n.category,
                "relevance_score": n.relevance_score,
                "ai_analysis": n.ai_analysis,
                "published_at": n.published_at.isoformat() if n.published_at else None,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in items
        ]
    }


@router.get("/warnings")
async def get_official_warnings(
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(OfficialWarning).order_by(desc(OfficialWarning.created_at))
    if active_only:
        stmt = stmt.where(OfficialWarning.is_active == True)

    result = await db.execute(stmt)
    warnings = result.scalars().all()

    return {
        "warnings": [
            {
                "id": w.id,
                "warning_id": w.warning_id,
                "source_system": w.source_system,
                "severity": w.severity,
                "urgency": w.urgency,
                "category": w.category,
                "headline": w.headline,
                "description": w.description,
                "instruction": w.instruction,
                "area_description": w.area_description,
                "effective": w.effective.isoformat() if w.effective else None,
                "expires": w.expires.isoformat() if w.expires else None,
                "is_active": w.is_active,
            }
            for w in warnings
        ]
    }


@router.get("/traffic")
async def get_traffic(
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TrafficEvent).order_by(desc(TrafficEvent.created_at))
    if active_only:
        stmt = stmt.where(TrafficEvent.is_active == True)

    result = await db.execute(stmt)
    events = result.scalars().all()

    return {
        "events": [
            {
                "id": e.id,
                "road": e.road,
                "event_type": e.event_type,
                "title": e.title,
                "description": e.description,
                "lat": e.lat,
                "lon": e.lon,
                "severity": e.severity,
                "source": e.source,
                "started_at": e.started_at.isoformat() if e.started_at else None,
            }
            for e in events
        ]
    }


@router.get("/alerts")
async def get_alerts(
    active_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Alert).order_by(desc(Alert.created_at)).limit(limit)
    if active_only:
        stmt = stmt.where(Alert.is_active == True)

    result = await db.execute(stmt)
    alerts = result.scalars().all()

    return {
        "alerts": [
            {
                "id": a.id,
                "category": a.category.value,
                "score": a.score,
                "title": a.title,
                "description": a.description,
                "is_active": a.is_active,
                "acknowledged": a.acknowledged,
                "escalation_level": a.escalation_level,
                "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
                "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
            }
            for a in alerts
        ]
    }


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Alert).where(Alert.id == alert_id)
    result = await db.execute(stmt)
    alert = result.scalar_one_or_none()
    if not alert:
        return {"error": "Alert not found"}

    alert.acknowledged = True
    alert.acknowledged_at = datetime.utcnow()
    await db.commit()
    return {"status": "acknowledged", "id": alert_id}


@router.get("/thresholds")
async def get_thresholds(db: AsyncSession = Depends(get_db)):
    stmt = select(AlertThreshold).order_by(AlertThreshold.category)
    result = await db.execute(stmt)
    thresholds = result.scalars().all()

    return {
        "thresholds": [
            {
                "id": t.id,
                "category": t.category.value,
                "name": t.name,
                "condition": t.condition,
                "score_contribution": t.score_contribution,
                "notification_channels": t.notification_channels,
                "is_enabled": t.is_enabled,
            }
            for t in thresholds
        ]
    }


@router.put("/thresholds/{threshold_id}")
async def update_threshold(
    threshold_id: int,
    condition: dict,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AlertThreshold).where(AlertThreshold.id == threshold_id)
    result = await db.execute(stmt)
    threshold = result.scalar_one_or_none()
    if not threshold:
        return {"error": "Threshold not found"}

    threshold.condition = condition
    await db.commit()
    return {"status": "updated", "id": threshold_id}


@router.get("/history/risk-scores")
async def get_risk_score_history(
    category: Optional[str] = Query(None),
    hours: int = Query(168, ge=1, le=8760),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    stmt = (
        select(RiskScore)
        .where(RiskScore.calculated_at > cutoff)
        .order_by(RiskScore.calculated_at)
    )
    if category:
        try:
            cat_enum = AlertCategory(category)
            stmt = stmt.where(RiskScore.category == cat_enum)
        except ValueError:
            pass

    result = await db.execute(stmt)
    scores = result.scalars().all()

    return {
        "history": [
            {
                "category": s.category.value,
                "score": s.score,
                "calculated_at": s.calculated_at.isoformat(),
            }
            for s in scores
        ]
    }
