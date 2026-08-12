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





# --- Filter-Zuordnung (empirisch gegen die Live-API verifiziert) ---

def test_wind_offshore_uses_verified_filter():
    """4169 ist ein Boersenpreis, kein Wind Offshore.

    Verifiziert: 4169 folgt dem Preisverlauf von Filter 252
    (300.2 -> 229.6 -> 190.7 -> 172.1 EUR/MWh), waehrend 124 die
    Offshore-Erzeugung liefert (970 -> 1120 -> 1217 -> 1281 MW).
    """
    from app.collectors.power.grid_collector import FILTER_GENERATION, FILTER_PRICE
    assert FILTER_GENERATION.get(124) == "Wind Offshore"
    assert 4169 not in FILTER_GENERATION, "Preisfilter darf nicht als Erzeugung zaehlen"
    assert FILTER_PRICE == 252


def test_no_phantom_total_generation_filter():
    """SMARD hat keinen Summenfilter — 4359 ist residuallast-artig."""
    from app.collectors.power.grid_collector import FILTER_GENERATION
    assert 4359 not in FILTER_GENERATION
    assert 4072 not in FILTER_GENERATION  # installierte Leistung, konstant


def test_renewables_exclude_storage():
    from app.collectors.power.grid_collector import FILTER_GENERATION, RENEWABLE_IDS
    assert 4070 not in RENEWABLE_IDS, "Pumpspeicher ist Speicher, kein EE-Erzeuger"
    assert RENEWABLE_IDS <= set(FILTER_GENERATION), "EE muessen Teil der Erzeugung sein"
    for fid in (1223, 4066, 4067, 124, 4068, 4069):
        assert fid in RENEWABLE_IDS


def test_generation_set_is_complete():
    """Die zwoelf SMARD-Erzeugungsarten; Summe deckte sich mit Prognose 122."""
    from app.collectors.power.grid_collector import FILTER_GENERATION
    assert len(FILTER_GENERATION) == 12
    for name in ("Photovoltaik", "Wind Onshore", "Wind Offshore", "Erdgas",
                 "Braunkohle", "Steinkohle", "Biomasse", "Wasserkraft"):
        assert name in FILTER_GENERATION.values()


def test_amprion_region_configured():
    """Troisdorf liegt in der Amprion-Regelzone."""
    from app.collectors.power.grid_collector import REGIONS
    assert "DE" in REGIONS
    assert "Amprion" in REGIONS


def test_value_at_or_before_falls_back():
    from app.collectors.power.grid_collector import _value_at_or_before
    series = {100: 1.0, 200: 2.0, 300: 3.0}
    assert _value_at_or_before(series, 200) == 2.0
    assert _value_at_or_before(series, 250) == 2.0, "faellt auf juengsten davor zurueck"
    assert _value_at_or_before(series, 50) is None
    assert _value_at_or_before(None, 200) is None


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
