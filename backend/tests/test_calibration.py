"""Tests der Kalibrierungs-Mathematik.

Die reinen Rechenfunktionen sind bewusst DB-frei gehalten, damit die
Lernlogik ohne laufende Datenbank prüfbar ist.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.schemas import AlertCategory
from app.services.learning.calibration import (
    MAX_MULTIPLIER, MIN_MULTIPLIER, MIN_SAMPLES, _adjust, _compute_metrics,
)


def test_metrics_perfect():
    m = _compute_metrics(tp=10, pp=0, fp=0, fn=0)
    assert m["precision"] == 1.0
    assert m["recall"] == 1.0
    assert m["f1"] == 1.0


def test_partial_counts_half():
    # 2 Volltreffer + 2 Teiltreffer, keine Fehlalarme -> Precision 3/4
    m = _compute_metrics(tp=2, pp=2, fp=0, fn=0)
    assert m["precision"] == 0.75


def test_missed_deployments_lower_recall():
    m = _compute_metrics(tp=2, pp=0, fp=0, fn=8)
    assert m["recall"] == 0.2
    assert m["precision"] == 1.0


def test_no_adjustment_below_min_samples():
    metrics = _compute_metrics(tp=0, pp=0, fp=2, fn=0)
    mult, off, reason = _adjust(AlertCategory.WATER, 1.0, 0.0, metrics, samples=2)
    assert mult == 1.0
    assert off == 0.0
    assert "zu wenig" in reason.lower()


def test_missed_deployments_make_system_more_sensitive():
    # Viele verpasste Einsaetze -> Gewicht hoch, Schwelle runter
    metrics = _compute_metrics(tp=2, pp=0, fp=0, fn=8)
    mult, off, reason = _adjust(AlertCategory.WATER, 1.0, 0.0, metrics, samples=10)
    assert mult > 1.0, "Gewicht muss steigen, wenn Einsaetze verpasst werden"
    assert off < 0.0, "Schwelle muss sinken, damit frueher gewarnt wird"
    assert "zu selten" in reason


def test_false_alarms_make_system_more_conservative():
    metrics = _compute_metrics(tp=1, pp=0, fp=9, fn=0)
    mult, off, reason = _adjust(AlertCategory.TRAFFIC, 1.0, 0.0, metrics, samples=10)
    assert mult < 1.0, "Gewicht muss sinken bei vielen Fehlalarmen"
    assert off > 0.0, "Schwelle muss steigen bei vielen Fehlalarmen"
    assert "Fehlalarme" in reason


def test_safety_critical_never_damped():
    # Selbst bei reinen Fehlalarmen darf eine Behoerdenwarnung nicht
    # unempfindlicher werden als neutral.
    metrics = _compute_metrics(tp=0, pp=0, fp=20, fn=0)
    mult, off, reason = _adjust(AlertCategory.OFFICIAL_WARNING, 1.0, 0.0, metrics, samples=20)
    assert mult >= 1.0
    assert off <= 0.0
    assert "Sicherheitskritisch" in reason


def test_multiplier_stays_within_bounds_over_many_rounds():
    # Wiederholte Extremfaelle duerfen das System nicht davonlaufen lassen
    metrics = _compute_metrics(tp=0, pp=0, fp=0, fn=30)
    mult, off = 1.0, 0.0
    for _ in range(50):
        mult, off, _ = _adjust(AlertCategory.FIRE, mult, off, metrics, samples=30)
    assert MIN_MULTIPLIER <= mult <= MAX_MULTIPLIER
    assert -15.0 <= off <= 15.0


def test_adjustment_is_damped_not_instant():
    metrics = _compute_metrics(tp=0, pp=0, fp=0, fn=10)
    mult_after_one, _, _ = _adjust(AlertCategory.WEATHER, 1.0, 0.0, metrics, samples=10)
    # Eine einzelne Runde darf nur einen Teil des Weges gehen
    assert mult_after_one < 1.9


def test_good_performance_drifts_back_to_neutral():
    metrics = _compute_metrics(tp=9, pp=0, fp=1, fn=0)
    # Ausgangslage kuenstlich hoch -> muss Richtung 1.0 zurueckwandern
    mult, _, reason = _adjust(AlertCategory.WATER, 1.8, 0.0, metrics, samples=10)
    assert mult < 1.8
    assert "Ziele erreicht" in reason


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except Exception:
            failed += 1
            print(f"  FAIL  {t.__name__}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} Tests bestanden")
    sys.exit(1 if failed else 0)
