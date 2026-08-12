"""Tests des Stromausfall-Collectors (Stoerungsauskunft der Netzbetreiber).

Diese Quelle liefert das, was SMARD nicht kann: konkrete Ausfaelle in der
Region. Kritisch sind drei Stellen — das Parsen der beiden unterschiedlichen
Koordinatenformate, das Buendeln der Buergermeldungen und das US-Datumsformat.
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.collectors.power.outage_collector import (
    CLUSTER_RADIUS_KM, MIN_CLUSTER_REPORTS, _haversine_km, cluster_reports,
    parse_api_date, parse_coordinates,
)

TROISDORF = (50.8159, 7.1533)


def test_confirmed_outage_coordinates_use_comma():
    """Bestaetigte Stoerungen liefern "laenge,breite"."""
    lat, lon = parse_coordinates("9.274755549999654,48.59601963848791")
    assert round(lat, 3) == 48.596
    assert round(lon, 3) == 9.275


def test_user_report_coordinates_use_semicolon():
    """Buergermeldungen liefern "laenge;breite" — anderes Trennzeichen."""
    lat, lon = parse_coordinates("6.863827;51.412495")
    assert round(lat, 3) == 51.412
    assert round(lon, 3) == 6.864


def test_coordinates_are_lon_lat_not_lat_lon():
    """Verwechslung wuerde Entfernungen voellig verfaelschen."""
    lat, lon = parse_coordinates("7.1533,50.8159")  # Troisdorf
    assert 50 < lat < 51, "Breite muss der zweite Wert sein"
    assert 7 < lon < 8


def test_implausible_coordinates_rejected():
    assert parse_coordinates("0,0") == (None, None)
    assert parse_coordinates("200,900") == (None, None)
    assert parse_coordinates("") == (None, None)
    assert parse_coordinates(None) == (None, None)
    assert parse_coordinates("kaputt") == (None, None)


def test_api_date_is_us_format():
    """08/12/2026 ist der 12. August, nicht der 8. Dezember."""
    dt = parse_api_date("08/12/2026 12:30:05")
    assert dt == datetime(2026, 8, 12, 12, 30, 5)


def test_bad_date_returns_none():
    assert parse_api_date("") is None
    assert parse_api_date(None) is None
    assert parse_api_date("12.08.2026") is None


def test_haversine_matches_known_distance():
    # Troisdorf -> Koeln sind rund 20 km Luftlinie
    d = _haversine_km(*TROISDORF, 50.9367, 6.9631)
    assert 15 < d < 25


def _report(lat, lon, dist, rid=1):
    return {"lat": lat, "lon": lon, "distance_km": dist, "row": {"id": rid}}


def test_nearby_reports_form_one_cluster():
    """Mehrere Meldungen aus einem Ort sind ein Ereignis, nicht viele."""
    reports = [
        _report(50.816, 7.153, 0.1, 1),
        _report(50.818, 7.155, 0.4, 2),
        _report(50.820, 7.150, 0.6, 3),
    ]
    clusters = cluster_reports(reports)
    assert len(clusters) == 1
    assert len(clusters[0]["members"]) == 3


def test_distant_reports_stay_separate():
    reports = [
        _report(50.816, 7.153, 0.1, 1),
        _report(51.412, 6.864, 70.0, 2),  # Muelheim, weit weg
    ]
    clusters = cluster_reports(reports)
    assert len(clusters) == 2


def test_cluster_keeps_nearest_distance():
    """Die Entfernung des Clusters ist die der naechstgelegenen Meldung."""
    reports = [
        _report(50.816, 7.153, 5.0, 1),
        _report(50.818, 7.155, 2.0, 2),
    ]
    clusters = cluster_reports(reports)
    assert clusters[0]["distance_km"] == 2.0


def test_single_report_is_below_cluster_threshold():
    """Eine einzelne Meldung kann eine Haussicherung sein — kein Signal."""
    clusters = cluster_reports([_report(50.816, 7.153, 0.1, 1)])
    assert len(clusters[0]["members"]) < MIN_CLUSTER_REPORTS


def test_cluster_radius_is_local():
    assert 0 < CLUSTER_RADIUS_KM <= 5, "Cluster duerfen nicht ganze Kreise umfassen"


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
