"""Tests des Aufraeumens gewachsener Datenbestaende.

Hintergrund sind zwei behobene Fehler, die ueber Wochen Duplikate erzeugt
haben:

* Der DWD-Collector legte jede Warnung bei jedem Lauf neu an. Vier gueltige
  Warnungen wurden binnen sechs Stunden zu 288 Zeilen.
* Die Alarm-Dedup schaute nur eine Stunde zurueck und loeste dieselbe Lage
  danach immer wieder neu aus — 53 offene Rueckmeldungen fuer eine Handvoll
  tatsaechlicher Ereignisse.

Geprueft wird ausserdem die Folge des Upserts: Warnungen werden nicht mehr
bei jedem Lauf neu geschrieben, also darf das Scoring nicht laenger ueber
``created_at`` filtern.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.alert.alert_engine import (
    WARNING_LOOKAHEAD, WARNING_MAX_AGE, is_warning_active,
)
from app.services.maintenance import (
    EPISODE_GAP, _weather_key, group_weather_duplicates, plan_alert_episodes,
)

NOW = datetime(2026, 8, 14, 12, 0, 0)


class FakeWarning:
    """Genuegend WeatherData-Oberflaeche fuer die Gruppierung."""

    def __init__(self, parameters=None, region=None, title=None,
                 valid_from=None, valid_to=None, severity=0):
        self.parameters = parameters
        self.region = region
        self.title = title
        self.valid_from = valid_from
        self.valid_to = valid_to
        self.severity = severity


class FakeAlert:
    def __init__(self, id, category, threshold=None, triggered_at=None,
                 score=60.0, title=None):
        self.id = id
        self.category = category
        self.threshold_config = {"_threshold": threshold} if threshold else None
        self.triggered_at = triggered_at
        self.created_at = triggered_at
        self.score = score
        self.title = title
        self.escalation_level = 1
        self.is_active = True
        self.resolved_at = None


# --- Wetterwarnungen: Duplikate erkennen ---

def test_identical_warning_from_many_runs_forms_one_group():
    """Der gemeldete Fall: 72 Laeufe x 4 Warnungen = 288 Zeilen."""
    rows = []
    for _run in range(72):
        for event in ("Hitze", "UV", "Gewitter", "Starkregen"):
            rows.append(FakeWarning(parameters={
                "_key": f"105382000|{event}|start|ende|Wetter",
            }))

    groups = group_weather_duplicates(rows)
    assert len(groups) == 4
    assert all(len(g) == 72 for g in groups.values())


def test_legacy_rows_without_key_are_reconstructed():
    """Zeilen aus der Zeit vor dem Upsert tragen keinen _key."""
    start = NOW
    end = NOW + timedelta(hours=6)
    rows = [
        FakeWarning(parameters={"warncell_id": "105382000", "event": "Hitze"},
                    valid_from=start, valid_to=end)
        for _ in range(5)
    ]
    groups = group_weather_duplicates(rows)
    assert len(groups) == 1


def test_legacy_and_new_row_of_same_warning_do_not_merge_wrongly():
    """Altzeile und Neuzeile derselben Warnung erzeugen denselben Schluessel.

    Der rekonstruierte Schluessel nutzt bewusst dieselben Bestandteile wie der
    Collector, damit ein Altbestand nicht neben seinem Nachfolger stehenbleibt.
    """
    start = NOW
    end = NOW + timedelta(hours=6)
    legacy = FakeWarning(
        parameters={"warncell_id": "105382000", "event": "Hitze"},
        valid_from=start, valid_to=end,
    )
    assert _weather_key(legacy).startswith("105382000|Hitze|")


def test_different_events_stay_separate():
    rows = [
        FakeWarning(parameters={"_key": "105382000|Hitze|a|b|Wetter"}),
        FakeWarning(parameters={"_key": "105382000|Gewitter|a|b|Wetter"}),
    ]
    assert len(group_weather_duplicates(rows)) == 2


def test_same_event_different_validity_is_a_new_warning():
    """Eine verlaengerte Hitzewarnung ist eine neue Warnung, kein Duplikat."""
    rows = [
        FakeWarning(parameters={"warncell_id": "1", "event": "Hitze"},
                    valid_from=NOW, valid_to=NOW + timedelta(hours=6)),
        FakeWarning(parameters={"warncell_id": "1", "event": "Hitze"},
                    valid_from=NOW + timedelta(days=1),
                    valid_to=NOW + timedelta(days=1, hours=6)),
    ]
    assert len(group_weather_duplicates(rows)) == 2


def test_group_order_preserves_oldest_first():
    """Die aelteste Zeile bleibt stehen — sie traegt den echten Erstkontakt."""
    rows = [FakeWarning(parameters={"_key": "k"}, severity=n) for n in (20, 40, 60)]
    group = group_weather_duplicates(rows)["k"]
    assert group[0].severity == 20
    assert group[-1].severity == 60


# --- Gueltigkeitsfenster statt created_at ---

def test_running_warning_counts_regardless_of_age():
    """Kernpunkt: Eine seit Tagen laufende Warnung darf nicht herausfallen.

    Vor dem Upsert hielt das staendige Neuanlegen created_at frisch. Wuerde das
    Scoring weiter darueber filtern, verschwaende eine mehrtaegige Hitzewarnung
    nach sechs Stunden lautlos aus der Lage.
    """
    assert is_warning_active(
        valid_from=NOW - timedelta(days=2),
        valid_to=NOW + timedelta(days=1),
        created_at=NOW - timedelta(days=2),
        now=NOW,
    )


def test_expired_warning_drops_out():
    assert not is_warning_active(
        valid_from=NOW - timedelta(days=2),
        valid_to=NOW - timedelta(hours=1),
        created_at=NOW - timedelta(minutes=5),
        now=NOW,
    )


def test_warning_starting_soon_already_counts():
    """Vorlauf ist der Sinn der Sache — eine Warnung fuer heute Abend zaehlt."""
    assert is_warning_active(
        valid_from=NOW + timedelta(hours=8),
        valid_to=NOW + timedelta(hours=20),
        created_at=NOW,
        now=NOW,
    )


def test_warning_far_in_the_future_does_not_count_yet():
    assert not is_warning_active(
        valid_from=NOW + WARNING_LOOKAHEAD + timedelta(hours=1),
        valid_to=NOW + timedelta(days=3),
        created_at=NOW,
        now=NOW,
    )


def test_warning_without_end_falls_back_to_age_limit():
    fresh = is_warning_active(None, None, NOW - timedelta(hours=2), now=NOW)
    stale = is_warning_active(None, None, NOW - WARNING_MAX_AGE - timedelta(hours=1), now=NOW)
    assert fresh and not stale


# --- Alarme: Wiederholungen zu Episoden buendeln ---

def _series(count, start, step, category="weather", threshold="Hitze", first_id=1):
    return [
        FakeAlert(id=first_id + n, category=category, threshold=threshold,
                  triggered_at=start + step * n)
        for n in range(count)
    ]


def test_hourly_repeats_of_one_situation_collapse_to_one_episode():
    """Der gemeldete Fall: 53 offene Rueckmeldungen fuer eine Lage."""
    alerts = _series(53, NOW - timedelta(hours=53), timedelta(hours=1))
    plan = plan_alert_episodes(alerts)
    assert len(plan) == 1
    representative, repeats = plan[0]
    assert representative.id == alerts[0].id
    assert len(repeats) == 52


def test_separate_situations_stay_separate():
    """Zwei Lagen mit deutlichem Abstand bleiben zwei Ereignisse."""
    first = _series(3, NOW - timedelta(days=5), timedelta(hours=1), first_id=1)
    second = _series(3, NOW - timedelta(days=1), timedelta(hours=1), first_id=10)
    plan = plan_alert_episodes(first + second)
    assert len(plan) == 2
    assert {p[0].id for p in plan} == {1, 10}


def test_gap_boundary_belongs_to_the_same_episode():
    """Genau am Abstand liegt noch dieselbe Lage, eine Sekunde spaeter nicht."""
    inside = [
        FakeAlert(1, "weather", "Hitze", NOW),
        FakeAlert(2, "weather", "Hitze", NOW + EPISODE_GAP),
    ]
    outside = [
        FakeAlert(1, "weather", "Hitze", NOW),
        FakeAlert(2, "weather", "Hitze", NOW + EPISODE_GAP + timedelta(seconds=1)),
    ]
    assert len(plan_alert_episodes(inside)) == 1
    assert len(plan_alert_episodes(outside)) == 2


def test_chain_of_close_alerts_stays_one_episode():
    """Der Abstand gilt zum Vorgaenger, nicht zum Episodenbeginn.

    Sonst wuerde eine Dauerlage, die alle fuenf Minuten nachfeuert, nach sechs
    Stunden kuenstlich in eine zweite Episode zerfallen.
    """
    alerts = _series(200, NOW, timedelta(minutes=5))
    assert len(plan_alert_episodes(alerts)) == 1


def test_different_categories_never_mix():
    alerts = [
        FakeAlert(1, "weather", "Hitze", NOW),
        FakeAlert(2, "power", "Stromausfall", NOW + timedelta(minutes=5)),
        FakeAlert(3, "weather", "Hitze", NOW + timedelta(minutes=10)),
    ]
    plan = plan_alert_episodes(alerts)
    assert len(plan) == 2
    ids = {p[0].id: [r.id for r in p[1]] for p in plan}
    assert ids[1] == [3]
    assert ids[2] == []


def test_different_thresholds_of_one_category_stay_separate():
    alerts = [
        FakeAlert(1, "weather", "Hitzewarnung", NOW),
        FakeAlert(2, "weather", "Unwetterwarnung", NOW + timedelta(minutes=5)),
    ]
    assert len(plan_alert_episodes(alerts)) == 2


def test_answered_alert_is_left_alone():
    """Ein abgegebenes Urteil wird nicht nachtraeglich einkassiert."""
    alerts = _series(4, NOW, timedelta(hours=1))
    plan = plan_alert_episodes(alerts, answered_ids={alerts[2].id})
    _, repeats = plan[0]
    assert alerts[2].id not in [r.id for r in repeats]
    assert len(repeats) == 2


def test_answered_alert_still_holds_the_episode_together():
    """Auch ein beantworteter Alarm haelt die Kette — er verschiebt last_seen."""
    alerts = [
        FakeAlert(1, "weather", "Hitze", NOW),
        FakeAlert(2, "weather", "Hitze", NOW + timedelta(hours=5)),
        FakeAlert(3, "weather", "Hitze", NOW + timedelta(hours=10)),
    ]
    plan = plan_alert_episodes(alerts, answered_ids={2})
    assert len(plan) == 1
    assert [r.id for r in plan[0][1]] == [3]


def test_single_alert_is_its_own_episode_without_repeats():
    plan = plan_alert_episodes([FakeAlert(1, "weather", "Hitze", NOW)])
    assert len(plan) == 1 and plan[0][1] == []


def test_empty_input_is_handled():
    assert plan_alert_episodes([]) == []


def test_alert_without_timestamp_does_not_swallow_others():
    """Ohne Zeitstempel laesst sich keine Episode bilden."""
    alerts = [
        FakeAlert(1, "weather", "Hitze", None),
        FakeAlert(2, "weather", "Hitze", NOW),
    ]
    assert len(plan_alert_episodes(alerts)) == 2


def test_legacy_alert_is_matched_by_title():
    """Alarme aus der Zeit vor threshold_config werden ueber den Titel zugeordnet."""
    a = FakeAlert(1, "weather", None, NOW, title="Hitzewarnung: 38 Grad erwartet")
    b = FakeAlert(2, "weather", None, NOW + timedelta(hours=1),
                  title="Hitzewarnung: 39 Grad erwartet")
    plan = plan_alert_episodes([a, b])
    assert len(plan) == 1
    assert [r.id for r in plan[0][1]] == [2]


def test_cleanup_is_idempotent_on_already_collapsed_data():
    """Ein zweiter Lauf darf nichts mehr finden.

    Nach dem Aufraeumen bleibt je Episode ein Vertreter — laesst man den Plan
    erneut ueber genau diese Vertreter laufen, entstehen keine Wiederholungen.
    """
    alerts = _series(20, NOW, timedelta(hours=1))
    survivors = [rep for rep, _ in plan_alert_episodes(alerts)]
    second = plan_alert_episodes(survivors)
    assert all(repeats == [] for _, repeats in second)


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
