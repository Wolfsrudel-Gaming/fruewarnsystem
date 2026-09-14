"""Tests der Quellengesundheit.

Am 14.09.2026 kam beim Nachgehen eines Verpflegungs-Voralarms heraus: Acht
von sechzehn Nachrichtenquellen lieferten seit unbekannter Zeit nichts mehr.
Zwei Verlage hatten ihre Feeds abgeschaltet (HTTP 410), drei kommunale
Adressen waren umgezogen (404), eine antwortete mit HTTP 200 und einer leeren
Seite, eine war ueber TLS nicht erreichbar.

Zu sehen war davon nichts. Der Sammler uebersprang jede Quelle, die nicht mit
200 antwortete, und schrieb bestenfalls eine Protokollzeile. Nach aussen sah
das aus wie: keine Meldungen, also Ruhe.

Der Grundsatz, den diese Tests festhalten: EINE AUSGEFALLENE QUELLE IST KEINE
RUHE. Beide liefern nichts, aber das eine heisst "es ist nichts passiert" und
das andere "wir wuerden es nicht merken". Jeder Test unten bildet einen der
acht real aufgetretenen Ausfaelle ab.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.collectors.news.news_collector import AUSGEMUSTERT, RSS_FEEDS
from app.services.knowledge.quellen import (
    AUSGEFALLEN_AB_FEHLVERSUCHEN, AUSGEFALLEN_AB_STUNDEN, GEWICHT,
    STATUS_FEHLER, STATUS_OK, STATUS_STUMM, STATUS_UNBEKANNT,
    STATUS_UNERREICHBAR, STUFE_AUSGEFALLEN, STUFE_OK, STUFE_WACKELT,
    bewerte_abruf, bewerte_quelle, gesamtbild, ist_erfolg,
)

JETZT = datetime(2026, 9, 14, 17, 0)


def _quelle(name, stufe, bereich="kreis", gewicht=None):
    return {"name": name, "stufe": stufe, "bereich": bereich,
            "gewicht": gewicht if gewicht is not None else GEWICHT[bereich]}


# --- Der einzelne Abruf: die acht realen Faelle ---

def test_abruf_mit_eintraegen_ist_erfolg():
    assert bewerte_abruf(200, 20) == STATUS_OK
    assert ist_erfolg(STATUS_OK)


def test_zweihundert_ohne_eintraege_ist_kein_erfolg():
    """Der GEFAEHRLICHSTE Fall — real: GA Region Sieg und Rhein.

    Antwortete mit HTTP 200 und 830 Byte ohne einen einzigen Eintrag. Fuer
    jede Pruefung, die nur auf den Statuscode schaut, war diese Quelle
    kerngesund. Sie lieferte nur nie wieder etwas.
    """
    assert bewerte_abruf(200, 0) == STATUS_STUMM
    assert not ist_erfolg(STATUS_STUMM)


def test_abgeschalteter_feed_ist_fehler():
    """Real: Koelner Stadt-Anzeiger und Koelnische Rundschau, HTTP 410."""
    assert bewerte_abruf(410, 0) == STATUS_FEHLER


def test_umgezogene_adresse_ist_fehler():
    """Real: Stadt Troisdorf und Stadt Bonn, HTTP 404.

    Beide lieferten dabei eine grosse HTML-Fehlerseite — 642 KB im Fall
    Troisdorf. Wer auf die Antwortgroesse schaut statt auf die Eintraege,
    haelt das fuer eine besonders ergiebige Quelle.
    """
    assert bewerte_abruf(404, 0) == STATUS_FEHLER


def test_nicht_erreichbar_ist_eigener_status():
    """Real: Polizei Bonn ueber polizei.nrw — Verbindungsfehler, gar keine
    Antwort. Das ist etwas anderes als eine Fehlerantwort und muss
    unterscheidbar bleiben: Es kann auch am eigenen Netz liegen."""
    assert bewerte_abruf(fehler=RuntimeError("TLS")) == STATUS_UNERREICHBAR


def test_fehler_schlaegt_statuscode():
    """Wirft der Abruf eine Ausnahme, zaehlt das — auch wenn zufaellig noch
    ein alter Statuscode herumliegt."""
    assert bewerte_abruf(200, 20, fehler=RuntimeError("abgebrochen")) == \
        STATUS_UNERREICHBAR


def test_ohne_abruf_ist_unbekannt():
    assert bewerte_abruf(None, 0) == STATUS_UNBEKANNT


# --- Bewertung ueber die Zeit ---

def test_ein_einzelner_aussetzer_ist_noch_kein_ausfall():
    """Ein Netzwackler oder eine Wartung darf nicht sofort Alarm ausloesen —
    sonst ist die Meldung nach einer Woche nur noch Rauschen."""
    b = bewerte_quelle(STATUS_FEHLER, fehlversuche_in_folge=1,
                       letzter_erfolg=JETZT - timedelta(minutes=20),
                       jetzt=JETZT)
    assert b["stufe"] == STUFE_WACKELT


def test_mehrere_fehlversuche_in_folge_sind_ein_ausfall():
    b = bewerte_quelle(STATUS_FEHLER,
                       fehlversuche_in_folge=AUSGEFALLEN_AB_FEHLVERSUCHEN,
                       letzter_erfolg=JETZT - timedelta(hours=1), jetzt=JETZT)
    assert b["stufe"] == STUFE_AUSGEFALLEN


def test_lange_ohne_erfolg_ist_ausfall_auch_ohne_gezaehlte_fehlversuche():
    """Nach einem Neustart steht der Zaehler auf null. Eine Quelle, die seit
    einem Tag nichts geliefert hat, ist trotzdem tot."""
    b = bewerte_quelle(STATUS_FEHLER, fehlversuche_in_folge=0,
                       letzter_erfolg=JETZT - timedelta(
                           hours=AUSGEFALLEN_AB_STUNDEN + 1),
                       jetzt=JETZT)
    assert b["stufe"] == STUFE_AUSGEFALLEN


def test_noch_nie_geliefert_ist_sofort_ausfall():
    """Eine Quelle, die von Anfang an nichts bringt, ist falsch eingetragen.
    Das ist kein voruebergehender Aussetzer und darf nicht als solcher
    durchgehen."""
    b = bewerte_quelle(STATUS_FEHLER, fehlversuche_in_folge=1,
                       letzter_erfolg=None, jetzt=JETZT)
    assert b["stufe"] == STUFE_AUSGEFALLEN


def test_erfolg_setzt_die_stufe_zurueck():
    b = bewerte_quelle(STATUS_OK, fehlversuche_in_folge=0,
                       letzter_erfolg=JETZT, jetzt=JETZT)
    assert b["stufe"] == STUFE_OK


def test_hinweis_zur_stummen_quelle_warnt_ausdruecklich():
    """Der Text muss aussprechen, worin die Gefahr liegt — sonst liest
    jemand 'stumm' und denkt an Ruhe."""
    b = bewerte_quelle(STATUS_STUMM, fehlversuche_in_folge=5,
                       letzter_erfolg=JETZT - timedelta(hours=30), jetzt=JETZT)
    hinweis = b["hinweis"].lower()
    assert "ruhe" in hinweis and "blind" in hinweis


def test_hinweis_nennt_die_dauer():
    b = bewerte_quelle(STATUS_FEHLER, fehlversuche_in_folge=5,
                       letzter_erfolg=JETZT - timedelta(hours=30), jetzt=JETZT)
    assert "30" in b["hinweis"]


# --- Gewichtung: nicht jede Quelle wiegt gleich ---

def test_kerngebiet_wiegt_schwerer_als_bundesweit():
    """Eine tote Lokalquelle kostet Vorlaufzeit genau dort, wo das System sie
    liefern soll. Ein toter bundesweiter Ticker ist ersetzbar."""
    assert GEWICHT["kern"] > GEWICHT["kreis"] > GEWICHT["bundesweit"]


def test_ausfall_im_kerngebiet_ist_immer_kritisch():
    """Auch wenn sonst alles laeuft: Faellt die oertliche Quelle aus, ist
    genau der Bereich blind, auf den es ankommt."""
    quellen = [_quelle("GA Troisdorf", STUFE_AUSGEFALLEN, "kern")] + \
              [_quelle(f"bund{i}", STUFE_OK, "bundesweit") for i in range(10)]
    assert gesamtbild(quellen, JETZT)["stufe"] == "kritisch"


def test_einzelner_bundesweiter_ausfall_ist_nicht_kritisch():
    quellen = [_quelle("Presseportal", STUFE_AUSGEFALLEN, "bundesweit")] + \
              [_quelle(f"k{i}", STUFE_OK, "kern") for i in range(4)]
    assert gesamtbild(quellen, JETZT)["stufe"] == "beeintraechtigt"


def test_halbe_beobachtung_tot_ist_kritisch():
    """Der reale Stand am 14.09.2026: acht von sechzehn Quellen tot."""
    quellen = [_quelle(f"tot{i}", STUFE_AUSGEFALLEN, "kreis") for i in range(8)] + \
              [_quelle(f"ok{i}", STUFE_OK, "kreis") for i in range(8)]
    bild = gesamtbild(quellen, JETZT)
    assert bild["stufe"] == "kritisch"
    assert bild["ausgefallen"] == 8


def test_alles_gesund_meldet_ok():
    quellen = [_quelle(f"ok{i}", STUFE_OK, "kern") for i in range(5)]
    bild = gesamtbild(quellen, JETZT)
    assert bild["stufe"] == STUFE_OK and bild["blindanteil"] == 0.0


def test_gesamtbild_nennt_die_ausgefallenen_beim_namen():
    """Eine Zahl allein hilft niemandem beim Reparieren."""
    quellen = [_quelle("GA Siegburg", STUFE_AUSGEFALLEN, "kern"),
               _quelle("WDR", STUFE_OK, "kreis")]
    assert gesamtbild(quellen, JETZT)["namen_ausgefallen"] == ["GA Siegburg"]


def test_leere_quellenliste_bricht_nicht():
    bild = gesamtbild([], JETZT)
    assert bild["gesamt"] == 0 and bild["blindanteil"] == 0.0


# --- Die reparierte Quellenliste ---

def test_keine_ausgemusterte_quelle_steht_wieder_in_der_liste():
    """Die toten Quellen sind namentlich vermerkt, damit sie nicht
    versehentlich zurueckwandern."""
    aktiv = {f["name"] for f in RSS_FEEDS}
    assert not (aktiv & set(AUSGEMUSTERT)), \
        f"ausgemusterte Quelle wieder aktiv: {aktiv & set(AUSGEMUSTERT)}"


def test_jede_quelle_hat_einen_bereich():
    """Ohne Bereich laesst sich nicht gewichten, wie schwer ihr Ausfall
    wiegt."""
    for f in RSS_FEEDS:
        assert f.get("bereich") in GEWICHT, f"{f['name']}: {f.get('bereich')}"


def test_das_kerngebiet_ist_mehrfach_gedeckt():
    """Eine einzige Ortsquelle waere ein Einzelfehlerpunkt — genau das ist am
    14.09. passiert, als die Stadtquellen wegfielen."""
    kern = [f for f in RSS_FEEDS if f.get("bereich") == "kern"]
    assert len(kern) >= 3, f"nur {len(kern)} Quellen im Kerngebiet"


def test_ausgemusterte_quellen_nennen_den_grund():
    for name, grund in AUSGEMUSTERT.items():
        assert grund and len(grund) > 8, name


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
