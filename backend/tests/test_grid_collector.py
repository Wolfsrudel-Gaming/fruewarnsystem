"""Tests der Stromnetz-Bewertung.

Hintergrund: Ein falsch belegter SMARD-Filter ("Erzeugung gesamt", der in
Wahrheit eine residuallast-artige Groesse lieferte) erzeugte eine dauerhafte
Scheindeckungsluecke von ~37 GW und damit Dauer-Fehlalarme bis zur SMS-Stufe.
Diese Tests sichern die drei Stellen ab, die das verhindern: die
Plausibilitaetsgrenze, das Importanteil-Kriterium und die Zeitausrichtung.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.collectors.power.grid_collector import (
    MAX_PLAUSIBLE_BALANCE_MW, STALE_SERIES_TOLERANCE_MS,
    _align_to_common_timestamp, _assess_stress,
)

HOUR = 3600 * 1000
BASE_TS = 1_754_000_000_000


def test_export_is_not_stress():
    stressed, indicator = _assess_stress(balance_mw=1966, consumption_mw=56654, generation_mw=58620)
    assert stressed is False
    assert indicator is None


def test_routine_import_is_not_stress():
    # Deutschland importiert regelmaessig — 5% der Last sind Normalbetrieb
    stressed, _ = _assess_stress(balance_mw=-2800, consumption_mw=56000, generation_mw=53200)
    assert stressed is False


def test_high_import_share_is_stress():
    # 20% der Netzlast als Import -> ungewoehnlich, wird gemeldet
    stressed, indicator = _assess_stress(balance_mw=-11200, consumption_mw=56000, generation_mw=44800)
    assert stressed is True
    assert "Importbedarf" in indicator
    assert "20%" in indicator


def test_severe_import_labelled_differently():
    _, moderate = _assess_stress(-9800, 56000, 46200)      # 17.5%
    _, severe = _assess_stress(-16800, 56000, 39200)       # 30%
    assert "erhoehter" in moderate
    assert "hoher" in severe


def test_implausible_balance_never_raises_alarm():
    """Der eigentliche Bug: 37 GW Defizit sind physikalisch unmoeglich.

    Die Grenzkuppelstellen liegen bei rund 20 GW. Solche Werte koennen nur
    aus fehlerhaften Daten stammen und duerfen keinen Alarm ausloesen.
    """
    stressed, indicator = _assess_stress(
        balance_mw=-37282, consumption_mw=56654, generation_mw=19372
    )
    assert stressed is False, "Unplausible Daten duerfen keinen Alarm erzeugen"
    assert indicator is None


def test_plausibility_limit_is_below_the_old_bug_value():
    assert MAX_PLAUSIBLE_BALANCE_MW < 37282


def test_zero_consumption_is_handled():
    stressed, _ = _assess_stress(balance_mw=-100, consumption_mw=0, generation_mw=0)
    assert stressed is False


def test_alignment_picks_newest_common_timestamp():
    series = {
        410: {BASE_TS: 50000.0, BASE_TS + HOUR: 51000.0},
        4068: {BASE_TS: 20000.0, BASE_TS + HOUR: 25000.0, BASE_TS + 2 * HOUR: 30000.0},
    }
    aligned, ts = _align_to_common_timestamp(series)
    assert ts == BASE_TS + HOUR, "Muss den neuesten gemeinsamen Zeitpunkt nehmen"
    assert aligned[410] == 51000.0
    assert aligned[4068] == 25000.0


def test_retired_series_does_not_block_alignment():
    """Kernenergie endet mit dem Atomausstieg.

    Wuerde diese tote Reihe in den Schnitt einbezogen, gaebe es keinen
    gemeinsamen Zeitpunkt und der Collector lieferte dauerhaft nichts.
    """
    series = {
        410: {BASE_TS: 50000.0},
        4068: {BASE_TS: 30000.0},
        1224: {BASE_TS - 200 * 24 * HOUR: 0.0},  # vor Monaten eingestellt
    }
    aligned, ts = _align_to_common_timestamp(series)
    assert ts == BASE_TS
    assert 1224 not in aligned, "Eingestellte Reihe wird uebersprungen"
    assert aligned[410] == 50000.0


def test_alignment_returns_nothing_without_overlap():
    series = {
        410: {BASE_TS: 50000.0},
        4068: {BASE_TS + HOUR: 30000.0},
    }
    aligned, ts = _align_to_common_timestamp(series)
    assert aligned == {}
    assert ts is None


def test_stale_tolerance_allows_normal_publication_lag():
    # 3h Verzoegerung ist normal und darf nicht als eingestellt gelten
    series = {
        410: {BASE_TS: 50000.0, BASE_TS + 3 * HOUR: 52000.0},
        4067: {BASE_TS: 1000.0},
    }
    aligned, ts = _align_to_common_timestamp(series)
    assert 4067 in aligned, "3h Lag liegt innerhalb der Toleranz"
    assert ts == BASE_TS


def test_stale_tolerance_constant_is_sane():
    assert STALE_SERIES_TOLERANCE_MS == 48 * HOUR


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
