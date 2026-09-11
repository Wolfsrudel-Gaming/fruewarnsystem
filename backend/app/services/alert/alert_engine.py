import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, and_, or_

from app.config import settings
from app.models.database import async_session
from app.models.schemas import (
    Alert, AlertCategory, AlertThreshold, RiskScore,
    WaterLevel, WeatherData, FireRisk, AirQuality, NewsItem,
    OfficialWarning, TrafficEvent, EarthquakeEvent, RadiationReading,
    ICUCapacity, GridStatus, RiverShippingWarning, EventCalendar, PowerOutage,
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


# --- Wiederholungssperre -----------------------------------------------------
# Ohne diese Logik meldet ein unveraendert anhaltender Zustand bei jedem
# Collector-Lauf erneut. Neu benachrichtigt wird nur, wenn sich die Lage
# spuerbar verschaerft — sonst wird der bestehende Alarm still fortgeschrieben.

# Score-Anstieg, ab dem eine Lage als deutlich verschaerft gilt
SIGNIFICANT_RISE = 10.0

# Fruehestens nach dieser Zeit erneut benachrichtigen, selbst bei Anstieg
RENOTIFY_COOLDOWN = timedelta(hours=6)

# Puffer unterhalb der Schwelle, bevor ein Alarm als beendet gilt. Verhindert
# Flattern, wenn der Score um die Schwelle herum schwankt.
RESOLVE_HYSTERESIS = 5.0


def _last_notified_at(notifications) -> Optional[datetime]:
    """Zeitpunkt der letzten Benachrichtigung aus dem Protokoll."""
    if not isinstance(notifications, list):
        return None
    stamps = []
    for entry in notifications:
        raw = entry.get("at") if isinstance(entry, dict) else None
        if not raw:
            continue
        try:
            stamps.append(datetime.fromisoformat(raw))
        except (TypeError, ValueError):
            continue
    return max(stamps) if stamps else None


def decide_alert_action(
    condition_met: bool,
    current_score: float,
    min_score: float,
    existing: Optional[dict],
    now: Optional[datetime] = None,
) -> tuple:
    """Entscheidet, was mit einem Schwellenwert zu tun ist.

    Bewusst frei von Datenbank und Seiteneffekten, damit die Regeln
    testbar sind. ``existing`` beschreibt den laufenden Alarm derselben
    Schwelle: ``{"score", "escalation_level", "last_notified"}``.

    Rueckgabe: (aktion, begruendung) mit aktion aus
    ``create`` | ``notify_update`` | ``silent_update`` | ``resolve`` | ``none``.
    """
    now = now or datetime.utcnow()

    if not condition_met:
        if existing is None:
            return "none", "Schwelle nicht erreicht"
        # Erst unterhalb der Hysterese gilt die Lage als entspannt
        if current_score <= min_score - RESOLVE_HYSTERESIS:
            return "resolve", (
                f"Score {current_score:.0f} unter Schwelle {min_score:.0f} "
                f"(Hysterese {RESOLVE_HYSTERESIS:.0f}) — Alarm beendet"
            )
        return "silent_update", "Score knapp unter Schwelle — Alarm bleibt bestehen"

    if existing is None:
        return "create", f"Neuer Alarm, Score {current_score:.0f}"

    rise = current_score - existing["score"]
    new_level = _escalation_level_for_score(current_score)
    level_rise = new_level > existing.get("escalation_level", 0)

    # Eine hoehere Eskalationsstufe bedeutet neue Kanaele — das muss raus,
    # unabhaengig von der Sperrzeit.
    if level_rise:
        return "notify_update", (
            f"Eskalationsstufe {existing.get('escalation_level', 0)} -> {new_level} "
            f"(Score {existing['score']:.0f} -> {current_score:.0f})"
        )

    if rise < SIGNIFICANT_RISE:
        return "silent_update", (
            f"Lage unveraendert (Score {existing['score']:.0f} -> {current_score:.0f}) "
            f"— keine erneute Meldung"
        )

    last = existing.get("last_notified")
    if last is not None and (now - last) < RENOTIFY_COOLDOWN:
        remaining = RENOTIFY_COOLDOWN - (now - last)
        return "silent_update", (
            f"Score +{rise:.0f}, aber Sperrzeit laeuft noch "
            f"({remaining.total_seconds() / 3600:.1f}h)"
        )

    return "notify_update", f"Deutliche Verschaerfung: Score +{rise:.0f}"


# --- Gesamtrisiko ------------------------------------------------------------
# Der Gesamtscore darf kein Mittelwert sein. Ein Mittel ueber 13 Kategorien
# verduennt jede ernste Lage: zwei Kategorien auf 100 und elf ruhige ergaben
# fruehers einen Gesamtwert von 38 ("Erhoeht") — obwohl zwei Risiken am
# Anschlag standen. Massgeblich ist das hoechste Einzelrisiko; mehrere
# gleichzeitig erhoehte Lagen verschaerfen es zusaetzlich.

# Bezugsgewicht fuer die Relevanz-Normierung (hoechstes vergebenes Gewicht)
REFERENCE_WEIGHT = 2.0

# Auch eine gering gewichtete Kategorie behaelt diesen Mindesteinfluss —
# Schifffahrt am Anschlag ist nicht belanglos, nur weniger dringlich.
MIN_RELEVANCE = 0.6

# Ab diesem Score zaehlt eine Kategorie als "gleichzeitig erhoeht"
BREADTH_THRESHOLD = 40.0

# Wie stark Parallellagen den Restweg nach 100 schliessen (max. 50%)
BREADTH_FACTOR = 0.12
BREADTH_CAP = 0.5


def _relevance(weight: float) -> float:
    """Gewicht -> Einflussfaktor zwischen MIN_RELEVANCE und 1.0."""
    ratio = min(1.0, (weight or 1.0) / REFERENCE_WEIGHT)
    return MIN_RELEVANCE + (1.0 - MIN_RELEVANCE) * ratio


def aggregate_overall_score(categories: dict) -> dict:
    """Gesamtrisiko aus den Kategorie-Scores.

    ``categories`` ist ``{name: {"score": float, "weight": float}}``.

    Vorgehen: Jeder Score wird mit der Relevanz seiner Kategorie gewichtet.
    Der hoechste dieser Werte bildet die Untergrenze — die Gesamtlage kann
    nie harmloser sein als das schlimmste Einzelrisiko. Weitere erhoehte
    Kategorien schliessen anteilig den Weg zu 100.
    """
    if not categories:
        return {"score": 0.0, "driver": None, "effective": {}, "concurrent": []}

    effective = {}
    for name, data in categories.items():
        score = float(data.get("score") or 0)
        effective[name] = round(score * _relevance(data.get("weight", 1.0)), 1)

    driver = max(effective, key=lambda k: effective[k])
    top = effective[driver]

    concurrent = sorted(
        (n for n, v in effective.items() if n != driver and v >= BREADTH_THRESHOLD),
        key=lambda n: -effective[n],
    )
    breadth = sum(effective[n] / 100.0 for n in concurrent)
    bonus_share = min(BREADTH_CAP, BREADTH_FACTOR * breadth)

    overall = top + (100.0 - top) * bonus_share

    return {
        "score": round(min(100.0, overall), 1),
        "driver": driver,
        "driver_score": top,
        "effective": effective,
        "concurrent": concurrent,
    }


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
    # Gelernte Gewichtung aus den Einsatz-Rueckmeldungen
    from app.services.learning.calibration import get_calibration_map
    calibration = await get_calibration_map()

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
        # Kein Risikowert, sondern ein Fruehindikator: Das Aufkommen in
        # sozialen Netzen. Traegt bewusst 0 zum Gesamtrisiko bei — die
        # Auswertung passiert ueber das Signal, nicht ueber den Score.
        scores["social"] = await _calc_social_indicator(session)

        # Gelernte Multiplikatoren auf die Basisgewichte anwenden. Das
        # Basisgewicht bleibt als base_weight sichtbar, damit im Dashboard
        # nachvollziehbar ist, was das System gelernt hat.
        for cat_name, cat_data in scores.items():
            cal = calibration.get(cat_name)
            if not cal:
                continue
            multiplier = cal.get("multiplier", 1.0)
            if multiplier != 1.0:
                base = cat_data.get("weight", 1.0)
                cat_data["base_weight"] = base
                cat_data["weight"] = round(base * multiplier, 3)
                cat_data["calibration_multiplier"] = multiplier

        aggregate = aggregate_overall_score(scores)
        overall = aggregate["score"]

        overall_contributions = []
        for cat_name, cat_data in scores.items():
            w = cat_data.get("weight", 1.0)
            eff = aggregate["effective"].get(cat_name, 0)
            role = ""
            if cat_name == aggregate["driver"]:
                role = " — bestimmt die Gesamtlage"
            elif cat_name in aggregate["concurrent"]:
                role = " — verschaerft die Gesamtlage"
            overall_contributions.append(_contrib(
                source=cat_name,
                source_type="category_score",
                value=cat_data["score"],
                points=eff,
                reason=f"{cat_data['detail']} (Gewicht {w}x){role}",
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
        "score": overall,
        "driver": aggregate["driver"],
        "concurrent": aggregate["concurrent"],
        "contributions": overall_contributions,
    }
    return scores


async def check_thresholds_and_alert(scores: dict):
    """Prueft alle Schwellenwerte und meldet nur echte Aenderungen.

    Ein anhaltender Zustand erzeugt genau einen Alarm, der fortgeschrieben
    wird. Erneut benachrichtigt wird nur bei deutlicher Verschaerfung oder
    hoeherer Eskalationsstufe; faellt der Score unter die Schwelle, wird der
    Alarm beendet statt ewig aktiv zu bleiben.
    """
    to_notify = []
    now = datetime.utcnow()

    from app.services.learning.calibration import get_calibration_map
    calibration = await get_calibration_map()

    async with async_session() as session:
        thresholds = (await session.execute(
            select(AlertThreshold).where(AlertThreshold.is_enabled == True)
        )).scalars().all()

        # Alle laufenden Alarme einmal laden und der jeweiligen Schwelle
        # zuordnen. Frueher wurde pro Kategorie geprueft — damit blockierte
        # ein Alarm alle uebrigen Schwellen derselben Kategorie, und bei zwei
        # aktiven Alarmen brach scalar_one_or_none() mit einem Fehler ab.
        active_alerts = (await session.execute(
            select(Alert).where(Alert.is_active == True)
        )).scalars().all()

        by_threshold = {}
        for a in active_alerts:
            by_threshold.setdefault(_threshold_key_of(a), []).append(a)

        for threshold in thresholds:
            cat = threshold.category.value
            if cat not in scores:
                continue

            score_data = scores[cat]
            current_score = score_data["score"]
            condition = threshold.condition or {}
            configured_min = condition.get("min_score", 50)

            # Gelernter Offset: negativ = frueher warnen, positiv = zurueckhaltender.
            # Auf 5..95 begrenzt, damit eine Kategorie weder dauerfeuert noch verstummt.
            offset = calibration.get(cat, {}).get("offset", 0.0)
            min_score = max(5.0, min(95.0, configured_min + offset))

            type_matches = True
            required_type = condition.get("type")
            if required_type:
                type_matches = required_type == score_data.get("primary_condition", "")

            condition_met = type_matches and current_score >= min_score

            key = (threshold.category, threshold.name)
            running = by_threshold.get(key, [])
            # Sollten sich historisch mehrere angesammelt haben: den juengsten
            # fortfuehren, die uebrigen stillschweigend schliessen.
            running.sort(key=lambda a: a.triggered_at or datetime.min, reverse=True)
            current = running[0] if running else None
            for stale in running[1:]:
                stale.is_active = False
                stale.resolved_at = now

            existing_info = None
            if current is not None:
                existing_info = {
                    "score": current.score,
                    "escalation_level": current.escalation_level or 0,
                    "last_notified": _last_notified_at(current.notifications_sent)
                                     or current.triggered_at,
                }

            action, reason = decide_alert_action(
                condition_met=condition_met,
                current_score=current_score,
                min_score=min_score,
                existing=existing_info,
                now=now,
            )

            if action == "none":
                continue

            if action == "resolve":
                current.is_active = False
                current.resolved_at = now
                logger.info("Alarm beendet: %s — %s", threshold.name, reason)
                continue

            if action == "silent_update":
                # Lage laeuft weiter: Score aktualisieren, aber niemanden wecken
                current.score = current_score
                current.source_data = scores[cat]
                logger.debug("Alarm unveraendert: %s — %s", threshold.name, reason)
                continue

            threshold_note = (
                f"Schwellenwert {min_score:.0f} überschritten. "
                f"Aktueller Score: {current_score:.1f}"
            )
            if abs(min_score - configured_min) >= 0.5:
                direction = "gesenkt" if min_score < configured_min else "angehoben"
                threshold_note += (
                    f" (Schwelle aus Einsatz-Rückmeldungen von {configured_min:.0f} "
                    f"auf {min_score:.0f} {direction})"
                )

            if action == "create":
                alert = Alert(
                    category=threshold.category,
                    score=current_score,
                    title=f"{threshold.name}: Score {current_score:.0f}/100",
                    description=threshold_note,
                    source_data=scores[cat],
                    # Schwellenname mitschreiben, damit ein laufender Alarm
                    # spaeter eindeutig seiner Schwelle zugeordnet werden kann
                    threshold_config={**condition, "_threshold": threshold.name},
                    is_active=True,
                    escalation_level=_escalation_level_for_score(current_score),
                    notifications_sent=[],
                )
                session.add(alert)
                to_notify.append((alert, reason, False))
                logger.warning("ALERT: %s — Score %.0f (%s)", threshold.name, current_score, reason)

            elif action == "notify_update":
                current.score = current_score
                current.title = f"{threshold.name}: Score {current_score:.0f}/100"
                current.description = threshold_note + f" — {reason}"
                current.source_data = scores[cat]
                current.escalation_level = _escalation_level_for_score(current_score)
                # Verschaerft sich die Lage, ist eine frueher erteilte
                # Quittierung ueberholt.
                current.acknowledged = False
                current.acknowledged_at = None
                to_notify.append((current, reason, True))
                logger.warning("ALERT verschaerft: %s — %s", threshold.name, reason)

        await session.commit()

        # Benachrichtigungs-Protokoll erst nach dem Versand fortschreiben
        for alert, reason, _ in to_notify:
            await session.refresh(alert)

    # Nach dem Commit: Kanäle benachrichtigen + WebSocket-Clients (App!) informieren.
    # Fehler hier dürfen den Collector-Lauf nicht abbrechen.
    for alert, reason, is_escalation in to_notify:
        sent = []
        try:
            from app.services.notification.notifier import send_alert_notifications
            sent = await send_alert_notifications(alert)
            logger.info("Alert %s: Benachrichtigungen gesendet via %s",
                        alert.id, sent or "keine Kanäle")
        except Exception as e:
            logger.error("Alert %s: Benachrichtigung fehlgeschlagen: %s", alert.id, e)

        try:
            from app.api.websocket.manager import ws_manager
            await ws_manager.broadcast({
                "type": "alert",
                "escalation": is_escalation,
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
            logger.error("Alert %s: WebSocket-Broadcast fehlgeschlagen: %s", alert.id, e)

        # Zeitpunkt festhalten — Grundlage der Sperrzeit beim naechsten Lauf
        try:
            async with async_session() as session:
                fresh = await session.get(Alert, alert.id)
                if fresh is not None:
                    log = list(fresh.notifications_sent or [])
                    log.append({
                        "at": datetime.utcnow().isoformat(),
                        "channels": sent,
                        "reason": reason,
                        "escalation": is_escalation,
                    })
                    fresh.notifications_sent = log[-20:]
                    await session.commit()
        except Exception as e:
            logger.error("Alert %s: Benachrichtigungsprotokoll nicht gespeichert: %s",
                         alert.id, e)


def _threshold_key_of(alert: Alert) -> tuple:
    """Ordnet einen bestehenden Alarm seiner Schwelle zu.

    Neuere Alarme tragen den Namen in ``threshold_config``. Aeltere aus der
    Zeit davor werden ueber den Titel zugeordnet, der mit dem Schwellennamen
    beginnt.
    """
    cfg = alert.threshold_config if isinstance(alert.threshold_config, dict) else {}
    name = cfg.get("_threshold")
    if not name and alert.title and ":" in alert.title:
        name = alert.title.rsplit(":", 1)[0].strip()
    return (alert.category, name or "")


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


# Wie weit im Voraus eine noch nicht begonnene Warnung schon zaehlt.
# Fuer ein Fruehwarnsystem ist genau das der interessante Teil.
WARNING_LOOKAHEAD = timedelta(hours=24)
# Rueckfalldauer fuer Warnungen ohne Gueltigkeitsende — ohne die wuerden
# Altlasten ohne valid_to ewig weiterzaehlen.
WARNING_MAX_AGE = timedelta(days=3)


def is_warning_active(
    valid_from: Optional[datetime],
    valid_to: Optional[datetime],
    created_at: Optional[datetime],
    now: Optional[datetime] = None,
) -> bool:
    """Zaehlt diese Warnung zur aktuellen Lage?

    Drei Bedingungen, alle muessen zutreffen:

    1. Sie laeuft noch — ``valid_to`` liegt in der Zukunft.
    2. Sie hat begonnen oder beginnt binnen ``WARNING_LOOKAHEAD``. Genau dieser
       Vorlauf ist der Sinn eines Fruehwarnsystems.
    3. Fehlt ``valid_to``, greift ersatzweise eine Altersgrenze, damit
       Datensaetze ohne Ende nicht ewig weiterzaehlen.

    ``active_warning_condition`` bildet dieselbe Logik als SQL-Ausdruck ab;
    beide muessen zusammen geaendert werden.
    """
    now = now or datetime.utcnow()
    if valid_to is not None:
        if valid_to < now:
            return False
    elif created_at is None or created_at <= now - WARNING_MAX_AGE:
        return False
    if valid_from is not None and valid_from > now + WARNING_LOOKAHEAD:
        return False
    return True


def active_warning_condition(now: Optional[datetime] = None):
    """SQL-Fassung von :func:`is_warning_active`.

    Frueher wurde ueber ``created_at`` gefiltert, was nur funktionierte, weil der
    Collector jede Warnung bei jedem Lauf neu einfuegte. Seit dem Upsert bleibt
    ``created_at`` auf dem Erstkontakt stehen — massgeblich ist jetzt der
    Gueltigkeitszeitraum der Warnung selbst.
    """
    now = now or datetime.utcnow()
    return and_(
        WeatherData.data_type == "warning",
        # laeuft noch (oder hat kein Ende, dann greift die Altersgrenze)
        or_(
            WeatherData.valid_to.is_(None),
            WeatherData.valid_to >= now,
        ),
        # hat begonnen oder beginnt in Kuerze
        or_(
            WeatherData.valid_from.is_(None),
            WeatherData.valid_from <= now + WARNING_LOOKAHEAD,
        ),
        # Sicherheitsnetz gegen Datensaetze ohne valid_to
        or_(
            WeatherData.valid_to.isnot(None),
            WeatherData.created_at > now - WARNING_MAX_AGE,
        ),
    )


async def _calc_weather_score(session) -> dict:
    stmt = (
        select(WeatherData)
        .where(active_warning_condition())
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


# Woran eine Probewarnung im TEXT zu erkennen ist.
#
# GRUNDSATZ: Diese Erkennung daempft NIEMALS den Alarm. Ein Probealarm wird
# behandelt wie ein Vollalarm — das ist der Sinn der Sache.
#
# Der Bund sendet den Bundesweiten Warntag bewusst mit status "Actual" und
# msgType "Alert", also wie eine echte Warnung (geprueft am 10.09.2026 an der
# laufenden Warnung). Genau deshalb, weil die ganze Alarmkette getestet werden
# soll. Ein System, das Probealarme leiser behandelt, prueft sich selbst nicht
# — und koennte im Ernstfall eine echte Warnung faelschlich fuer eine Uebung
# halten und wegdaempfen.
#
# Der Hinweis dient allein der Anzeige: Der Nutzer soll lesen koennen, was in
# der Warnung steht. Die Alarmstaerke beruehrt er nicht.
PROBEWARNUNG_BEGRIFFE = (
    "probewarnung", "probealarm", "warntag", "testwarnung", "probemeldung",
    "uebungswarnung", "übungswarnung", "dies ist eine übung",
    "dies ist eine uebung",
)

# Dringlichkeit gewichtet die Schwere. Eine Extremwarnung, die erst in Tagen
# eintritt, ist etwas anderes als eine, die jetzt gilt.
URGENCY_FAKTOR = {
    "immediate": 1.0,
    "expected": 0.85,
    "future": 0.6,
    "past": 0.3,
    "unknown": 0.85,
}


def _ist_probewarnung(*texte) -> bool:
    text = " ".join(str(t or "") for t in texte).lower()
    return any(w in text for w in PROBEWARNUNG_BEGRIFFE)


# Eine Entwarnung traegt dieselbe Schwere wie die Warnung, die sie zuruecknimmt
# — am Warntag 2026 kam sie mit severity "Extreme" und msgType "Cancel". Wer
# nur die Schwere liest, alarmiert bei der Entwarnung genauso laut.
#
# Der Kollektor setzt Entwarnungen bereits auf inaktiv. Diese Pruefung ist die
# zweite Sicherung: Sollte eine doch als aktiv durchkommen, darf sie die Lage
# nicht anheben.
def _ist_entwarnung(w) -> bool:
    roh = w.raw_data if isinstance(w.raw_data, dict) else {}
    typ = str(roh.get("_msg_type") or "").strip().lower()
    if typ in ("cancel", "allclear", "all clear"):
        return True
    kopf = (w.headline or "").strip().lower()
    return kopf.startswith("entwarnung")


async def _calc_warning_score(session) -> dict:
    """Behoerdliche Warnungen bewerten.

    Drei Dinge muessen hier zusammenkommen, die vorher fehlten:

    * Der GELTUNGSBEREICH. Eine Warnung fuer "Deutschland" oder "Nordrhein-
      Westfalen" schliesst Troisdorf ein — sie ist nicht "woanders", sondern
      "ueberall, also auch hier". Ohne diese Unterscheidung wurde am
      Bundesweiten Warntag eine Extremwarnung fuer das gesamte Bundesgebiet
      wie eine Meldung aus einem fremden Kreis gedaempft.
    * Die DRINGLICHKEIT. CAP liefert sie mit, sie blieb bisher ungenutzt.
    * Die PROBEWARNUNG. Sie muss erkennbar sein, damit sie die Lernschleife
      nicht verfaelscht — alarmiert wird trotzdem, denn genau dafuer ist ein
      Probealarm da.
    """
    from app.services.knowledge.geo import (
        SCOPE_FLAECHIG, SCOPE_ORT, covers_troisdorf, detect_scope,
    )

    stmt = select(OfficialWarning).where(OfficialWarning.is_active == True)
    result = await session.execute(stmt)
    warnings = result.scalars().all()

    if not warnings:
        return {"score": 0, "weight": 2.0, "detail": "Keine Warnungen",
                "area_scope": "unbekannt", "covers_us": False,
                "is_test": False, "contributions": []}

    severity_map = {"minor": 20, "moderate": 40, "severe": 70, "extreme": 100}
    max_score = 0
    contributions = []

    leit = None          # massgebliche Warnung
    leit_punkte = -1.0
    flaechendeckend = 0
    probe = 0
    aufgehoben = 0

    for w in warnings:
        # Eine Entwarnung hebt die Lage auf, sie treibt sie nicht.
        if _ist_entwarnung(w):
            aufgehoben += 1
            contributions.append(_contrib(
                source=f"{w.source_system or 'NINA'} - {w.area_description or 'Unbekannt'}",
                source_type="official_warning_cancel",
                value="Entwarnung",
                points=0,
                reason=(w.headline or "Entwarnung") +
                       " · hebt eine vorherige Warnung auf, zaehlt nicht zur Lage",
                ts=w.effective,
            ))
            continue

        roh = severity_map.get((w.severity or "").lower(), 30)
        faktor = URGENCY_FAKTOR.get((w.urgency or "unknown").lower(), 0.85)
        punkte = roh * faktor

        gebiet = f"{w.area_description or ''} {w.headline or ''}"
        treffer = detect_scope(gebiet)
        deckt_uns = covers_troisdorf(gebiet)
        ist_probe = _ist_probewarnung(w.headline, w.description, w.area_description)

        if treffer["scope"] == SCOPE_FLAECHIG:
            flaechendeckend += 1
        if ist_probe:
            probe += 1

        # Massgeblich ist die schwerste Warnung, die uns tatsaechlich betrifft.
        # Eine Extremwarnung fuer einen fremden Kreis darf die Lage hier nicht
        # bestimmen — eine fuer ganz Deutschland sehr wohl.
        #
        # ist_probe geht hier bewusst NICHT ein: Ein Probealarm zaehlt mit
        # voller Staerke.
        gewichtet = punkte * (1.0 if deckt_uns else 0.5)
        if gewichtet > leit_punkte:
            leit_punkte = gewichtet
            leit = {"warnung": w, "scope": treffer["scope"],
                    "deckt_uns": deckt_uns, "ist_probe": ist_probe}

        max_score = max(max_score, punkte)

        hinweise = [w.headline or "Behördliche Warnung"]
        if w.area_description:
            hinweise.append(f"Gebiet: {w.area_description}")
        if w.urgency:
            hinweise.append(f"Dringlichkeit: {w.urgency}")
        if ist_probe:
            hinweise.append("PROBEWARNUNG")

        contributions.append(_contrib(
            source=f"{w.source_system or 'NINA'} - {w.area_description or 'Unbekannt'}",
            source_type="official_warning",
            value=f"Severity: {w.severity}",
            points=punkte,
            reason=" · ".join(hinweise),
            ts=w.effective,
        ))

    echte = len(warnings) - aufgehoben
    details = [f"{echte} aktive Warnung{'en' if echte != 1 else ''}"]
    if flaechendeckend:
        details.append(f"{flaechendeckend} flächendeckend")
    if probe:
        details.append(f"{probe} Probewarnung{'en' if probe > 1 else ''}")
    if aufgehoben:
        details.append(f"{aufgehoben} Entwarnung{'en' if aufgehoben > 1 else ''}")
    if echte == 0:
        details = ["Keine aktive Warnung"]
        if aufgehoben:
            details.append(f"{aufgehoben} Entwarnung{'en' if aufgehoben > 1 else ''}")

    return {
        "score": round(min(100, max_score), 1),
        "weight": 2.0,
        "detail": " · ".join(details),
        "cancelled": aufgehoben,
        # Der Ortsbezug der massgeblichen Warnung steuert die Einsatzerwartung
        "area_scope": leit["scope"] if leit else "unbekannt",
        "area": leit["warnung"].area_description if leit else None,
        "covers_us": bool(leit and leit["deckt_uns"]),
        "flaechendeckend": flaechendeckend,
        "is_test": bool(leit and leit["ist_probe"]),
        "max_severity": (leit["warnung"].severity if leit else None),
        "max_urgency": (leit["warnung"].urgency if leit else None),
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
        return {"score": 0, "weight": 0.6, "detail": "Keine relevanten Nachrichten",
                "area_scope": "unbekannt", "contributions": []}

    from app.services.knowledge.geo import SCOPE_ORT, detect_scope

    max_relevance = max(n.relevance_score for n in news)
    score = max_relevance * 80
    contributions = []

    # Der Ortsbezug der staerksten Meldung bestimmt den Ortsbezug der
    # Kategorie. Nicht der haeufigste: Eine einzelne Meldung ueber einen
    # Grossbrand in Troisdorf wiegt schwerer als fuenf ueber anderswo.
    leitmeldung = max(news, key=lambda n: n.relevance_score or 0)
    orts_treffer = detect_scope(leitmeldung.title, leitmeldung.summary or "")

    for n in news[:10]:
        ai = n.ai_analysis or {}
        article_points = n.relevance_score * 80
        ort = detect_scope(n.title, n.summary or "")

        reason_parts = []
        # Der Titel steht bewusst vorn: Er traegt Ortsnamen und Stichworte,
        # auf die die Einsatzerwartung ihre Evakuierungserkennung stuetzt.
        reason_parts.append(n.title[:160])
        if ort["ort"]:
            reason_parts.append(f"Ort: {ort['ort']}")
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
            reason=" · ".join(reason_parts),
            ts=n.published_at or n.created_at,
        ))

    lokale = sum(
        1 for n in news
        if detect_scope(n.title, n.summary or "")["scope"] == SCOPE_ORT
    )
    detail = f"{len(news)} relevante Nachrichten"
    if lokale:
        detail += f", davon {lokale} aus Troisdorf/Siegburg"

    return {
        "score": min(100, score),
        "weight": 0.6,
        "detail": detail,
        # Massgeblich fuer den Ortsfaktor der Einsatzerwartung
        "area_scope": orts_treffer["scope"],
        "area": orts_treffer["ort"],
        "local_count": lokale,
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
    """Bewertet die Stromlage.

    Massgeblich sind konkrete Ausfaelle in der Region — die bundesweite
    Erzeugungsbilanz sagt nichts darueber aus, ob in Troisdorf das Licht
    ausgeht, und geht nur noch als gedeckelter Nebenaspekt ein.
    """
    contributions = []
    outage_score = 0
    outage_detail = None

    # --- Konkrete Stromausfaelle (Hauptsignal) ---
    outages = (await session.execute(
        select(PowerOutage)
        .where(PowerOutage.is_active == True)
        .order_by(PowerOutage.distance_km)
    )).scalars().all()

    confirmed = [o for o in outages if o.kind == "confirmed"]
    reported = [o for o in outages if o.kind == "reported"]
    grosslagen = [o for o in outages if o.kind == "grosslage"]
    extremlagen = [o for o in outages if o.kind == "extremlage"]

    for o in outages:
        d = o.distance_km if o.distance_km is not None else 999
        count = o.report_count or 0

        if o.kind == "grosslage":
            # Im eigenen Kreis: flaechiger Ausfall, kann Kreis-Kraefte binden
            score = 70 if count >= 300 else 55
            quelle = "Grosslage im Rhein-Sieg-Kreis"
            grund = (f"{count} Meldungen um {o.city or 'den Kreis'} ({d:.0f} km) — "
                     f"flaechiger Ausfall im eigenen Kreisgebiet")
        elif o.kind == "extremlage":
            # Ausserhalb: nur noch als moegliche Amtshilfe-Lage relevant
            score = 60 if count >= 1500 else 45
            quelle = "Extremlage ausserhalb des Kreises"
            grund = (f"{count} Meldungen um {o.city or 'die Region'} ({d:.0f} km) — "
                     f"moegliche Amtshilfe-Lage")
        elif o.kind == "confirmed":
            score = 95 if d <= 5 else 85
            quelle = f"Netzbetreiber {o.operator_name or 'unbekannt'}"
            grund = f"Bestaetigter Stromausfall in {o.city or o.postal_code or 'Troisdorf'}"
            if o.expected_end:
                grund += f", voraussichtlich bis {o.expected_end.strftime('%H:%M')}"
        else:
            # Buergermeldungen aus Troisdorf: frueher, aber unsicherer Hinweis.
            # Viele Meldungen erhoehen die Verlaesslichkeit.
            confidence = min(1.0, 0.4 + 0.1 * count)
            score = 85 * confidence * 0.7
            quelle = "Buergermeldungen Troisdorf (unbestaetigt)"
            grund = (f"{count} Meldungen aus {o.city or 'Troisdorf'} — "
                     f"vom Netzbetreiber noch nicht bestaetigt")

        contributions.append(_contrib(
            source=quelle,
            source_type="power_outage",
            value=f"{d:.0f} km entfernt",
            points=score,
            reason=grund,
            ts=o.started_at,
        ))
        outage_score = max(outage_score, score)

    if confirmed:
        outage_detail = f"{len(confirmed)} bestaetigte Stromausfaelle in Troisdorf"
    elif reported:
        outage_detail = f"{len(reported)} unbestaetigte Meldungscluster in Troisdorf"
    elif grosslagen:
        biggest = max(grosslagen, key=lambda o: o.report_count or 0)
        outage_detail = (f"Grosslage im Kreis: {biggest.report_count} Meldungen "
                         f"um {biggest.city or 'den Kreis'}")
    elif extremlagen:
        biggest = max(extremlagen, key=lambda o: o.report_count or 0)
        outage_detail = (f"Extremlage ausserhalb: {biggest.report_count} Meldungen "
                         f"um {biggest.city or 'die Region'}")

    # --- Bundesweite Netzbilanz (Nebenaspekt, gedeckelt) ---
    cutoff = datetime.utcnow() - timedelta(hours=6)
    readings = (await session.execute(
        select(GridStatus)
        .where(GridStatus.created_at > cutoff)
        .order_by(GridStatus.created_at.desc())
        .limit(5)
    )).scalars().all()

    grid_score = 0
    for r in [x for x in readings if x.is_stressed]:
        balance = r.balance_mw or 0
        consumption = r.consumption_mw or 0
        if consumption <= 0 or balance >= 0:
            continue
        import_share = -balance / consumption

        if import_share >= 0.30:
            score = 40
        elif import_share >= 0.25:
            score = 30
        elif import_share >= 0.20:
            score = 20
        else:
            score = 12

        contributions.append(_contrib(
            source=f"SMARD Bundesnetzagentur - {r.region}",
            source_type="grid",
            value=f"Import {abs(balance):.0f} MW ({import_share:.0%} der Netzlast)",
            points=score,
            reason=(r.stress_indicator or "Erhoehter Importbedarf")
                   + " (bundesweit, kein lokaler Ausfall)",
            ts=r.timestamp,
        ))
        grid_score = max(grid_score, score)

    total = max(outage_score, grid_score)

    if outage_detail:
        detail = outage_detail
        if confirmed:
            primary = "outage"
        elif reported:
            primary = "outage_unconfirmed"
        elif grosslagen:
            primary = "grosslage_kreis"
        else:
            primary = "extremlage_ausserhalb"
    elif grid_score:
        detail = "Bundesweit erhoehter Importbedarf"
        primary = "grid_stress"
    elif readings:
        latest = readings[0]
        if latest.balance_mw is None:
            detail = "Keine Ausfaelle gemeldet"
        elif latest.balance_mw >= 0:
            detail = f"Keine Ausfaelle, Erzeugungsueberschuss {latest.balance_mw:.0f} MW"
        else:
            detail = f"Keine Ausfaelle, Import {abs(latest.balance_mw):.0f} MW (Normalbetrieb)"
        primary = "normal"
    else:
        detail = "Keine Daten"
        primary = "normal"

    return {
        "score": min(100, total),
        "weight": 0.7,
        "detail": detail,
        "primary_condition": primary,
        "confirmed_outages": len(confirmed),
        "reported_clusters": len(reported),
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


async def _calc_social_indicator(session) -> dict:
    """Aufkommen in sozialen Netzen — Fruehindikator, kein Risikowert.

    Bewusst mit Score 0: Ein Aufkommen darf die Gesamtlage nicht von selbst
    anheben, denn es ist unbestaetigt. Bewertet wird es ueber das Signal in
    services/knowledge/signals.py, das die Unsicherheit ausdruecklich benennt.
    """
    from app.models.schemas import SocialPost
    from app.services.knowledge.social_burst import FENSTER, finde_aufkommen

    # Etwas mehr als das Auswertefenster laden, damit Beitraege am Rand nicht
    # verlorengehen.
    cutoff = datetime.utcnow() - FENSTER * 2
    posts = (await session.execute(
        select(SocialPost)
        .where(and_(SocialPost.is_incident == True,
                    SocialPost.posted_at.isnot(None),
                    SocialPost.posted_at > cutoff))
        .order_by(SocialPost.posted_at.desc())
        .limit(300)
    )).scalars().all()

    aufkommen = finde_aufkommen(posts)

    contributions = []
    if aufkommen:
        contributions.append(_contrib(
            source=f"Soziale Netze – {aufkommen['ort']}",
            source_type="social_burst",
            value=f"{aufkommen['konten']} Konten",
            points=0,
            reason=(
                f"{aufkommen['beitraege']} Beitraege von "
                f"{aufkommen['konten']} Konten binnen "
                f"{aufkommen['fenster_minuten']} Minuten · UNBESTAETIGT"
            ),
        ))

    return {
        # Nie ein eigener Risikowert — siehe Beschreibung oben
        "score": 0,
        "weight": 0.0,
        "detail": (
            f"Aufkommen zu {aufkommen['ort']}: {aufkommen['beitraege']} "
            f"Beitraege, {aufkommen['konten']} Konten"
            if aufkommen else
            f"{len(posts)} Beitraege mit Ereignisbezug, kein Aufkommen"
        ),
        "burst": aufkommen,
        "posts_gesamt": len(posts),
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
    """Legt fehlende Standard-Schwellenwerte an.

    Frueher brach die Funktion ab, sobald ueberhaupt Schwellen existierten —
    neu hinzugekommene Standards erreichten damit keine laufende Installation.
    Jetzt wird je (Kategorie, Name) ergaenzt, Bestehendes bleibt unangetastet.
    """
    async with async_session() as session:
        existing_rows = (await session.execute(select(AlertThreshold))).scalars().all()
        known = {(t.category, t.name) for t in existing_rows}

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
                name="Stromausfall in Troisdorf",
                condition={"min_score": 50, "type": "outage"},
                score_contribution=30,
                notification_channels=["push", "telegram"],
                is_enabled=True,
            ),
            AlertThreshold(
                category=AlertCategory.POWER,
                name="Moeglicher Stromausfall Troisdorf (unbestaetigt)",
                condition={"min_score": 40, "type": "outage_unconfirmed"},
                score_contribution=15,
                notification_channels=["push"],
                is_enabled=True,
            ),
            AlertThreshold(
                category=AlertCategory.POWER,
                name="Grosslage im Rhein-Sieg-Kreis",
                condition={"min_score": 50, "type": "grosslage_kreis"},
                score_contribution=20,
                notification_channels=["push", "telegram"],
                is_enabled=True,
            ),
            AlertThreshold(
                category=AlertCategory.POWER,
                name="Extremlage ausserhalb des Kreises",
                condition={"min_score": 45, "type": "extremlage_ausserhalb"},
                score_contribution=10,
                notification_channels=["push"],
                is_enabled=True,
            ),
            AlertThreshold(
                category=AlertCategory.POWER,
                name="Stromnetz-Belastung (bundesweit)",
                condition={"min_score": 60, "type": "grid_stress"},
                score_contribution=10,
                notification_channels=["push"],
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
        added = 0
        for t in defaults:
            if (t.category, t.name) in known:
                continue
            session.add(t)
            added += 1

        if added:
            await session.commit()
            logger.info("Alert-Schwellenwerte ergaenzt: %s neu", added)
