import enum
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.schemas import (
    AlertFeedback, Deployment, CategoryCalibration, FeedbackOutcome, PowerOutage,
    WaterLevel, WeatherData, FireRisk, AirQuality, NewsItem,
    OfficialWarning, TrafficEvent, EventCalendar, Alert,
    RiskScore, AlertCategory, AlertThreshold, LightningData,
    EarthquakeEvent,
    RadiationReading,
    ICUCapacity,
    GridStatus,
    RiverShippingWarning,
    FuelStation,
    TransitDisruption,
    SoilMoisture,
    DroughtData,
    FloodWarningLevel,
    GDACAlert,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Fallback-Koordinaten fuer Stationen, deren raw_data keine Position enthaelt
# (currentmeasurement.json der Fix-Stationen liefert keine Koordinaten).
STATION_COORDS = {
    "KOELN": (50.9367, 6.9631),
    "BONN": (50.7220, 7.1128),
    "SIEGBURG": (50.8009, 7.2071),
    "TROISDORF": (50.8161, 7.1425),
}


def _station_coords(level: WaterLevel) -> tuple:
    raw = level.raw_data if isinstance(level.raw_data, dict) else {}
    lat = raw.get("latitude")
    lon = raw.get("longitude")
    if lat is not None and lon is not None:
        return lat, lon
    return STATION_COORDS.get((level.station_id or "").upper(), (None, None))


# Deutsche Kategorie-Aliasse (von der Mobile App verwendet) -> interne Enum-Werte
CATEGORY_ALIASES = {
    "hochwasser": "water",
    "wetter": "weather",
    "waldbrand": "fire",
    "verkehr": "traffic",
    "luftqualitaet": "air_quality",
    "nachrichten": "news",
    "warnungen": "official_warning",
    "erdbeben": "seismic",
    "strahlung": "radiation",
    "gesundheit": "health",
    "strom": "power",
    "veranstaltungen": "events",
    "schifffahrt": "shipping",
}
CATEGORY_LABELS = {
    "water": "Hochwasser",
    "weather": "Wetter",
    "fire": "Waldbrand",
    "traffic": "Verkehr",
    "air_quality": "Luftqualität",
    "news": "Nachrichten",
    "official_warning": "Behördenwarnungen",
    "seismic": "Erdbeben",
    "radiation": "Strahlung",
    "health": "Gesundheit",
    "power": "Stromnetz",
    "events": "Veranstaltungen",
    "shipping": "Schifffahrt",
    "manv": "MANV",
    "custom": "Benutzerdefiniert",
}
# Umkehrung: englischer Key -> deutscher Alias
CATEGORY_ALIASES_REVERSE = {v: k for k, v in CATEGORY_ALIASES.items()}


def resolve_category(value: str) -> str:
    """Akzeptiert deutsche Aliasse und englische Enum-Werte."""
    return CATEGORY_ALIASES.get(value.lower().strip(), value)


@router.get("/overview")
async def get_overview(db: AsyncSession = Depends(get_db)):
    cutoff = datetime.utcnow() - timedelta(hours=6)

    # Ein Scoring-Lauf schreibt ~13 Zeilen (eine pro Kategorie) — limit muss
    # gross genug sein, um fuer jede Kategorie den neuesten Wert zu erfassen.
    risk_stmt = (
        select(RiskScore)
        .where(RiskScore.calculated_at > cutoff)
        .order_by(desc(RiskScore.calculated_at))
        .limit(100)
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
                "label": CATEGORY_LABELS.get(cat, cat),
            }

    # Deutsche Alias-Keys für die Mobile App (gleiche Objekte, keine Duplikat-Daten)
    for cat in list(scores_by_cat.keys()):
        alias = CATEGORY_ALIASES_REVERSE.get(cat)
        if alias and alias not in scores_by_cat:
            scores_by_cat[alias] = scores_by_cat[cat]

    alert_stmt = select(Alert).where(Alert.is_active == True).order_by(desc(Alert.score))
    alert_result = await db.execute(alert_stmt)
    active_alerts = [
        {
            "id": a.id,
            "category": a.category.value,
            "category_label": CATEGORY_LABELS.get(a.category.value, a.category.value),
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
    canonical = {k: v for k, v in scores_by_cat.items() if k not in CATEGORY_ALIASES}
    if canonical:
        total = sum(s["score"] for s in canonical.values())
        overall = min(100, total / len(canonical))

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

    from app.collectors.water.pegel_collector import classify_water_level

    stations = {}
    for l in levels:
        if l.station_id not in stations:
            classification = classify_water_level(l.level_cm, l.river or "")
            lat, lon = _station_coords(l)
            stations[l.station_id] = {
                "station_id": l.station_id,
                "station_name": l.station_name,
                "river": l.river,
                "current_level": l.level_cm,
                "trend": l.trend,
                "warning_level": classification["warning_level"],
                "condition": classification["condition"],
                "lat": lat,
                "lon": lon,
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


@router.get("/weather-forecast")
async def get_weather_forecast(db: AsyncSession = Depends(get_db)):
    """Aktuelles Wetter, 24h-Vorhersage und 30-Tage-Hitze/Trockenheits-Analyse."""
    cutoff = datetime.utcnow() - timedelta(hours=24)

    async def latest(data_type: str):
        stmt = (
            select(WeatherData)
            .where(WeatherData.data_type == data_type)
            .where(WeatherData.source == "open_meteo")
            .where(WeatherData.created_at > cutoff)
            .order_by(desc(WeatherData.created_at))
            .limit(1)
        )
        return (await db.execute(stmt)).scalars().first()

    forecast = await latest("forecast")
    climate = await latest("climate_30d")

    return {
        "current": (forecast.parameters or {}).get("current") if forecast else None,
        "hourly_24h": (forecast.parameters or {}).get("hourly_24h") if forecast else None,
        "climate_30d": climate.parameters if climate else None,
        "climate_daily": climate.raw_data if climate else None,
        "updated_at": forecast.created_at.isoformat() if forecast else None,
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
                "is_relevant": n.is_relevant,
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
                "category_label": CATEGORY_LABELS.get(a.category.value, a.category.value),
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
        raise HTTPException(status_code=404, detail="Alert nicht gefunden")

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
            cat_enum = AlertCategory(resolve_category(category))
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


@router.get("/report")
async def get_situation_report(db: AsyncSession = Depends(get_db)):
    """Oeffentlicher Lagebericht fuer Dashboard und Mobile-App.

    Nutzt das lokale LLM, faellt bei Nichtverfuegbarkeit auf einen
    strukturierten Bericht aus den aktuellen Daten zurueck.
    """
    from app.services.analysis.llm_analyzer import analyzer
    from app.api.routes.analysis import _generate_fallback_report

    cutoff = datetime.utcnow() - timedelta(hours=24)

    risk_stmt = (
        select(RiskScore)
        .where(RiskScore.calculated_at > cutoff)
        .order_by(desc(RiskScore.calculated_at))
        .limit(100)
    )
    risk_result = await db.execute(risk_stmt)
    risk_scores = {}
    for r in risk_result.scalars().all():
        cat = r.category.value
        if cat not in risk_scores:
            risk_scores[cat] = {
                "score": r.score,
                "detail": r.components.get("detail", "") if r.components else "",
            }

    alert_stmt = select(Alert).where(Alert.is_active == True).order_by(desc(Alert.score))
    alert_result = await db.execute(alert_stmt)
    active_alerts = [
        {"category": a.category.value, "title": a.title, "score": a.score}
        for a in alert_result.scalars().all()
    ]

    news_stmt = (
        select(NewsItem)
        .where(and_(NewsItem.is_relevant == True, NewsItem.created_at > cutoff))
        .order_by(desc(NewsItem.relevance_score))
        .limit(15)
    )
    news_result = await db.execute(news_stmt)
    relevant_news = [
        {
            "title": n.title,
            "source": n.source,
            "category": n.category,
            "relevance_score": n.relevance_score,
            "ai_analysis": n.ai_analysis,
        }
        for n in news_result.scalars().all()
    ]

    context = {
        "risk_scores": risk_scores,
        "active_alerts": active_alerts,
        "relevant_news": relevant_news,
    }

    llm_available = await analyzer.check_availability()
    report = await analyzer.generate_situation_report(context) if llm_available else None
    if report is None:
        report = _generate_fallback_report(context)
        llm_available = False

    return {
        "report": report,
        "generated_at": datetime.utcnow().isoformat(),
        "llm_generated": llm_available,
        "context_summary": {
            "risk_categories": len(risk_scores),
            "active_alerts": len(active_alerts),
            "relevant_news": len(relevant_news),
        },
    }


@router.get("/scoring/live")
async def get_live_scoring_breakdown():
    from app.services.alert.alert_engine import calculate_risk_scores
    scores = await calculate_risk_scores()

    breakdown = {}
    for cat, data in scores.items():
        breakdown[cat] = {
            "score": data.get("score", 0),
            "weight": data.get("weight"),
            "detail": data.get("detail"),
            "contributions": data.get("contributions", []),
        }

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "categories": breakdown,
    }


@router.get("/scoring/history/{score_id}")
async def get_scoring_detail(score_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(RiskScore).where(RiskScore.id == score_id)
    result = await db.execute(stmt)
    score = result.scalar_one_or_none()
    if not score:
        return {"error": "Score nicht gefunden"}

    components = score.components or {}
    return {
        "id": score.id,
        "category": score.category.value,
        "score": score.score,
        "calculated_at": score.calculated_at.isoformat() if score.calculated_at else None,
        "detail": components.get("detail"),
        "weight": components.get("weight"),
        "contributions": components.get("contributions", []),
        "raw_components": {k: v for k, v in components.items() if k not in ("contributions",)},
    }


@router.get("/scoring/history")
async def get_scoring_breakdown_history(
    category: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    stmt = (
        select(RiskScore)
        .where(RiskScore.calculated_at > cutoff)
        .order_by(desc(RiskScore.calculated_at))
        .limit(limit)
    )
    if category:
        try:
            cat_enum = AlertCategory(category)
            stmt = stmt.where(RiskScore.category == cat_enum)
        except ValueError:
            return {"error": f"Unbekannte Kategorie: {category}"}

    result = await db.execute(stmt)
    scores = result.scalars().all()

    return {
        "entries": [
            {
                "id": s.id,
                "category": s.category.value,
                "score": s.score,
                "calculated_at": s.calculated_at.isoformat() if s.calculated_at else None,
                "detail": (s.components or {}).get("detail"),
                "contributions": (s.components or {}).get("contributions", []),
            }
            for s in scores
        ]
    }


# ---------------------------------------------------------------------------
# Generische Daten-Endpunkte: ALLES was der Server sammelt ist auch abrufbar.
# ---------------------------------------------------------------------------

DATASETS = {
    "seismic": (EarthquakeEvent, "Erdbeben (BGR/EMSC)"),
    "radiation": (RadiationReading, "Radioaktivität / ODL-Messnetz (BfS)"),
    "health": (ICUCapacity, "Intensivbetten-Kapazität (RKI Intensivregister)"),
    "power": (GridStatus, "Stromnetz-Status"),
    "shipping": (RiverShippingWarning, "Schifffahrts-Warnungen (PEGELONLINE / Rhein)"),
    "fuel": (FuelStation, "Kraftstoff-Verfügbarkeit (Tankerkönig)"),
    "transit": (TransitDisruption, "ÖPNV/Bahn-Störungen (KVB/VRR)"),
    "lightning": (LightningData, "Blitzdaten"),
    "soil-moisture": (SoilMoisture, "Bodenfeuchte"),
    "drought": (DroughtData, "Dürremonitor (UFZ)"),
    "flood-warnings": (FloodWarningLevel, "Hochwasser-Meldestufen (OpenHygon/PEGELONLINE)"),
    "gdac": (GDACAlert, "GDACS Katastrophen-Alerts"),
    "events": (EventCalendar, "Veranstaltungskalender"),
}

_EXCLUDED_COLUMNS = {"raw_data"}


def _serialize_row(obj, include_raw: bool = False) -> dict:
    """Alle Spalten einer Tabellenzeile JSON-tauglich serialisieren."""
    out = {}
    for col in obj.__table__.columns:
        if not include_raw and col.name in _EXCLUDED_COLUMNS:
            continue
        val = getattr(obj, col.name)
        if isinstance(val, datetime):
            val = val.isoformat()
        elif isinstance(val, enum.Enum):
            val = val.value
        out[col.name] = val
    return out


@router.get("/data")
async def list_datasets(db: AsyncSession = Depends(get_db)):
    """Alle zusätzlich verfügbaren Datensätze mit Anzahl der Einträge (letzte 7 Tage)."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    result = {}
    for key, (model, label) in DATASETS.items():
        stmt = select(func.count()).select_from(model)
        if hasattr(model, "created_at"):
            stmt = stmt.where(model.created_at > cutoff)
        count = (await db.execute(stmt)).scalar() or 0
        result[key] = {
            "label": label,
            "endpoint": f"/api/dashboard/data/{key}",
            "entries_7d": count,
        }
    return {"datasets": result}


@router.get("/data/{dataset}")
async def get_dataset(
    dataset: str,
    hours: int = Query(168, ge=1, le=8760),
    limit: int = Query(200, ge=1, le=2000),
    include_raw: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """Rohdaten eines Datensatzes, neueste zuerst."""
    if dataset not in DATASETS:
        raise HTTPException(status_code=404, detail=f"Unbekannter Datensatz. Verfügbar: {sorted(DATASETS)}")
    model, label = DATASETS[dataset]

    stmt = select(model)
    if hasattr(model, "created_at"):
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        stmt = stmt.where(model.created_at > cutoff).order_by(desc(model.created_at))
    else:
        stmt = stmt.order_by(desc(model.id))
    stmt = stmt.limit(limit)

    rows = (await db.execute(stmt)).scalars().all()
    return {
        "dataset": dataset,
        "label": label,
        "count": len(rows),
        "items": [_serialize_row(r, include_raw=include_raw) for r in rows],
    }


# ---------------------------------------------------------------------------
# Lernschleife: Rückmeldungen zu Alarmen und echten Einsätzen
# ---------------------------------------------------------------------------


class FeedbackRequest(BaseModel):
    outcome: str = Field(..., description="einsatz | vorsorge | kein_einsatz | unklar")
    deployment_type: Optional[str] = None
    forces_count: Optional[int] = None
    severity_rating: Optional[int] = Field(None, ge=1, le=5)
    lead_time_minutes: Optional[int] = None
    notes: Optional[str] = None
    reported_by: Optional[str] = None


class DeploymentRequest(BaseModel):
    category: str
    title: str
    description: Optional[str] = None
    occurred_at: Optional[datetime] = None
    forces_count: Optional[int] = None
    severity_rating: Optional[int] = Field(None, ge=1, le=5)
    matched_alert_id: Optional[int] = None
    reported_by: Optional[str] = None


@router.post("/alerts/{alert_id}/feedback")
async def submit_alert_feedback(
    alert_id: int,
    req: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Rückmeldung: Kam es nach diesem Alarm zu einem echten Einsatz?"""
    alert = (await db.execute(select(Alert).where(Alert.id == alert_id))).scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert nicht gefunden")

    try:
        outcome = FeedbackOutcome(req.outcome)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unbekanntes Ergebnis '{req.outcome}'. Erlaubt: "
                   f"{', '.join(o.value for o in FeedbackOutcome)}",
        )

    existing = (await db.execute(
        select(AlertFeedback).where(AlertFeedback.alert_id == alert_id)
    )).scalar_one_or_none()

    if existing:
        # Korrektur einer bereits abgegebenen Rückmeldung
        existing.outcome = outcome
        existing.deployment_type = req.deployment_type
        existing.forces_count = req.forces_count
        existing.severity_rating = req.severity_rating
        existing.lead_time_minutes = req.lead_time_minutes
        existing.notes = req.notes
        existing.reported_by = req.reported_by
        feedback = existing
        created = False
    else:
        feedback = AlertFeedback(
            alert_id=alert_id,
            category=alert.category,
            outcome=outcome,
            alert_score=alert.score,
            deployment_type=req.deployment_type,
            forces_count=req.forces_count,
            severity_rating=req.severity_rating,
            lead_time_minutes=req.lead_time_minutes,
            notes=req.notes,
            reported_by=req.reported_by,
            score_snapshot=alert.source_data,
        )
        db.add(feedback)
        created = True

    # Ein bestätigter Einsatz wird zugleich als Einsatz protokolliert —
    # so ist die Einsatzhistorie vollständig, egal über welchen Weg gemeldet.
    if outcome == FeedbackOutcome.EINSATZ:
        already = (await db.execute(
            select(Deployment).where(Deployment.matched_alert_id == alert_id)
        )).scalar_one_or_none()
        if not already:
            db.add(Deployment(
                category=alert.category,
                title=req.deployment_type or alert.title,
                description=req.notes,
                occurred_at=alert.triggered_at or datetime.utcnow(),
                forces_count=req.forces_count,
                severity_rating=req.severity_rating,
                was_predicted=True,
                matched_alert_id=alert_id,
                reported_by=req.reported_by,
            ))

    await db.commit()

    return {
        "status": "created" if created else "updated",
        "alert_id": alert_id,
        "outcome": outcome.value,
    }


@router.get("/alerts/pending-feedback")
async def get_alerts_pending_feedback(
    days: int = Query(14, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Quittierte Alarme, zu denen noch keine Rückmeldung vorliegt."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    answered = {
        r[0] for r in (await db.execute(select(AlertFeedback.alert_id))).all()
    }

    # Auch von selbst beendete Alarme abfragen: Seit Alarme aufgeloest werden,
    # waeren sonst genau die Faelle unbewertbar, die sich ohne Zutun erledigt
    # haben — und das sind die interessanten Fehlalarm-Kandidaten.
    alerts = (await db.execute(
        select(Alert)
        .where(and_(
            Alert.triggered_at > cutoff,
            or_(Alert.acknowledged == True, Alert.is_active == False),
        ))
        .order_by(desc(Alert.triggered_at))
    )).scalars().all()

    pending = [a for a in alerts if a.id not in answered]

    return {
        "count": len(pending),
        "alerts": [
            {
                "id": a.id,
                "category": a.category.value,
                "category_label": CATEGORY_LABELS.get(a.category.value, a.category.value),
                "score": a.score,
                "title": a.title,
                "description": a.description,
                "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
            }
            for a in pending
        ],
    }


@router.post("/deployments")
async def log_deployment(req: DeploymentRequest, db: AsyncSession = Depends(get_db)):
    """Einsatz melden — auch nachträglich und ohne vorherigen Alarm.

    Einsätze ohne Alarm sind die wichtigste Lernquelle: Sie zeigen, wo das
    System noch blind ist.
    """
    resolved = resolve_category(req.category)
    try:
        cat_enum = AlertCategory(resolved)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unbekannte Kategorie: {req.category}")

    occurred = req.occurred_at or datetime.utcnow()

    # Passenden Alarm suchen, falls keiner angegeben wurde: gleiche Kategorie,
    # ausgelöst in den 12 Stunden vor dem Einsatz.
    matched_id = req.matched_alert_id
    if matched_id is None:
        window_start = occurred - timedelta(hours=12)
        candidate = (await db.execute(
            select(Alert)
            .where(and_(
                Alert.category == cat_enum,
                Alert.triggered_at >= window_start,
                Alert.triggered_at <= occurred,
            ))
            .order_by(desc(Alert.triggered_at))
            .limit(1)
        )).scalar_one_or_none()
        if candidate:
            matched_id = candidate.id

    deployment = Deployment(
        category=cat_enum,
        title=req.title,
        description=req.description,
        occurred_at=occurred,
        forces_count=req.forces_count,
        severity_rating=req.severity_rating,
        was_predicted=matched_id is not None,
        matched_alert_id=matched_id,
        reported_by=req.reported_by,
    )
    db.add(deployment)
    await db.commit()
    await db.refresh(deployment)

    return {
        "status": "created",
        "id": deployment.id,
        "was_predicted": deployment.was_predicted,
        "matched_alert_id": matched_id,
        "hinweis": (
            "Kein passender Alarm gefunden — dieser Einsatz zählt als verpasste Warnung "
            "und macht das System in dieser Kategorie empfindlicher."
            if matched_id is None else
            "Passender Alarm gefunden und verknüpft."
        ),
    }


@router.get("/deployments")
async def list_deployments(
    days: int = Query(180, ge=1, le=1095),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (await db.execute(
        select(Deployment)
        .where(Deployment.occurred_at > cutoff)
        .order_by(desc(Deployment.occurred_at))
        .limit(limit)
    )).scalars().all()

    return {
        "count": len(rows),
        "deployments": [
            {
                "id": d.id,
                "category": d.category.value,
                "category_label": CATEGORY_LABELS.get(d.category.value, d.category.value),
                "title": d.title,
                "description": d.description,
                "occurred_at": d.occurred_at.isoformat() if d.occurred_at else None,
                "forces_count": d.forces_count,
                "severity_rating": d.severity_rating,
                "was_predicted": d.was_predicted,
                "matched_alert_id": d.matched_alert_id,
                "reported_by": d.reported_by,
            }
            for d in rows
        ],
    }


@router.delete("/deployments/{deployment_id}")
async def delete_deployment(deployment_id: int, db: AsyncSession = Depends(get_db)):
    """Fehleingabe zurücknehmen."""
    dep = (await db.execute(
        select(Deployment).where(Deployment.id == deployment_id)
    )).scalar_one_or_none()
    if not dep:
        raise HTTPException(status_code=404, detail="Einsatz nicht gefunden")
    await db.delete(dep)
    await db.commit()
    return {"status": "deleted", "id": deployment_id}


@router.get("/calibration")
async def get_calibration_status():
    """Lernstatus: Treffsicherheit und gelernte Anpassungen je Kategorie."""
    from app.services.learning.calibration import get_quality_report
    report = await get_quality_report()
    for cat in report.get("categories", []):
        cat["category_label"] = CATEGORY_LABELS.get(cat["category"], cat["category"])
    return report


@router.post("/calibration/recompute")
async def trigger_recompute(
    window_days: int = Query(180, ge=7, le=1095),
):
    """Kalibrierung sofort neu berechnen (läuft sonst täglich automatisch)."""
    from app.services.learning.calibration import recompute_calibration
    results = await recompute_calibration(window_days=window_days)
    return {"status": "recomputed", "categories": results}


@router.put("/calibration/{category}/lock")
async def set_calibration_lock(
    category: str,
    locked: bool = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Kategorie gegen automatische Anpassung sperren bzw. wieder freigeben."""
    resolved = resolve_category(category)
    try:
        cat_enum = AlertCategory(resolved)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unbekannte Kategorie: {category}")

    cal = (await db.execute(
        select(CategoryCalibration).where(CategoryCalibration.category == cat_enum)
    )).scalar_one_or_none()
    if not cal:
        cal = CategoryCalibration(category=cat_enum)
        db.add(cal)

    cal.is_locked = locked
    await db.commit()
    return {"status": "updated", "category": resolved, "is_locked": locked}


@router.get("/power")
async def get_power_detail(
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    """Stromnetz im Detail: Erzeugungsmix, Netzlast, Börsenpreis, Prognose.

    Liefert je Regelzone den aktuellsten Stand plus Verlauf. Troisdorf liegt
    im Amprion-Gebiet — dessen Werte sind lokal aussagekräftiger als die
    bundesweiten.
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    rows = (await db.execute(
        select(GridStatus)
        .where(GridStatus.created_at > cutoff)
        .order_by(desc(GridStatus.timestamp))
    )).scalars().all()

    if not rows:
        return {"regions": [], "history": [], "hinweis": "Noch keine Stromdaten erfasst"}

    regions = {}
    history = []
    for r in rows:
        raw = r.raw_data if isinstance(r.raw_data, dict) else {}
        entry = {
            "region": r.region,
            "region_label": raw.get("region_label", r.region),
            "generation_mw": r.generation_mw,
            "consumption_mw": r.consumption_mw,
            "balance_mw": r.balance_mw,
            "renewable_share": r.renewable_share,
            "price_eur_mwh": r.price_eur_mwh,
            "forecast_total_mw": raw.get("forecast_total_mw"),
            "import_share": raw.get("import_share"),
            "is_stressed": r.is_stressed,
            "stress_indicator": r.stress_indicator,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "generation_parts": raw.get("generation_parts", {}),
            "renewable_parts": raw.get("renewable_parts", {}),
            "conventional_parts": raw.get("conventional_parts", {}),
        }
        # Neuester Stand je Regelzone (rows sind absteigend sortiert)
        if r.region not in regions:
            regions[r.region] = entry

        history.append({
            "region": r.region,
            "timestamp": entry["timestamp"],
            "consumption_mw": r.consumption_mw,
            "generation_mw": r.generation_mw,
            "balance_mw": r.balance_mw,
            "renewable_share": r.renewable_share,
            "price_eur_mwh": r.price_eur_mwh,
        })

    # Bundeswert zuerst, dann die Regelzonen
    ordered = sorted(regions.values(), key=lambda x: (x["region"] != "DE", x["region"]))

    return {
        "regions": ordered,
        "history": history,
        "source": "SMARD / Bundesnetzagentur",
        "hinweis": (
            "Netzstress wird nur bundesweit bewertet — eine einzelne Regelzone "
            "hat keine eigene Bilanz."
        ),
    }


@router.get("/outages")
async def get_power_outages(
    include_resolved: bool = Query(False),
    max_distance_km: float = Query(60.0, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Konkrete Stromausfälle in der Region (Störungsauskunft der Netzbetreiber).

    Zwei Verlässlichkeitsstufen: `confirmed` sind vom Netzbetreiber bestätigte
    Störungen, `reported` sind gebündelte Bürgermeldungen — früher da, aber
    noch unbestätigt.
    """
    stmt = select(PowerOutage).where(PowerOutage.distance_km <= max_distance_km)
    if not include_resolved:
        stmt = stmt.where(PowerOutage.is_active == True)
    rows = (await db.execute(stmt.order_by(PowerOutage.distance_km))).scalars().all()

    def serialize(o):
        return {
            "id": o.id,
            "kind": o.kind,
            "operator_name": o.operator_name,
            "postal_code": o.postal_code,
            "city": o.city,
            "district": o.district,
            "street": o.street,
            "lat": o.lat,
            "lon": o.lon,
            "distance_km": o.distance_km,
            "report_count": o.report_count,
            "started_at": o.started_at.isoformat() if o.started_at else None,
            "expected_end": o.expected_end.isoformat() if o.expected_end else None,
            "is_active": o.is_active,
            "is_fixed": o.is_fixed,
            "info": o.info,
            "source": o.source,
        }

    confirmed = [o for o in rows if o.kind == "confirmed"]
    reported = [o for o in rows if o.kind == "reported"]
    grosslagen = [o for o in rows if o.kind == "grosslage"]
    extremlagen = [o for o in rows if o.kind == "extremlage"]

    # Entfernung nur über Troisdorf — eine Extremlage 120 km weiter als
    # "nächster Ausfall" auszuweisen wäre irreführend.
    local = confirmed + reported

    return {
        "confirmed": [serialize(o) for o in confirmed],
        "reported": [serialize(o) for o in reported],
        "grosslagen": [serialize(o) for o in grosslagen],
        "extremlagen": [serialize(o) for o in extremlagen],
        "count_confirmed": len(confirmed),
        "count_reported": len(reported),
        "count_grosslagen": len(grosslagen),
        "count_extremlagen": len(extremlagen),
        "nearest_km": min((o.distance_km for o in local if o.distance_km is not None),
                          default=None),
        "zonen": {
            "troisdorf": "jeder Ausfall",
            "rhein_sieg": "nur Großlagen ab 100 Meldungen",
            "ausserhalb": "nur Extremlagen ab 500 Meldungen",
        },
        "source": "Störungsauskunft der Verteilnetzbetreiber",
    }
