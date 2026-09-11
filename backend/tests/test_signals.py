"""Tests der abgeleiteten Signale und der Ortserkennung.

Die Ortserkennung ist die kritischste Stelle des ganzen Systems geworden:
Nachrichten wiegen seit der Profilkorrektur voll, und ob eine Meldung
Troisdorf oder Dueren meint, entscheidet ueber Alarm oder Ruhe. Ein Fehler
hier ist teurer als ein Fehler in jeder Kennzahl.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.knowledge.geo import (
    SCOPE_AUSSERHALB, SCOPE_KREIS, SCOPE_NACHBARSCHAFT, SCOPE_ORT,
    SCOPE_UNBEKANNT, detect_scope, is_local,
)
from app.services.knowledge.signals import (
    DAUER_SCHWELLE_STUNDEN, KRAEFTE_SCHWELLE, alle_signale, flaechenlage_signal,
    kampfmittel_signal, kombilage_signal, verpflegungsbedarf_signal,
)


def _news(text, score=50):
    """Lage mit einer einzelnen Nachrichtenmeldung."""
    return {"news": {"score": score, "detail": "1 relevante Nachricht",
                     "contributions": [{"reason": text}]}}


# Stichtag ohne laufende Grosslage. Ohne ihn haetten diese Tests je nach
# Kalendertag ein anderes Ergebnis — waehrend Puetzchens Markt laeuft, meldet
# sich das Grosslagen-Signal zusaetzlich.
RUHIGER_TAG = date(2026, 3, 15)


# --- Ortserkennung ---

def test_kerngebiet_wird_erkannt():
    assert detect_scope("Grossbrand in Troisdorf")["scope"] == SCOPE_ORT
    assert detect_scope("Sperrung in Siegburg")["scope"] == SCOPE_ORT


def test_deutsche_ableitungen_treffen():
    """"Troisdorfer Feuerwehr" ist in Schlagzeilen haeufiger als der blanke
    Ortsname. Ohne die Endungen bliebe die haeufigste Form unerkannt."""
    for text in ("Troisdorfer Feuerwehr im Einsatz",
                 "Der Siegburger Markt", "Duerener Lagerhalle brennt"):
        assert detect_scope(text)["ort"] is not None, text


def test_stadtteile_zaehlen_als_troisdorf():
    """Eine Meldung ueber Sieglar oder Spich meint Troisdorf."""
    for teil in ("Sieglar", "Spich", "Oberlar", "Kriegsdorf"):
        treffer = detect_scope(f"Feuer in {teil}")
        assert treffer["scope"] == SCOPE_ORT, teil
        assert "Troisdorf" in treffer["ort"]


def test_nachbarschaft_und_kreis_getrennt():
    assert detect_scope("Unfall in Lohmar")["scope"] == SCOPE_NACHBARSCHAFT
    assert detect_scope("Unfall in Windeck")["scope"] == SCOPE_KREIS


def test_ausserhalb_wird_als_solches_erkannt():
    """Der Fall Dueren — die Lage ist real, die Zustaendigkeit eine andere."""
    assert detect_scope("Grossbrand in Dueren")["scope"] == SCOPE_AUSSERHALB
    assert detect_scope("Chemieguertel Koeln")["scope"] == SCOPE_AUSSERHALB


def test_naehere_zustaendigkeit_gewinnt():
    """Werden zwei Orte genannt, zaehlt der naehere."""
    assert detect_scope("Kraefte aus Troisdorf helfen in Koeln")["scope"] == SCOPE_ORT


def test_keine_falschtreffer_in_laengeren_woertern():
    """Ohne strenge Wortgrenze vorne wuerde "Abonnement" als Bonn gelesen."""
    for text in ("Abonnement gekuendigt", "Verbrauch gestiegen",
                 "Die Buchhaltung meldet"):
        assert detect_scope(text)["scope"] == SCOPE_UNBEKANNT, text


def test_leerer_text_ist_unbekannt():
    assert detect_scope("")["scope"] == SCOPE_UNBEKANNT
    assert detect_scope(None)["scope"] == SCOPE_UNBEKANNT


def test_is_local_deckt_kerngebiet_und_nachbarschaft():
    assert is_local("Brand in Troisdorf")
    assert is_local("Brand in Hennef")
    assert not is_local("Brand in Windeck")
    assert not is_local("Brand in Dueren")


# --- Kampfmittel ---

def test_bombenfund_im_kerngebiet_wird_erkannt():
    signal = kampfmittel_signal(_news("Fliegerbombe in Siegburg gefunden"))
    assert signal is not None
    assert signal["ort"] == "Siegburg"


def test_bombenfund_ausserhalb_loest_nichts_aus():
    """Ein Bombenfund in Koeln ist Koelner Sache."""
    assert kampfmittel_signal(_news("Fliegerbombe in Koeln-Kalk gefunden")) is None


def test_kampfmittel_ohne_ort_loest_nichts_aus():
    assert kampfmittel_signal(_news("Fliegerbombe gefunden")) is None


def test_kampfmittel_in_der_nachbarschaft_zaehlt_auch():
    signal = kampfmittel_signal(_news("Blindgaenger in Niederkassel entdeckt"))
    assert signal is not None
    assert signal["zone"] == SCOPE_NACHBARSCHAFT


def test_verschiedene_schreibweisen_treffen():
    for text in ("Bombenfund in Troisdorf", "Entschaerfung in Troisdorf",
                 "Kampfmittel in Troisdorf", "Weltkriegsbombe in Troisdorf"):
        assert kampfmittel_signal(_news(text)) is not None, text


# --- Verpflegungsbedarf ---

def test_grosse_kraeftezahl_loest_verpflegungssignal_aus():
    signal = verpflegungsbedarf_signal(
        _news("Brand in Troisdorf: 120 Einsatzkraefte vor Ort"))
    assert signal is not None
    assert signal["kraefte"] == 120


def test_kleine_kraeftezahl_reicht_nicht():
    """Unter der Schwelle wird die Kueche erfahrungsgemaess nicht gerufen."""
    unter = KRAEFTE_SCHWELLE - 20
    signal = verpflegungsbedarf_signal(
        _news(f"Kleinbrand in Troisdorf: {unter} Einsatzkraefte vor Ort"))
    assert signal is None or signal["kraefte"] is None


def test_lange_dauer_loest_aus():
    signal = verpflegungsbedarf_signal(
        _news("Dauereinsatz der Feuerwehr in Troisdorf"))
    assert signal is not None


def test_stundenangabe_wird_gelesen():
    signal = verpflegungsbedarf_signal(
        _news("Loeschen in Siegburg dauert seit 6 Stunden an"))
    assert signal is not None
    assert signal["stunden"] == 6


def test_kurze_dauer_reicht_nicht():
    unter = DAUER_SCHWELLE_STUNDEN - 1
    signal = verpflegungsbedarf_signal(
        _news(f"Einsatz in Troisdorf nach {unter} Stunden beendet"))
    assert signal is None or signal["stunden"] is None


def test_lange_lage_ausserhalb_zaehlt_nicht():
    """Ein Grossbrand in Hamburg dauert genauso lange, geht Troisdorf aber
    nichts an."""
    assert verpflegungsbedarf_signal(
        _news("Grossbrand in Hamburg, 200 Einsatzkraefte")) is None


def test_hoechste_kraeftezahl_gewinnt():
    lage = {"news": {"score": 60, "detail": "2 Meldungen", "contributions": [
        {"reason": "Brand in Troisdorf: 60 Einsatzkraefte"},
        {"reason": "Brand in Troisdorf: 140 Einsatzkraefte nachgefordert"},
    ]}}
    assert verpflegungsbedarf_signal(lage)["kraefte"] == 140


def test_ruhige_lage_erzeugt_kein_signal():
    assert verpflegungsbedarf_signal(_news("Stadtfest in Troisdorf gut besucht")) is None


# --- Kombilage ---

def test_veranstaltung_mit_wetterlage():
    signal = kombilage_signal({"events": {"score": 55}, "weather": {"score": 62}})
    assert signal is not None


def test_veranstaltung_allein_reicht_nicht():
    assert kombilage_signal({"events": {"score": 80}, "weather": {"score": 10}}) is None


def test_wetter_allein_reicht_nicht():
    assert kombilage_signal({"events": {"score": 5}, "weather": {"score": 90}}) is None


def test_fehlende_kategorien_brechen_nicht():
    assert kombilage_signal({}) is None


# --- Zusammenspiel ---

def test_mehrere_signale_werden_gemeldet():
    lage = _news("Fliegerbombe in Troisdorf, 200 Einsatzkraefte im Dauereinsatz")
    lage["events"] = {"score": 50}
    lage["weather"] = {"score": 50}
    arten = {s["kind"] for s in alle_signale(lage, tag=RUHIGER_TAG)}
    assert arten == {"kampfmittel", "verpflegungsbedarf", "kombilage"}


def test_kampfmittel_steht_vor_den_anderen():
    """Wichtigstes zuerst — die Reihenfolge landet so in der Begruendung."""
    lage = _news("Fliegerbombe in Troisdorf, 200 Einsatzkraefte im Dauereinsatz")
    assert alle_signale(lage, tag=RUHIGER_TAG)[0]["kind"] == "kampfmittel"


def test_reihenfolge_der_signale_landet_so_in_der_begruendung():
    """Die Begruendung wird rueckwaerts aufgebaut.

    Jedes insert(0) draengt das Vorige nach hinten — ein Vorwaertslauf wuerde
    die Liste umdrehen und das wichtigste Signal ans Ende stellen. Genau das
    war eine Zeitlang der Fall.
    """
    from app.services.knowledge.assessment import assess_deployment
    lage = _news("Fliegerbombe in Troisdorf, 200 Einsatzkraefte im Dauereinsatz")
    lage["events"] = {"score": 50}
    lage["weather"] = {"score": 50}
    ergebnis = assess_deployment(lage, {}, tag=RUHIGER_TAG)

    reihenfolge = [s["kind"] for s in ergebnis["signals"]]
    assert reihenfolge[0] == "kampfmittel"
    # Der Hinweis des wichtigsten Signals steht auch in der Begruendung vorn
    # (nach dem Evakuierungshinweis, der immer Vorrang hat).
    kampfmittel_hinweis = ergebnis["signals"][0]["hinweis"]
    assert kampfmittel_hinweis in ergebnis["reasons"][:2]


def test_ruhige_lage_erzeugt_keine_signale():
    assert alle_signale({"news": {"score": 0}, "weather": {"score": 0}},
                        tag=RUHIGER_TAG) == []


def test_signale_heben_die_einsatzerwartung():
    from app.services.knowledge.assessment import assess_deployment
    ohne = assess_deployment(_news("Stadtfest in Troisdorf", score=40), {},
                             tag=RUHIGER_TAG)
    mit = assess_deployment(
        _news("Fliegerbombe in Troisdorf gefunden", score=40), {},
        tag=RUHIGER_TAG)
    assert mit["value"] > ohne["value"]
    assert mit["level"] == "einsatz_wahrscheinlich"


# --- Flaechenlage: der Bundesweite Warntag ---
#
# Gemeldet am 10.09.2026: Waehrend des Warntags stand das Gesamtrisiko auf 100,
# die Einsatzerwartung aber nur bei "koennte was sein". Ursache war die
# Ortsdaempfung, die "nicht lokal" und "weniger relevant" gleichsetzte — eine
# Warnung fuer ganz Deutschland ist aber nicht "woanders", sondern "ueberall,
# also auch hier".

def _amtliche_warnung(**kw):
    basis = {
        "score": 100, "detail": "1 aktive Warnungen",
        "area_scope": "flaechendeckend", "area": "Deutschland",
        "covers_us": True, "flaechendeckend": 1, "is_test": False,
        "max_severity": "Extreme", "max_urgency": "Immediate",
        "contributions": [],
    }
    basis.update(kw)
    return {"official_warning": basis}


def test_bundesweite_extremwarnung_loest_flaechenlage_aus():
    signal = flaechenlage_signal(_amtliche_warnung())
    assert signal is not None
    assert signal["gebiet"] == "Deutschland"


def test_flaechenlage_hebt_auf_vollalarm():
    """Der gemeldete Fall. Vorher blieb die Bewertung bei rund 51."""
    from app.services.knowledge.assessment import assess_deployment
    ergebnis = assess_deployment(_amtliche_warnung(), {}, tag=RUHIGER_TAG)
    assert ergebnis["level"] == "einsatz_wahrscheinlich"
    assert ergebnis["value"] >= 96


def test_probewarnung_alarmiert_genauso_wie_eine_echte_warnung():
    """GRUNDSATZ: Ein Probealarm wird behandelt wie ein Vollalarm.

    Der Bund sendet den Warntag bewusst mit status "Actual" und msgType
    "Alert" — damit die ganze Kette geprueft wird. Ein System, das an dieser
    Stelle unterscheidet, prueft sich selbst nicht und koennte im Ernstfall
    eine echte Warnung faelschlich fuer eine Uebung halten.
    """
    from app.services.knowledge.assessment import assess_deployment
    echt = assess_deployment(_amtliche_warnung(is_test=False), {},
                             tag=RUHIGER_TAG)
    probe = assess_deployment(_amtliche_warnung(is_test=True), {},
                              tag=RUHIGER_TAG)
    assert probe["value"] == echt["value"]
    assert probe["level"] == echt["level"] == "einsatz_wahrscheinlich"


def test_probewarnung_wird_im_wortlaut_erwaehnt():
    """Anzeigen ja, daempfen nein — der Nutzer soll lesen, was drinsteht."""
    signal = flaechenlage_signal(_amtliche_warnung(is_test=True))
    assert signal["ist_probewarnung"] is True
    assert "Probewarnung" in signal["hinweis"]
    assert "voller Staerke" in signal["hinweis"]


def test_warnung_fuer_fremden_kreis_loest_keine_flaechenlage_aus():
    """Der Fall Dueren bleibt, wie er war."""
    assert flaechenlage_signal(_amtliche_warnung(
        area_scope="ausserhalb", area="Kreis Dueren",
        covers_us=False, flaechendeckend=0)) is None


def test_leichte_flaechenwarnung_loest_nicht_aus():
    """Eine bundesweite Meldung geringer Schwere ist keine Extremlage."""
    assert flaechenlage_signal(_amtliche_warnung(max_severity="Minor")) is None
    assert flaechenlage_signal(_amtliche_warnung(max_severity="Moderate")) is None


def test_schwere_flaechenwarnung_reicht_bereits():
    assert flaechenlage_signal(_amtliche_warnung(max_severity="Severe")) is not None


def test_flaechenlage_ohne_warnungen_ist_still():
    assert flaechenlage_signal({}) is None
    assert flaechenlage_signal({"official_warning": None}) is None


def test_flaechenlage_steht_ganz_vorn():
    """Die deutlichste Lage gehoert in der Begruendung nach oben."""
    lage = _amtliche_warnung()
    lage["events"] = {"score": 60}
    lage["weather"] = {"score": 60}
    assert alle_signale(lage, tag=RUHIGER_TAG)[0]["kind"] == "flaechenlage"


def test_nrw_weite_warnung_deckt_troisdorf_ebenfalls():
    """Nicht nur bundesweit — auch eine Landeswarnung gilt hier."""
    from app.services.knowledge.geo import covers_troisdorf
    assert covers_troisdorf("Nordrhein-Westfalen")
    assert covers_troisdorf("Regierungsbezirk Köln")
    assert not covers_troisdorf("Regierungsbezirk Münster")


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
