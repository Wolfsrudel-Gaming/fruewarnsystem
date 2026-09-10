"""Tests der behoerdlichen Warnungen.

Zwei Faelle vom Bundesweiten Warntag 2026, beide am lebenden System geprueft:

* Die WARNUNG kam mit severity "Extreme", msgType "Alert", areaDesc
  "Deutschland" — und wurde von der Ortsdaempfung auf 51 heruntergerechnet,
  weil "nicht lokal" mit "weniger relevant" gleichgesetzt wurde. Eine
  flaechendeckende Warnung ist aber nicht "woanders", sondern "ueberall".
* Die ENTWARNUNG kam mit DERSELBEN severity "Extreme", nur msgType "Cancel".
  Wer allein die Schwere liest, alarmiert bei der Entwarnung genauso laut wie
  bei der Warnung.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.collectors.warnings.nina_collector import CANCEL_TYPES, _referenced_ids
from app.services.alert.alert_engine import _ist_entwarnung, _ist_probewarnung


class FakeWarnung:
    """Genuegend OfficialWarning-Oberflaeche fuer die Pruefungen."""

    def __init__(self, headline="", severity="Extreme", msg_type=None,
                 area="Deutschland", urgency="Immediate"):
        self.headline = headline
        self.severity = severity
        self.urgency = urgency
        self.area_description = area
        self.description = ""
        self.source_system = "mowas"
        self.effective = None
        self.raw_data = {"_msg_type": msg_type} if msg_type is not None else {}


# --- Entwarnung erkennen ---

def test_cancel_wird_als_entwarnung_erkannt():
    """Der Warntag-Fall: msgType Cancel bei unveraenderter Schwere."""
    w = FakeWarnung(
        headline="Entwarnung: Bundesweiter Warntag 2026 - Probewarnung - Deutschland",
        severity="Extreme", msg_type="Cancel")
    assert _ist_entwarnung(w)


def test_entwarnung_auch_ohne_msgtype_am_titel_erkannt():
    """Faellt der Nachrichtentyp aus, traegt der Titel die Information."""
    w = FakeWarnung(headline="Entwarnung: Unwetter Rhein-Sieg-Kreis",
                    msg_type=None)
    assert _ist_entwarnung(w)


def test_echte_warnung_ist_keine_entwarnung():
    w = FakeWarnung(
        headline="Bundesweiter Warntag 2026 - Probewarnung - Deutschland",
        severity="Extreme", msg_type="Alert")
    assert not _ist_entwarnung(w)


def test_update_ist_keine_entwarnung():
    """Eine fortgeschriebene Warnung bleibt eine Warnung."""
    w = FakeWarnung(headline="Unwetter — Aktualisierung", msg_type="Update")
    assert not _ist_entwarnung(w)


def test_wort_entwarnung_mitten_im_titel_zaehlt_nicht():
    """Nur ein Titel, der MIT "Entwarnung" beginnt, ist eine.

    Sonst wuerde "Keine Entwarnung in Sicht" die Lage aufheben — also genau
    das Gegenteil dessen, was die Meldung sagt.
    """
    w = FakeWarnung(headline="Keine Entwarnung in Sicht: Hochwasser haelt an",
                    msg_type="Alert")
    assert not _ist_entwarnung(w)


def test_alle_cancel_schreibweisen_treffen():
    for typ in ("Cancel", "cancel", "AllClear", "All Clear"):
        assert _ist_entwarnung(FakeWarnung(msg_type=typ)), typ


# --- Rueckverweise ---

def test_referenzen_werden_aus_dem_cap_feld_gelesen():
    """Echtes Feld der Warntag-Entwarnung."""
    roh = ("DE-BB-SC-SE009,mow.DE-BB-SC-SE009-20260910-9-001,"
           "2026-09-10T08:59:56-00:00")
    assert _referenced_ids(roh) == {"mow.DE-BB-SC-SE009-20260910-9-001"}


def test_mehrere_referenzen_werden_alle_gelesen():
    assert _referenced_ids("A,id-1,t1 B,id-2,t2") == {"id-1", "id-2"}


def test_leere_referenz_bricht_nicht():
    assert _referenced_ids("") == set()
    assert _referenced_ids(None) == set()
    assert _referenced_ids("kaputt") == set()


def test_cancel_typen_sind_kleingeschrieben_hinterlegt():
    """Der Vergleich erfolgt in Kleinschreibung — sonst greift er nie."""
    assert all(t == t.lower() for t in CANCEL_TYPES)


# --- Probewarnung ---

def test_probewarnung_wird_am_wortlaut_erkannt():
    assert _ist_probewarnung(
        "Bundesweiter Warntag 2026 - Probewarnung - Deutschland")
    assert _ist_probewarnung("", "Dies ist eine Übung", "")


def test_echte_lage_ist_keine_probewarnung():
    assert not _ist_probewarnung("Hochwasser an der Sieg", "Pegel steigt")


# --- Zusammenspiel: die Lage faellt nach der Entwarnung ---

def _lage(score, **kw):
    basis = {
        "score": score, "detail": "1 aktive Warnung",
        "area_scope": "flaechendeckend", "area": "Deutschland",
        "covers_us": True, "flaechendeckend": 1, "is_test": True,
        "cancelled": 0, "max_severity": "Extreme", "max_urgency": "Immediate",
        "contributions": [],
    }
    basis.update(kw)
    return {"official_warning": basis}


def test_lage_faellt_nach_der_entwarnung_auf_ruhe():
    """Der Kern: Eine Entwarnung geht runter, nicht rauf.

    Nach dem Cancel bleibt keine aktive Warnung uebrig — Score 0, kein
    Geltungsbereich, keine Flaechenlage.
    """
    from app.services.knowledge.assessment import assess_deployment

    waehrend = assess_deployment(_lage(100), {})
    danach = assess_deployment(_lage(
        0, covers_us=False, flaechendeckend=0, cancelled=1,
        max_severity=None, max_urgency=None, area_scope="unbekannt",
        detail="Keine aktive Warnung · 1 Entwarnung"), {})

    assert waehrend["level"] == "einsatz_wahrscheinlich"
    assert danach["level"] == "ruhe"
    assert danach["value"] < waehrend["value"]


def test_entwarnung_loest_keine_flaechenlage_aus():
    from app.services.knowledge.signals import flaechenlage_signal
    assert flaechenlage_signal(_lage(
        0, covers_us=False, flaechendeckend=0, cancelled=1,
        max_severity=None)) is None


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
