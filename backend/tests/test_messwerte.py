"""Tests der Messwertauswertung — Waldbrand, Pegel, Schifffahrt, Nachrichten.

Alle vier Fehler hier sind im Betrieb aufgefallen, nicht beim Lesen des Codes.
Gemeinsam haben sie eine Form: Die QUELLE war richtig, die AUSWERTUNG nicht.
Ein Frühwarnsystem, das korrekte Daten falsch verrechnet, ist schwerer zu
entlarven als eines, das gar keine Daten hat — das Ergebnis sieht plausibel
aus.

  Waldbrand    Stufe 1 von 5 heisst beim DWD "sehr geringe Gefahr". Die
               Rechnung Stufe * 20 gab dieser Entwarnung 20 Punkte. Im
               November, bei Frost und nach Regen, zeigte das System damit
               dauerhaft eine Waldbrandgefahr an, die der DWD verneint.

  Pegel        Eine geschaetzte Schwelle JE FLUSS fuer alle Pegel des
               Flusses. Bonn (MHW 680) und Koeln (MHW 725) wurden mit
               derselben Zahl 700 bewertet.

  Schifffahrt  Bewertete nach den amtlichen Werten der Station, der Pegel
               nach der Schaetzung — zwei Maßstaebe fuer dieselbe Zahl, und
               dadurch Widerspruch. Hochwassermarke I fehlte ganz.

  Nachrichten  Der Ortsbezug war nur ein Faktor. Ein Grossbrand in Muenchen
               sammelte genug Stichworte, um die Schwelle trotzdem zu
               reissen.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.collectors.news.news_collector import (
    ORTSGEWICHT, ORTSGEWICHT_FERN, _calculate_relevance, ots_ort,
)
from app.collectors.water.pegel_collector import (
    RIVER_THRESHOLDS, SCHWELLEN_REIHENFOLGE, classify_water_level,
    schwellen_aus_kennwerten,
)
from app.services.alert.alert_engine import WBI_TEXT, wbi_punkte

# Echte Kennwerte, am 25.11.2026 von PEGELONLINE abgerufen.
KOELN = {"GlW": 139.0, "TuGLW": 250.0, "M_II": 830.0, "M_I": 620.0,
         "HHW": 1069.0, "NNW": 69.0, "MNW": 114.0, "MW": 297.0,
         "MHW": 725.0, "HSW": 830.0}
BONN = {"GlW": 142.0, "TuGLW": 250.0, "HHW": 1013.0, "NNW": 81.0,
        "MNW": 121.0, "MW": 290.0, "MHW": 680.0}


# --- Waldbrandgefahrenindex ---

def test_unterste_wbi_stufe_ist_keine_gefahr():
    """Stufe 1 heisst beim DWD "sehr geringe Gefahr" — das ist eine
    Entwarnung und darf keine Punkte geben. Vorher: 1 * 20 = 20."""
    assert wbi_punkte(1) == 0


def test_wbi_stufe_2_bleibt_klein():
    """Stufe 2 ist "geringe Gefahr" — sichtbar, aber nicht handlungsrelevant."""
    assert 0 < wbi_punkte(2) <= 15


def test_wbi_steigt_streng_ab_stufe_zwei():
    werte = [wbi_punkte(i) for i in range(2, 6)]
    assert all(a < b for a, b in zip(werte, werte[1:])), werte


def test_hoechste_wbi_stufe_ist_hundert():
    assert wbi_punkte(5) == 100


def test_wbi_ohne_daten_ist_null():
    for leer in (None, 0, "", "keine Angabe"):
        assert wbi_punkte(leer) == 0


def test_wbi_ueber_der_skala_bleibt_bei_hundert():
    """Fuer den Fall, dass der DWD die Skala erweitert — kein Score > 100."""
    assert wbi_punkte(7) == 100


def test_jede_wbi_stufe_hat_einen_klartext():
    """Im Einsatz muss dastehen, was die Stufe bedeutet, nicht nur die Zahl."""
    for stufe in range(1, 6):
        assert WBI_TEXT.get(stufe), stufe


# --- Pegel: amtliche Kennwerte statt Schaetzung ---

def test_amtliche_schwellen_steigen_streng():
    for name, kennwerte in (("Köln", KOELN), ("Bonn", BONN)):
        s = schwellen_aus_kennwerten(kennwerte)
        assert s is not None, name
        werte = [s[k] for k in SCHWELLEN_REIHENFOLGE]
        assert all(a < b for a, b in zip(werte, werte[1:])), (name, werte)


def test_jeder_pegel_bekommt_seine_eigenen_schwellen():
    """Der Kern des Fehlers: Bonn und Koeln liegen beide am Rhein, haben aber
    verschiedene Pegelnullpunkte. Eine gemeinsame Schwelle ist fuer den einen
    immer falsch."""
    koeln = schwellen_aus_kennwerten(KOELN)
    bonn = schwellen_aus_kennwerten(BONN)
    assert koeln["high_normal"] != bonn["high_normal"]
    assert koeln["low_extreme"] != bonn["low_extreme"]


def test_koeln_nutzt_die_amtlichen_hochwassermarken():
    """Marke I (620) = Geschwindigkeitsbeschraenkung,
    Marke II (830) = Schifffahrt eingestellt. Genau die Zahlen, nach denen
    auch die Schifffahrt urteilt."""
    s = schwellen_aus_kennwerten(KOELN)
    assert s["high_normal"] == 620.0
    assert s["high_extreme"] == 830.0


def test_pegel_und_schifffahrt_urteilen_nach_denselben_zahlen():
    """Der eigentliche Widerspruch. Unter der Sperrmarke darf der Pegel nicht
    "extremhochwasser" melden, und darueber nicht "normal"."""
    s = schwellen_aus_kennwerten(KOELN)
    sperrmarke = KOELN["HSW"]
    knapp_darunter = classify_water_level(sperrmarke - 5, "Rhein", KOELN)
    knapp_darueber = classify_water_level(sperrmarke + 5, "Rhein", KOELN)
    assert knapp_darunter["warning_level"] != "extreme_high"
    assert knapp_darueber["warning_level"] == "extreme_high"
    assert s["high_extreme"] == sperrmarke


def test_abgeleitete_hochwasserstufen_werden_als_solche_ausgewiesen():
    """Bonn veroeffentlicht keine Hochwassermarken. Die obere Haelfte wird
    dann aus MHW/HHW gespannt — das ist eine Ableitung und muss im Klartext
    danebenstehen, damit sie niemand fuer eine amtliche Marke haelt."""
    e = classify_water_level(300, "Rhein", BONN)
    assert "abgeleitet" in e["basis"].lower()


def test_amtliche_basis_wird_benannt():
    e = classify_water_level(324, "Rhein", KOELN)
    assert e["basis"] == "amtliche Pegelkennwerte"


def test_ohne_kennwerte_greift_die_schaetzung_und_sagt_es():
    e = classify_water_level(324, "Rhein", None)
    assert "geschaetzt" in e["basis"]
    assert e["warning_level"] == "normal"


def test_unvollstaendige_kennwerte_fuehren_nicht_zu_halben_schwellen():
    """Lieber die bekannte Schaetzung als eine amtlich aussehende, aber
    lueckenhafte Reihe."""
    assert schwellen_aus_kennwerten({"GlW": 139.0}) is None
    assert schwellen_aus_kennwerten({}) is None
    assert schwellen_aus_kennwerten(None) is None


def test_widerspruechliche_kennwerte_werden_verworfen():
    """Stuende eine Schwelle unter der darunterliegenden, wuerden Stufen
    uebersprungen — dann ist die Schaetzung das kleinere Übel."""
    kaputt = dict(KOELN)
    kaputt["M_I"] = 50.0       # tiefer als der Niedrigwasserbereich
    assert schwellen_aus_kennwerten(kaputt) is None


def test_muell_in_den_kennwerten_bricht_nicht():
    kaputt = dict(KOELN)
    kaputt["MNW"] = "keine Angabe"
    assert schwellen_aus_kennwerten(kaputt) is None


def test_niedrigwasser_wird_mit_amtlichen_werten_erkannt():
    e = classify_water_level(KOELN["NNW"] - 5, "Rhein", KOELN)
    assert e["warning_level"] == "extreme_low"


def test_fehlender_messwert_meldet_keine_daten():
    e = classify_water_level(None, "Rhein", KOELN)
    assert e["warning_level"] == "unknown"


def test_pegelonline_fuehrt_nur_bundeswasserstrassen():
    """PEGELONLINE ist das Netz der Wasser- und Schifffahrtsverwaltung. Sieg
    und Agger stehen dort nicht — sie lagen mit uuid=None in der Stationsliste
    und lieferten still nichts. Sie kommen ueber OpenHygon."""
    from app.collectors.water.pegel_collector import STATIONS
    for name, info in STATIONS.items():
        assert info.get("uuid"), f"{name} ohne uuid — kann nichts liefern"
        assert info["river"].lower() == "rhein", name


def test_die_schaetzung_bleibt_als_rueckfall_erhalten():
    """Sie ist nicht gut, aber besser als nichts — und fuer Gewaesser ohne
    amtliche Kennwerte der einzige Maßstab."""
    assert "rhein" in RIVER_THRESHOLDS and "sieg" in RIVER_THRESHOLDS


# --- Nachrichten: Ortsbezug ---

def test_ortszeile_wird_gelesen():
    assert ots_ort("München (ots) - Die Feuerwehr") == "München"
    assert ots_ort("Sankt Augustin (ots) - Am Sonntag") == "Sankt Augustin"
    assert ots_ort("Troisdorf (ots) - Brand") == "Troisdorf"


def test_ortszeile_fehlt_bei_normalen_meldungen():
    assert ots_ort("Ein ganz normaler Zeitungstext ohne Ortszeile") is None
    assert ots_ort("") is None
    assert ots_ort(None) is None


def test_grossbrand_in_muenchen_ist_nicht_relevant():
    """Der gemeldete Fehler. Viele Stichworte, maximaler Score — und trotzdem
    1000 km weit weg."""
    r = _calculate_relevance(
        "Großbrand in einem Mehrfamilienhaus",
        "München (ots) - Feuerwehr im Großeinsatz, Brand, Rauch, Explosion",
        bundesweit=True)
    assert r <= 0.3, f"Relevanz {r} — Muenchen gilt wieder als relevant"


def test_auch_gesaettigte_stichworte_retten_eine_ferne_meldung_nicht():
    """Der Score deckelt bei 1,0. Mal Fernfaktor muss das unter der Schwelle
    bleiben — sonst haengt es am Zufall, wie viele Worte passen."""
    assert 1.0 * ORTSGEWICHT_FERN <= 0.3


def test_die_weitere_umgebung_bleibt_relevant():
    """Koeln-Porz grenzt an Troisdorf. "Weit weg" und "nicht im Kreis" sind
    nicht dasselbe — diese Verwechslung war der Fehler."""
    r = _calculate_relevance(
        "Großbrand in einem Lagerhaus",
        "Köln (ots) - Feuerwehr Großeinsatz, Brand, Rauch", bundesweit=True)
    assert r > 0.3, f"Koeln faellt mit {r} durch"


def test_bonner_meldungen_bleiben_relevant():
    """Polizei Bonn und Feuerwehr Bonn sind eigene Quellen im System. Wuerden
    ihre Meldungen als "nicht von hier" verworfen, waeren beide Quellen
    sinnlos."""
    r = _calculate_relevance(
        "POL-BN: Feuer in Bonn-Beuel",
        "Bonn (ots) - Feuerwehr im Einsatz, Brand, verletzt", bundesweit=True)
    assert r > 0.3, f"Bonn faellt mit {r} durch"


def test_flaechendeckende_lage_schlaegt_die_ortszeile():
    """Beim bundesweiten Warntag steht in der Ortszeile "Bonn", gemeint ist
    ganz Deutschland. Genau diese Verwechslung hat im September dazu gefuehrt,
    dass eine bundesweite Behoerdenwarnung mild gemeldet wurde."""
    r = _calculate_relevance(
        "Bundesweiter Warntag: Sirenen heulen in ganz Deutschland",
        "Bonn (ots) - Warnung, Sirene", bundesweit=True)
    assert r > 0.3, f"bundesweite Lage faellt mit {r} durch"


def test_flaechendeckend_zaehlt_voll():
    """Eine Lage, die ganz Deutschland betrifft, betrifft uns vollstaendig.
    Der Schluessel fehlte und fiel auf den Standardwert fuer "unbekannt"."""
    assert ORTSGEWICHT["flaechendeckend"] == 1.0


def test_oertliche_meldung_wiegt_am_schwersten():
    r = _calculate_relevance(
        "Feuer in Troisdorf-Spich: Feuerwehr im Großeinsatz",
        "Troisdorf (ots) - Brand, Evakuierung", bundesweit=False)
    assert r > 0.6


def test_alltag_vom_ort_ist_keine_lage():
    """Ortsbezug allein genuegt nicht — sonst ist jede Schwimmbadmeldung
    eine Lage."""
    r = _calculate_relevance("Revision im Aggua Troisdorf",
                             "Schwimmbad lässt Wasser ab", bundesweit=False)
    assert r <= 0.3


def test_ortsgewichte_sind_geordnet():
    assert (ORTSGEWICHT["troisdorf"] >= ORTSGEWICHT["nachbarschaft"]
            > ORTSGEWICHT["rhein_sieg"] > ORTSGEWICHT["ausserhalb"]
            > ORTSGEWICHT_FERN)


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
