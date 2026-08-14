"""Tests der Einsatzerwartung.

Die Einsatzerwartung beantwortet eine andere Frage als das Gesamtrisiko:
nicht "wie schlimm ist die Lage", sondern "was folgt daraus fuer die
Bereitschaft Troisdorf". Der Ausloeser war der gemeldete Fall Dueren — ein
realer Grossbrand in einem anderen Kreis, bei dem die App fast auf Vollalarm
stand, obwohl Troisdorf dafuer nicht gezogen wird.

Grundlage der Bewertung ist der Rettungsdienstbedarfsplan 2023 des
Rhein-Sieg-Kreises: Zustaendigkeiten, Vorlaufzeiten und die Regel, dass
ueberoertliche Hilfe erst angefordert wird, wenn der betroffene Kreis seine
eigenen Mittel erschoepft hat.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.knowledge.assessment import (
    EINSATZBEZUG, NEBENLAGE_SCHWELLE, ORTSFAKTOR_AUSSERHALB,
    assess_deployment, einsatzgewichteter_score,
)

LABELS = {
    "water": "Hochwasser", "weather": "Wetter", "fire": "Waldbrand",
    "traffic": "Verkehr", "official_warning": "Behördenwarnungen",
    "power": "Stromnetz", "health": "Gesundheit", "news": "Nachrichten",
    "manv": "MANV", "radiation": "Strahlung", "seismic": "Erdbeben",
    "shipping": "Schifffahrt", "events": "Veranstaltungen",
    "air_quality": "Luftqualität",
}


def _scores(**kwargs):
    """Alle Kategorien auf 0, ausser den genannten."""
    base = {name: {"score": 0} for name in EINSATZBEZUG}
    for name, value in kwargs.items():
        if isinstance(value, dict):
            base[name] = value
        else:
            base[name] = {"score": value}
    return base


def _level(result):
    return result["level"]


# --- Der gemeldete Fall ---

def test_grossbrand_im_nachbarkreis_erzeugt_keinen_einsatzalarm():
    """Dueren: schwere Lage, andere Zustaendigkeit.

    Die Warnung ist echt und gehoert angezeigt — aber Troisdorf wird dafuer
    nicht gezogen, solange der betroffene Kreis nicht ueberoertliche Hilfe
    anfordert.
    """
    result = assess_deployment(_scores(
        official_warning={"score": 90, "area_scope": "ausserhalb"},
        air_quality=35,
    ), LABELS)
    assert _level(result) in ("beobachtung", "ruhe")
    assert any("Ortsbezug" in r for r in result["reasons"])


def test_gleiche_warnung_im_eigenen_kreis_wiegt_deutlich_schwerer():
    """Dieselbe Meldung, andere Zustaendigkeit — anderes Ergebnis."""
    fern = assess_deployment(_scores(
        official_warning={"score": 90, "area_scope": "ausserhalb"}), LABELS)
    nah = assess_deployment(_scores(
        official_warning={"score": 90, "area_scope": "troisdorf"}), LABELS)
    assert nah["value"] > fern["value"] * 1.8


def test_warnung_ohne_ortsangabe_wird_konservativ_eingeordnet():
    """Fehlt die Ortsangabe, gilt Kreisebene — nicht ignorieren, aber auch
    nicht wie eine Lage vor der Haustuer behandeln."""
    ohne = assess_deployment(_scores(official_warning={"score": 80}), LABELS)
    nah = assess_deployment(_scores(
        official_warning={"score": 80, "area_scope": "troisdorf"}), LABELS)
    fern = assess_deployment(_scores(
        official_warning={"score": 80, "area_scope": "ausserhalb"}), LABELS)
    assert fern["value"] < ohne["value"] < nah["value"]


# --- Einsatzbezug der Kategorien ---

def test_hochwasser_schlaegt_direkt_auf_die_bereitschaft_durch():
    """Evakuierung und Betreuung sind DRK-Kernaufgaben."""
    result = assess_deployment(_scores(water=85), LABELS)
    assert _level(result) == "einsatz_wahrscheinlich"
    assert "Betreuungsdienst" in result["components"]


def test_erdbeben_gleicher_hoehe_bleibt_deutlich_darunter():
    """Eine Erdbebenmeldung fuehrt in der Eifel praktisch nie zum Einsatz."""
    wasser = assess_deployment(_scores(water=85), LABELS)
    beben = assess_deployment(_scores(seismic=85), LABELS)
    assert beben["value"] < wasser["value"]
    assert _level(beben) != "einsatz_wahrscheinlich"


def test_nachrichten_allein_loesen_nie_eine_einsatzerwartung_aus():
    """Nachrichten sind ein Indiz, nie ein Grund."""
    result = assess_deployment(_scores(news=100), LABELS)
    assert _level(result) in ("beobachtung", "ruhe")


def test_strahlung_wird_nie_abgewertet():
    """Sicherheitskritisch — hier darf keine Daempfung greifen."""
    assert EINSATZBEZUG["radiation"] == 1.0
    result = assess_deployment(_scores(radiation=85), LABELS)
    assert _level(result) == "einsatz_wahrscheinlich"
    assert "CBRN-Schutz" in result["components"]


def test_stromausfall_ausserhalb_wiegt_weniger_als_vor_ort():
    """Der Stromkollektor liefert seine Zone mit — die wird respektiert."""
    ort = assess_deployment(_scores(
        power={"score": 80, "primary_condition": "outage"}), LABELS)
    fern = assess_deployment(_scores(
        power={"score": 80, "primary_condition": "extremlage_ausserhalb"}), LABELS)
    assert fern["value"] < ort["value"]


def test_grosslage_im_kreis_liegt_zwischen_ort_und_ausserhalb():
    ort = assess_deployment(_scores(
        power={"score": 80, "primary_condition": "outage"}), LABELS)
    kreis = assess_deployment(_scores(
        power={"score": 80, "primary_condition": "grosslage_kreis"}), LABELS)
    fern = assess_deployment(_scores(
        power={"score": 80, "primary_condition": "extremlage_ausserhalb"}), LABELS)
    assert fern["value"] < kreis["value"] < ort["value"]


# --- Mehrere Lagen gleichzeitig ---

def test_mehrere_erhoehte_kategorien_verschaerfen_die_erwartung():
    einzeln = assess_deployment(_scores(weather=70), LABELS)
    mehrfach = assess_deployment(_scores(weather=70, water=60, power=60), LABELS)
    assert mehrfach["value"] > einzeln["value"]
    assert len(mehrfach["contributing"]) >= 1


def test_zuschlag_hebt_hoechstens_eine_stufe():
    """Der Breitenzuschlag darf die Bewertung nicht sprengen.

    Sonst wuerde eine Sammlung mittlerer Werte eine schwere Einzellage
    ueberholen — genau der Fehler, der beim Gesamtscore korrigiert wurde,
    nur mit umgekehrtem Vorzeichen.
    """
    viele = assess_deployment(_scores(
        weather=50, water=50, power=50, fire=50, traffic=50, health=50), LABELS)
    eine_schwere = assess_deployment(_scores(water=95), LABELS)
    assert eine_schwere["value"] > viele["value"]


def test_nebenlagen_unter_der_schwelle_zaehlen_nicht():
    unter = NEBENLAGE_SCHWELLE - 10
    result = assess_deployment(_scores(water=80, weather=unter / 0.9 - 1), LABELS)
    assert result["contributing"] == []


# --- Stufen und Begruendung ---

def test_ruhige_lage_ergibt_ruhe():
    result = assess_deployment(_scores(), LABELS)
    assert _level(result) == "ruhe"
    assert result["value"] == 0.0


def test_leere_eingabe_bricht_nicht():
    result = assess_deployment({}, LABELS)
    assert _level(result) == "ruhe"
    assert result["driver"] is None


def test_overall_wird_nicht_als_kategorie_gewertet():
    """Der Gesamtscore steht mit im Dict — er darf nicht mitgerechnet werden."""
    result = assess_deployment(
        {"overall": {"score": 100}, "water": {"score": 20}}, LABELS)
    assert result["driver"] == "water"


def test_begruendung_nennt_den_treibenden_anlass_mit_klarnamen():
    result = assess_deployment(_scores(water=80), LABELS)
    assert any("Hochwasser" in r for r in result["reasons"])


def test_stufen_steigen_monoton_mit_dem_score():
    werte = [assess_deployment(_scores(water=s), LABELS)["value"]
             for s in (10, 30, 50, 70, 90)]
    assert werte == sorted(werte)


def test_komponenten_sind_dubletten_frei():
    """Treiber und Nebenlage koennen dieselbe Komponente brauchen."""
    result = assess_deployment(_scores(water=80, power=60), LABELS)
    assert len(result["components"]) == len(set(result["components"]))


def test_vorlaufzeiten_stammen_aus_dem_bedarfsplan():
    """24 Stunden Sonderbedarf, 30-60 Minuten Spitzenbedarf."""
    result = assess_deployment(_scores(weather=70), LABELS)
    assert result["lead_time"]["sonderbedarf_stunden"] == 24
    assert result["lead_time"]["spitzenbedarf_minuten_regel"] == 30
    assert result["lead_time"]["spitzenbedarf_minuten_spaet"] == 60


def test_einsatzgewichteter_score_ist_nachvollziehbar():
    """Der Wert muss sich aus Score x Bezug x Ortsfaktor ergeben."""
    wert = einsatzgewichteter_score("weather", {"score": 100})
    assert abs(wert - 100 * EINSATZBEZUG["weather"]) < 0.01

    fern = einsatzgewichteter_score(
        "official_warning", {"score": 100, "area_scope": "ausserhalb"})
    erwartet = 100 * EINSATZBEZUG["official_warning"] * ORTSFAKTOR_AUSSERHALB
    assert abs(fern - erwartet) < 0.01


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
