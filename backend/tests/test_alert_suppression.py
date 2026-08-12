"""Tests der Wiederholungssperre für Alarme.

Hintergrund: Vorher wurde ein bestehender Alarm nur eine Stunde lang als
Duplikat erkannt. Bei einem Collector-Takt von fünf Minuten meldete eine
unverändert anhaltende Lage über zwölf Stunden also zwölfmal — und der
Abgleich lief pro Kategorie statt pro Schwelle, sodass ein Alarm alle
übrigen Schwellen derselben Kategorie blockierte.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.alert.alert_engine import (
    RENOTIFY_COOLDOWN, RESOLVE_HYSTERESIS, SIGNIFICANT_RISE,
    _last_notified_at, decide_alert_action,
)

NOW = datetime(2026, 8, 12, 12, 0, 0)


def _running(score, level=None, notified_minutes_ago=30):
    """Laufender Alarm. Die Stufe leitet sich aus dem Score ab — ein Alarm
    mit Score 65 steht zwangslaeufig auf Stufe 2."""
    from app.services.alert.alert_engine import _escalation_level_for_score
    return {
        "score": score,
        "escalation_level": level if level is not None else _escalation_level_for_score(score),
        "last_notified": NOW - timedelta(minutes=notified_minutes_ago),
    }


def test_first_time_creates_alert():
    action, _ = decide_alert_action(True, 65, 50, None, NOW)
    assert action == "create"


def test_below_threshold_without_alert_does_nothing():
    action, _ = decide_alert_action(False, 20, 50, None, NOW)
    assert action == "none"


def test_identical_values_do_not_renotify():
    """Der eigentliche Punkt: gleicher Wert -> keine neue Meldung."""
    action, reason = decide_alert_action(True, 65, 50, _running(65), NOW)
    assert action == "silent_update"
    assert "unveraendert" in reason


def test_hundred_identical_runs_notify_exactly_once():
    """Ein anhaltender Zustand darf genau einmal melden."""
    running = None
    notifications = 0
    for _ in range(100):
        action, _ = decide_alert_action(True, 65, 50, running, NOW)
        if action in ("create", "notify_update"):
            notifications += 1
            running = _running(65, level=2, notified_minutes_ago=0)
    assert notifications == 1, "Nur der erste Lauf darf benachrichtigen"


def test_small_fluctuation_stays_silent():
    # Score pendelt um wenige Punkte — das ist keine neue Lage
    for score in (63, 67, 61, 69):
        action, _ = decide_alert_action(True, score, 50, _running(65), NOW)
        assert action == "silent_update", f"Score {score} sollte still bleiben"


def test_significant_rise_notifies_again():
    """Deutlicher Anstieg innerhalb derselben Eskalationsstufe.

    30 -> 45 bleibt Stufe 1, greift also nicht ueber die Stufenregel, sondern
    ueber den Score-Anstieg — sofern die Sperrzeit abgelaufen ist.
    """
    cooled = int(RENOTIFY_COOLDOWN.total_seconds() / 60) + 10
    action, reason = decide_alert_action(
        True, 30 + SIGNIFICANT_RISE + 5, 25,
        _running(30, notified_minutes_ago=cooled),
        NOW,
    )
    assert action == "notify_update"
    assert "Verschaerfung" in reason


def test_significant_rise_within_cooldown_stays_silent():
    """Auch ein Anstieg darf nicht sofort erneut wecken."""
    action, reason = decide_alert_action(
        True, 80, 50, _running(65, level=3, notified_minutes_ago=10), NOW
    )
    assert action == "silent_update"
    assert "Sperrzeit" in reason


def test_escalation_level_rise_always_notifies():
    """Neue Eskalationsstufe heisst neue Kanaele — das muss durch die Sperrzeit.

    Score 65 (Stufe 2) steigt auf 88 (Stufe 4: zusaetzlich SMS und E-Mail),
    obwohl erst vor fuenf Minuten gemeldet wurde.
    """
    action, reason = decide_alert_action(
        True, 88, 50, _running(65, level=2, notified_minutes_ago=5), NOW
    )
    assert action == "notify_update"
    assert "Eskalationsstufe" in reason


def test_falling_score_resolves_alert():
    action, reason = decide_alert_action(
        False, 50 - RESOLVE_HYSTERESIS - 1, 50, _running(65), NOW
    )
    assert action == "resolve"
    assert "beendet" in reason


def test_hysteresis_prevents_flapping():
    """Knapp unter der Schwelle bleibt der Alarm bestehen."""
    action, _ = decide_alert_action(False, 48, 50, _running(65), NOW)
    assert action == "silent_update"


def test_flapping_around_threshold_notifies_once():
    """Ein um die Schwelle pendelnder Score darf nicht dauernd neu alarmieren."""
    running = None
    notifications = 0
    for score in [52, 48, 51, 49, 53, 47, 52] * 5:
        met = score >= 50
        action, _ = decide_alert_action(met, score, 50, running, NOW)
        if action == "create":
            notifications += 1
            running = _running(score, notified_minutes_ago=0)
        elif action == "notify_update":
            notifications += 1
        elif action == "resolve":
            running = None
    assert notifications == 1, f"Erwartet 1 Meldung, waren {notifications}"


def test_resolved_alert_can_trigger_again_later():
    """Nach Entwarnung muss ein neues Ereignis wieder melden duerfen."""
    action, _ = decide_alert_action(False, 30, 50, _running(65), NOW)
    assert action == "resolve"
    # Spaeter tritt die Lage erneut auf — kein laufender Alarm mehr
    action, _ = decide_alert_action(True, 70, 50, None, NOW + timedelta(hours=3))
    assert action == "create"


def test_last_notified_reads_protocol():
    log = [
        {"at": "2026-08-12T08:00:00", "channels": ["ntfy"]},
        {"at": "2026-08-12T11:30:00", "channels": ["ntfy", "telegram"]},
    ]
    assert _last_notified_at(log) == datetime(2026, 8, 12, 11, 30, 0)


def test_last_notified_handles_broken_protocol():
    assert _last_notified_at(None) is None
    assert _last_notified_at([]) is None
    assert _last_notified_at(["kaputt"]) is None
    assert _last_notified_at([{"at": "keine-zeit"}]) is None


def test_constants_are_sane():
    assert SIGNIFICANT_RISE >= 5, "Zu kleine Schwelle wuerde wieder spammen"
    assert RENOTIFY_COOLDOWN >= timedelta(hours=1)
    assert 0 < RESOLVE_HYSTERESIS < 20


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
