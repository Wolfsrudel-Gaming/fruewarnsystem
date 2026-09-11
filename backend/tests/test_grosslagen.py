"""Tests der bekannten Grosslagen.

Eingepflegt am 11.09.2026, waehrend Puetzchens Markt lief.

Der Kern ist nicht der Termin, sondern die GRUNDLAST. Eine Grossveranstaltung
erzeugt im Normalbetrieb eine hohe, aber erwartbare Zahl an Hilfeleistungen.
Ohne dieses Wissen liest ein Fruehwarnsystem "Rettungsdienst im Dauereinsatz
auf Puetzchens Markt" als Eskalation — dabei beschreibt die Schlagzeile den
Normalzustand.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.knowledge.grosslagen import (
    ABTASTUNG_ERHOEHT, AUFFAELLIG_AB_FAKTOR, GROSSLAGEN, WACHSAME_ZONEN,
    WACHSAMKEIT_ERHOEHT, WACHSAMKEIT_NORMAL, aktive_grosslagen,
    bevorstehende_grosslagen, grundlast_text, ist_auffaellig, ist_wachsam,
    wachsamkeitsstufe,
)
from app.services.knowledge.signals import grosslage_signal

MARKT = GROSSLAGEN[0]


# --- Termin: die Regel muss jedes Jahr stimmen ---

def test_termin_2026_entspricht_der_amtlichen_ankuendigung():
    """Amtlich: 11. bis 15. September 2026, 657. Auflage."""
    beginn, ende = MARKT["termin"](2026)
    assert beginn == date(2026, 9, 11)
    assert ende == date(2026, 9, 15)


def test_termin_2025_entspricht_der_amtlichen_bilanz():
    """Die Bilanz 2025 nennt das Abschlussfeuerwerk am Dienstag, 16.09."""
    beginn, ende = MARKT["termin"](2025)
    assert beginn == date(2025, 9, 12)
    assert ende == date(2025, 9, 16)


def test_termin_2024_stimmt_ebenfalls():
    assert MARKT["termin"](2024) == (date(2024, 9, 6), date(2024, 9, 10))


def test_termin_dauert_immer_fuenf_tage():
    for jahr in range(2024, 2036):
        beginn, ende = MARKT["termin"](jahr)
        assert (ende - beginn).days == 4, jahr
        assert beginn.weekday() == 4, f"{jahr}: Beginn ist kein Freitag"
        assert ende.weekday() == 1, f"{jahr}: Ende ist kein Dienstag"


# --- Laufende und bevorstehende Lagen ---

def test_erster_und_letzter_tag_zaehlen_mit():
    assert aktive_grosslagen(date(2026, 9, 11))
    assert aktive_grosslagen(date(2026, 9, 15))
    assert not aktive_grosslagen(date(2026, 9, 10))
    assert not aktive_grosslagen(date(2026, 9, 16))


def test_tagzaehlung_stimmt():
    lage = aktive_grosslagen(date(2026, 9, 13))[0]
    assert lage["tag_nummer"] == 3
    assert lage["tage_gesamt"] == 5


def test_vorlauf_wird_erkannt():
    bevor = bevorstehende_grosslagen(date(2026, 9, 5))
    assert bevor and bevor[0]["in_tagen"] == 6


def test_kein_vorlauf_waehrend_die_lage_laeuft():
    """Sonst meldete die App Beginn und Verlauf gleichzeitig."""
    assert bevorstehende_grosslagen(date(2026, 9, 12)) == []


def test_jahreswechsel_wird_beruecksichtigt():
    """Im Dezember steht die naechste Lage im Folgejahr."""
    bevor = bevorstehende_grosslagen(date(2026, 12, 20), vorlauf_tage=400)
    assert bevor and bevor[0]["beginn"].year == 2027


# --- Grundlast: der eigentliche Wert dieses Wissens ---

def test_normale_zahlen_sind_nicht_auffaellig():
    """2025 amtlich: rund 180 Behandlungen, 48 Transporte, 8 Notarzteinsaetze.

    Genau das ist der Normalbetrieb — und darf keinen Alarm erzeugen.
    """
    assert not ist_auffaellig(MARKT, {"behandlungen": 180, "transporte": 48,
                                      "notarzt": 8})


def test_vielfaches_der_grundlast_ist_auffaellig():
    erwartet = MARKT["grundlast"]["behandlungen"]
    assert ist_auffaellig(MARKT, {"behandlungen": int(erwartet * AUFFAELLIG_AB_FAKTOR)})


def test_ein_einziger_feuerwehreinsatz_ist_auffaellig():
    """Die Grundlast der Feuerwehr ist null.

    In beiden ausgewerteten Jahren rueckte sie zu keinem Einsatz aus. Bei
    80.000 Quadratmetern Kirmes mit Gasflaschen und Fritteusen ist jeder
    Einsatz dort ein ernstzunehmender Anlass.
    """
    assert MARKT["grundlast"]["feuerwehr"] == 0
    assert ist_auffaellig(MARKT, {"feuerwehr": 1})
    assert not ist_auffaellig(MARKT, {"feuerwehr": 0})


def test_unbekannte_kennzahlen_werden_uebergangen():
    assert not ist_auffaellig(MARKT, {"eisverkaeufe": 99999})


def test_fehlende_werte_brechen_nicht():
    assert not ist_auffaellig(MARKT, {})
    assert not ist_auffaellig(MARKT, {"behandlungen": None})


def test_ein_auffaelliger_wert_genuegt():
    assert ist_auffaellig(MARKT, {"behandlungen": 10, "feuerwehr": 2})


def test_grundlasttext_nennt_den_normalbetrieb():
    text = grundlast_text(MARKT)
    assert "Normalbetrieb" in text
    assert "Behandlungen" in text


# --- Signal ---

def test_signal_meldet_die_laufende_lage_ohne_zu_alarmieren():
    """Eine laufende Grossveranstaltung ist Normalbetrieb, kein Alarmgrund."""
    from app.services.knowledge.assessment import (
        SIGNAL_MINDESTWERT, assess_deployment,
    )
    assert "grosslage" not in SIGNAL_MINDESTWERT

    signal = grosslage_signal({}, tag=date(2026, 9, 11))
    assert signal["kind"] == "grosslage"
    assert signal["bevorstehend"] is False
    assert "Normalbetrieb" in signal["hinweis"]

    # Ohne weitere Lage bleibt die Einsatzerwartung unten
    ergebnis = assess_deployment({"events": {"score": 0}}, {})
    assert ergebnis["level"] == "ruhe"


def test_signal_nennt_das_wetter_als_kritischen_punkt():
    signal = grosslage_signal({"weather": {"score": 70}}, tag=date(2026, 9, 11))
    assert "Wetterlage" in signal["hinweis"]


def test_signal_schweigt_bei_ruhigem_wetter():
    signal = grosslage_signal({"weather": {"score": 20}}, tag=date(2026, 9, 11))
    assert "Wetterlage" not in signal["hinweis"]


def test_signal_warnt_vor_dem_beginn():
    signal = grosslage_signal({}, tag=date(2026, 9, 5))
    assert signal["bevorstehend"] is True
    assert "24 Stunden" in signal["hinweis"]


def test_signal_schweigt_ausserhalb_der_saison():
    assert grosslage_signal({}, tag=date(2026, 3, 15)) is None


def test_puetzchen_zaehlt_als_nachbarschaft():
    """Bonn liegt ausserhalb des Kreises, dieser Platz aber unmittelbar an der
    Grenze zu Sankt Augustin — und es faehrt eine Sonderbuslinie direkt aus
    Troisdorf."""
    assert MARKT["zone"] == "nachbarschaft"


# --- Wachsamkeit ---
#
# Der eigentliche Punkt an einer Grosslage: Sie ist kein Alarmgrund, aber ein
# Verstaerker. Bei einer Million Menschen auf 80.000 Quadratmetern wird aus
# einem kleinen Ereignis binnen Minuten eine Lage, die den Grossraum bindet.
# Das System soll deshalb haeufiger hinsehen, nicht lauter rufen.

def test_wachsamkeit_steigt_waehrend_der_lage():
    assert wachsamkeitsstufe(date(2026, 9, 11))["stufe"] == WACHSAMKEIT_ERHOEHT
    assert ist_wachsam(date(2026, 9, 13))
    assert ist_wachsam(date(2026, 9, 15))


def test_wachsamkeit_faellt_danach_zurueck():
    assert wachsamkeitsstufe(date(2026, 9, 16))["stufe"] == WACHSAMKEIT_NORMAL
    assert not ist_wachsam(date(2026, 3, 15))


def test_wachsamkeit_steigt_nicht_schon_im_vorlauf():
    """Vorher gibt es nichts zu beobachten, was es sonst nicht auch gaebe."""
    assert not ist_wachsam(date(2026, 9, 9))


def test_wachsamkeit_nennt_einen_grund():
    grund = wachsamkeitsstufe(date(2026, 9, 11))["grund"]
    assert "Puetzchens Markt" in grund
    assert "1.000.000" in grund, "Tausenderpunkte fehlen"
    assert ", die den gesamten" in grund, "Satzkomma wurde zerstoert"


def test_normale_wachsamkeit_hat_keinen_grund_und_keine_abtastung():
    stufe = wachsamkeitsstufe(date(2026, 3, 15))
    assert stufe["grund"] is None
    assert stufe["abtastung"] == {}
    assert stufe["lagen"] == []


def test_nur_nahe_zonen_heben_die_wachsamkeit():
    """Ein Volksfest in Ostwestfalen aendert hier nichts."""
    assert "ausserhalb" not in WACHSAME_ZONEN
    assert set(WACHSAME_ZONEN) <= {"troisdorf", "nachbarschaft", "rhein_sieg"}


def test_abtastung_wird_kuerzer_nicht_laenger():
    """Die verkuerzten Abstaende muessen unter den Regelwerten liegen."""
    from app.config import settings
    regel = {
        "warnings": settings.interval_warnings,
        "news": settings.interval_news,
        "feuerwehr_bonn": settings.interval_feuerwehr_bonn,
        "weather_warnings": settings.interval_weather,
        "traffic": settings.interval_traffic,
    }
    for job, sekunden in ABTASTUNG_ERHOEHT.items():
        assert sekunden <= regel[job], f"{job} wuerde seltener abfragen"


def test_abtastung_bleibt_hoeflich():
    """Keine Quelle oefter als einmal pro Minute — die Schnittstellen sind
    fremde Systeme, und ein Fruehwarnsystem darf sie nicht ueberrennen."""
    assert min(ABTASTUNG_ERHOEHT.values()) >= 60


def test_abtastung_trifft_vorhandene_scheduler_jobs():
    """Ein umbenannter Job wuerde die Anpassung still ins Leere laufen lassen.

    Deshalb wird gegen die tatsaechlichen Job-Kennungen in main.py geprueft,
    statt sie in zwei Dateien zu pflegen und auf Disziplin zu hoffen.
    """
    quelle = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text()
    for job in ABTASTUNG_ERHOEHT:
        assert f'id="{job}"' in quelle, f"Kein Scheduler-Job mit id={job}"


def test_nur_schnelle_quellen_werden_verkuerzt():
    """Strompreise und Pegelstaende aendern sich durch eine Kirmes nicht."""
    for job in ("grid", "fuel", "shipping", "drought", "icu"):
        assert job not in ABTASTUNG_ERHOEHT


# --- Kontextgewichtung ---

def test_manv_zaehlt_waehrend_der_grosslage_voll():
    """Ein Massenanfall auf einem Volksfest ist fuer Troisdorf vor allem eine
    Betreuungslage — Tausende Unverletzte und Getrennte. Genau dafuer ist der
    Standort da, die uebliche Daempfung trifft hier nicht zu."""
    from app.services.knowledge.assessment import einsatzbezug_fuer
    assert einsatzbezug_fuer("manv", wachsam=False) < 1.0
    assert einsatzbezug_fuer("manv", wachsam=True) == 1.0


def test_kontextgewichtung_hebt_die_einsatzerwartung():
    from app.services.knowledge.assessment import assess_deployment
    lage = {"manv": {"score": 75}}
    normal = assess_deployment(lage, {}, tag=date(2026, 3, 15))
    wachsam = assess_deployment(lage, {}, tag=date(2026, 9, 11))
    assert wachsam["value"] > normal["value"]
    assert wachsam["vigilance"]["stufe"] == WACHSAMKEIT_ERHOEHT


def test_kontextgewichtung_erklaert_sich():
    from app.services.knowledge.assessment import assess_deployment
    ergebnis = assess_deployment({"manv": {"score": 75}}, {"manv": "MANV"},
                                 tag=date(2026, 9, 11))
    assert any("Betreuungslage" in g for g in ergebnis["reasons"])


def test_kontextgewichtung_aendert_unbeteiligte_kategorien_nicht():
    """Hochwasser wird durch eine Kirmes nicht gefaehrlicher."""
    from app.services.knowledge.assessment import einsatzbezug_fuer
    for cat in ("water", "radiation", "news", "power", "weather"):
        assert einsatzbezug_fuer(cat, True) == einsatzbezug_fuer(cat, False), cat


def test_wachsamkeit_allein_alarmiert_nicht():
    """Eine laufende Grossveranstaltung ist Normalbetrieb."""
    from app.services.knowledge.assessment import assess_deployment
    ergebnis = assess_deployment({"events": {"score": 0}}, {},
                                 tag=date(2026, 9, 11))
    assert ergebnis["level"] == "ruhe"


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
