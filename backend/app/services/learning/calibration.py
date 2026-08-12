"""Selbstkalibrierung des Frühwarnsystems.

Aus den Rückmeldungen der Einsatzkräfte ("kam es zum Einsatz?") und den
nachgemeldeten Einsätzen ohne Alarm lernt das System pro Kategorie, wie
zuverlässig seine Warnungen sind, und passt Gewichtung und Auslöseschwelle
gedämpft an.

Grundsätze:
  * Recall wiegt schwerer als Precision — ein verpasster Einsatz ist
    schlimmer als ein Fehlalarm.
  * Angepasst wird nur gedämpft und begrenzt, damit einzelne Rückmeldungen
    das System nicht aus der Bahn werfen.
  * Sicherheitskritische Kategorien (behördliche Warnungen, Strahlung)
    werden nie gedämpft — sie können nur empfindlicher werden.
  * Jede Anpassung wird im Klartext begründet und ist damit nachvollziehbar.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from app.models.database import async_session
from app.models.schemas import (
    AlertCategory, AlertFeedback, CategoryCalibration, Deployment, FeedbackOutcome,
)

logger = logging.getLogger(__name__)

# Betrachtungszeitraum für die Statistik
WINDOW_DAYS = 180
# Erst ab so vielen bewertbaren Rückmeldungen wird überhaupt angepasst
MIN_SAMPLES = 5

# Zielwerte
TARGET_PRECISION = 0.60  # mind. 60% der Alarme sollen berechtigt sein
TARGET_RECALL = 0.85     # mind. 85% der echten Einsätze sollen vorgewarnt sein

# Wie stark eine Neuberechnung auf den Bestand wirkt (0..1)
DAMPING = 0.35

MIN_MULTIPLIER = 0.70
MAX_MULTIPLIER = 2.00
MAX_THRESHOLD_OFFSET = 15.0

# Diese Kategorien dürfen nie unempfindlicher werden als der Ausgangszustand
SAFETY_CRITICAL = {
    AlertCategory.OFFICIAL_WARNING,
    AlertCategory.RADIATION,
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _compute_metrics(tp: int, pp: int, fp: int, fn: int) -> dict:
    """Precision/Recall/F1. Teilerfolge (Vorsorge) zählen halb."""
    effective_tp = tp + 0.5 * pp
    predicted_positive = tp + pp + fp
    actual_positive = tp + pp + fn

    precision = effective_tp / predicted_positive if predicted_positive > 0 else None
    recall = effective_tp / actual_positive if actual_positive > 0 else None

    f1 = None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)

    return {"precision": precision, "recall": recall, "f1": f1}


def _adjust(
    category: AlertCategory,
    current_multiplier: float,
    current_offset: float,
    metrics: dict,
    samples: int,
) -> tuple:
    """Liefert (multiplier, offset, begruendung)."""
    precision = metrics["precision"]
    recall = metrics["recall"]

    if samples < MIN_SAMPLES:
        return (
            current_multiplier,
            current_offset,
            f"Noch zu wenig Rückmeldungen ({samples} von {MIN_SAMPLES}) — "
            f"keine Anpassung, System bleibt beim Ausgangswert.",
        )

    recall_gap = max(0.0, TARGET_RECALL - recall) if recall is not None else 0.0
    precision_gap = max(0.0, TARGET_PRECISION - precision) if precision is not None else 0.0

    # Recall-Lücke zieht das Gewicht hoch, Precision-Lücke drückt es runter.
    # Die Asymmetrie (1.0 vs. 0.5) ist gewollt: lieber ein Fehlalarm zu viel
    # als ein verpasster Einsatz.
    target_multiplier = 1.0 + 1.0 * recall_gap - 0.5 * precision_gap
    target_offset = 12.0 * precision_gap - 18.0 * recall_gap

    new_multiplier = current_multiplier + DAMPING * (target_multiplier - current_multiplier)
    new_offset = current_offset + DAMPING * (target_offset - current_offset)

    new_multiplier = _clamp(new_multiplier, MIN_MULTIPLIER, MAX_MULTIPLIER)
    new_offset = _clamp(new_offset, -MAX_THRESHOLD_OFFSET, MAX_THRESHOLD_OFFSET)

    if category in SAFETY_CRITICAL:
        # Nie unempfindlicher machen als neutral
        new_multiplier = max(1.0, new_multiplier)
        new_offset = min(0.0, new_offset)

    reasons = []
    if recall_gap > 0.01:
        reasons.append(
            f"Trefferquote {recall:.0%} unter Ziel {TARGET_RECALL:.0%} — "
            f"System warnt zu selten, wird empfindlicher"
        )
    if precision_gap > 0.01:
        reasons.append(
            f"Genauigkeit {precision:.0%} unter Ziel {TARGET_PRECISION:.0%} — "
            f"zu viele Fehlalarme, Schwelle wird angehoben"
        )
    if not reasons:
        reasons.append(
            f"Ziele erreicht (Genauigkeit {precision:.0%}, Trefferquote {recall:.0%}) — "
            f"Anpassung läuft langsam auf neutral zurück"
        )
    if category in SAFETY_CRITICAL:
        reasons.append("Sicherheitskritische Kategorie: Dämpfung ausgeschlossen")

    return new_multiplier, new_offset, " · ".join(reasons)


async def recompute_calibration(window_days: int = WINDOW_DAYS) -> dict:
    """Wertet alle Rückmeldungen aus und schreibt die Kalibrierung fort."""
    cutoff = datetime.utcnow() - timedelta(days=window_days)
    results = {}

    async with async_session() as session:
        feedback_rows = (await session.execute(
            select(AlertFeedback).where(AlertFeedback.created_at > cutoff)
        )).scalars().all()

        deployment_rows = (await session.execute(
            select(Deployment).where(Deployment.occurred_at > cutoff)
        )).scalars().all()

        existing = {
            c.category: c
            for c in (await session.execute(select(CategoryCalibration))).scalars().all()
        }

        # Zählwerke je Kategorie aufbauen
        counts = {}

        def bucket(cat):
            return counts.setdefault(cat, {"tp": 0, "pp": 0, "fp": 0, "fn": 0})

        for fb in feedback_rows:
            b = bucket(fb.category)
            if fb.outcome == FeedbackOutcome.EINSATZ:
                b["tp"] += 1
            elif fb.outcome == FeedbackOutcome.VORSORGE:
                b["pp"] += 1
            elif fb.outcome == FeedbackOutcome.KEIN_EINSATZ:
                b["fp"] += 1
            # UNKLAR fliesst bewusst nicht ein

        for dep in deployment_rows:
            if not dep.was_predicted:
                bucket(dep.category)["fn"] += 1

        for category, b in counts.items():
            metrics = _compute_metrics(b["tp"], b["pp"], b["fp"], b["fn"])
            samples = b["tp"] + b["pp"] + b["fp"] + b["fn"]

            cal = existing.get(category)
            if cal is None:
                cal = CategoryCalibration(category=category)
                session.add(cal)
                existing[category] = cal

            if cal.is_locked:
                reason = "Manuell fixiert — keine automatische Anpassung"
                new_mult, new_off = cal.weight_multiplier or 1.0, cal.threshold_offset or 0.0
            else:
                new_mult, new_off, reason = _adjust(
                    category,
                    cal.weight_multiplier if cal.weight_multiplier is not None else 1.0,
                    cal.threshold_offset if cal.threshold_offset is not None else 0.0,
                    metrics,
                    samples,
                )

            cal.weight_multiplier = round(new_mult, 3)
            cal.threshold_offset = round(new_off, 2)
            cal.true_positives = b["tp"]
            cal.partial_positives = b["pp"]
            cal.false_positives = b["fp"]
            cal.false_negatives = b["fn"]
            cal.precision = round(metrics["precision"], 3) if metrics["precision"] is not None else None
            cal.recall = round(metrics["recall"], 3) if metrics["recall"] is not None else None
            cal.f1_score = round(metrics["f1"], 3) if metrics["f1"] is not None else None
            cal.sample_count = samples
            cal.last_adjustment_reason = reason

            results[category.value] = {
                "weight_multiplier": cal.weight_multiplier,
                "threshold_offset": cal.threshold_offset,
                "precision": cal.precision,
                "recall": cal.recall,
                "samples": samples,
                "reason": reason,
            }

        await session.commit()

    logger.info(f"Kalibrierung neu berechnet für {len(results)} Kategorien")
    return results


async def get_calibration_map() -> dict:
    """Aktuelle Kalibrierung als {kategorie: {multiplier, offset}}.

    Wird beim Scoring und bei der Schwellenprüfung angewandt. Fällt bei
    Fehlern still auf neutral zurück — die Alarmierung darf nie an der
    Kalibrierung scheitern.
    """
    try:
        async with async_session() as session:
            rows = (await session.execute(select(CategoryCalibration))).scalars().all()
            return {
                r.category.value: {
                    "multiplier": r.weight_multiplier if r.weight_multiplier is not None else 1.0,
                    "offset": r.threshold_offset if r.threshold_offset is not None else 0.0,
                }
                for r in rows
            }
    except Exception as e:
        logger.error(f"Kalibrierung konnte nicht geladen werden, nutze neutrale Werte: {e}")
        return {}


async def get_quality_report() -> dict:
    """Gesamtbild der Systemgüte für die App."""
    async with async_session() as session:
        cals = (await session.execute(select(CategoryCalibration))).scalars().all()

        total_tp = sum(c.true_positives or 0 for c in cals)
        total_pp = sum(c.partial_positives or 0 for c in cals)
        total_fp = sum(c.false_positives or 0 for c in cals)
        total_fn = sum(c.false_negatives or 0 for c in cals)

        overall = _compute_metrics(total_tp, total_pp, total_fp, total_fn)
        samples = total_tp + total_pp + total_fp + total_fn

        # Offene Alarme ohne Rückmeldung — die Lernlücke
        feedback_alert_ids = {
            r[0] for r in (await session.execute(select(AlertFeedback.alert_id))).all()
        }

        return {
            "overall": {
                "precision": round(overall["precision"], 3) if overall["precision"] is not None else None,
                "recall": round(overall["recall"], 3) if overall["recall"] is not None else None,
                "f1": round(overall["f1"], 3) if overall["f1"] is not None else None,
                "true_positives": total_tp,
                "partial_positives": total_pp,
                "false_positives": total_fp,
                "false_negatives": total_fn,
                "sample_count": samples,
                "maturity": _maturity_label(samples),
            },
            "categories": [
                {
                    "category": c.category.value,
                    "weight_multiplier": c.weight_multiplier,
                    "threshold_offset": c.threshold_offset,
                    "precision": c.precision,
                    "recall": c.recall,
                    "f1_score": c.f1_score,
                    "true_positives": c.true_positives,
                    "partial_positives": c.partial_positives,
                    "false_positives": c.false_positives,
                    "false_negatives": c.false_negatives,
                    "sample_count": c.sample_count,
                    "is_locked": c.is_locked,
                    "reason": c.last_adjustment_reason,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                }
                for c in sorted(cals, key=lambda x: -(x.sample_count or 0))
            ],
            "feedback_given": len(feedback_alert_ids),
            "min_samples_for_learning": MIN_SAMPLES,
            "target_precision": TARGET_PRECISION,
            "target_recall": TARGET_RECALL,
        }


def _maturity_label(samples: int) -> str:
    if samples == 0:
        return "Noch keine Rückmeldungen"
    if samples < MIN_SAMPLES:
        return "Sammelt Daten"
    if samples < 20:
        return "Erste Anpassungen aktiv"
    if samples < 60:
        return "Eingespielt"
    return "Gut kalibriert"
