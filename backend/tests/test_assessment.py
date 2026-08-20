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
    EINSATZBEZUG, EVAKUIERUNG_MINDESTWERT,
    EVAKUIERUNG_MINDESTWERT_NACHBARSCHAFT, NEBENLAGE_SCHWELLE,
    ORTSFAKTOR_AUSSERHALB, ORTSFAKTOR_KREIS, ORTSFAKTOR_NACHBARSCHAFT,
    ORTSFAKTOR_ORT, assess_deployment, einsatzgewichteter_score,
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


def test_manv_wiegt_weniger_als_eine_betreuungslage():
    """Troisdorf wirkt bei MANV mit, ist aber kein Rettungsdienststandort.

    Eine Hochwasserlage bindet die Kueche und den Betreuungsdienst unmittelbar,
    ein MANV zuerst den Rettungsdienst.
    """
    manv = assess_deployment(_scores(manv=80), LABELS)
    wasser = assess_deployment(_scores(water=80), LABELS)
    assert manv["value"] < wasser["value"]


def test_gesundheit_wiegt_wenig_mangels_rettungsdienst():
    gesundheit = assess_deployment(_scores(health=90), LABELS)
    assert _level(gesundheit) != "einsatz_wahrscheinlich"


def test_erdbeben_gleicher_hoehe_bleibt_deutlich_darunter():
    """Eine Erdbebenmeldung fuehrt in der Eifel praktisch nie zum Einsatz."""
    wasser = assess_deployment(_scores(water=85), LABELS)
    beben = assess_deployment(_scores(seismic=85), LABELS)
    assert beben["value"] < wasser["value"]
    assert _level(beben) != "einsatz_wahrscheinlich"


def test_nachrichten_sind_der_staerkste_fruehindikator():
    """Korrektur aus der Einsatzerfahrung.

    Ein frueheres Modell wertete Nachrichten als "Indiz, nie Grund" ab. Nach
    Auskunft der Einheit ist die Presse der zuverlaessigste Vorbote: Was
    Verpflegung braucht, dauert lange und bindet viele Kraefte — und genau
    darueber wird berichtet.
    """
    ortsnah = assess_deployment(_scores(
        news={"score": 85, "detail": "Grossbrand in Troisdorf"}), LABELS)
    assert ortsnah["level"] == "einsatz_wahrscheinlich"


def test_nachricht_ohne_ortsbezug_wiegt_weniger():
    """Eine Meldung ueber irgendwo sagt wenig, eine ueber Troisdorf viel."""
    fern = assess_deployment(_scores(news={"score": 85}), LABELS)
    nah = assess_deployment(_scores(
        news={"score": 85, "detail": "Lage in Siegburg"}), LABELS)
    assert nah["value"] > fern["value"]


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


# --- Evakuierung im Kerngebiet ---

def test_evakuierung_in_troisdorf_bedeutet_einsatz():
    """Erfahrungswert der Einheit: hier ist keine Abwaegung noetig."""
    result = assess_deployment(_scores(
        news={"score": 40, "detail": "Bombenfund, Evakuierung in Troisdorf"},
    ), LABELS)
    assert _level(result) == "einsatz_wahrscheinlich"
    assert result["evacuation"]["ort"] == "Troisdorf"
    assert "Betreuungsgespann" in result["components"]


def test_evakuierung_in_siegburg_zaehlt_wie_das_eigene_stadtgebiet():
    result = assess_deployment(_scores(
        official_warning={"score": 35, "detail": "Räumung mehrerer Straßen in Siegburg"},
    ), LABELS)
    assert _level(result) == "einsatz_wahrscheinlich"
    assert result["evacuation"]["ort"] == "Siegburg"


def test_evakuierung_ausserhalb_des_kerngebiets_loest_nichts_aus():
    """Ein Bombenfund in Koeln ist Koelner Sache."""
    result = assess_deployment(_scores(
        news={"score": 40, "detail": "Bombenfund mit Evakuierung in Koeln-Kalk"},
    ), LABELS)
    assert result["evacuation"] is None
    assert _level(result) != "einsatz_wahrscheinlich"


def test_ortsname_ohne_evakuierung_loest_nichts_aus():
    """Beide Hinweise muessen zusammenkommen, sonst gaebe es Dauerfeuer."""
    result = assess_deployment(_scores(
        news={"score": 30, "detail": "Stadtfest in Troisdorf gut besucht"},
    ), LABELS)
    assert result["evacuation"] is None


def test_evakuierung_wird_auch_in_beitraegen_erkannt():
    """Die Ausloeser stecken oft in den Einzelbeitraegen, nicht im Kurztext."""
    result = assess_deployment(_scores(
        news={
            "score": 30,
            "detail": "3 relevante Meldungen",
            "contributions": [
                {"source": "Rundschau", "reason": "Kellerbrand"},
                {"source": "GA", "reason": "Wohnhaus in Troisdorf geräumt"},
            ],
        },
    ), LABELS)
    assert result["evacuation"] is not None


def test_evakuierung_senkt_eine_hohe_bewertung_nicht():
    """Der Mindestwert ist eine Untergrenze, keine Deckelung."""
    ohne = assess_deployment(_scores(water=95), LABELS)
    mit = assess_deployment(_scores(
        water={"score": 95, "detail": "Evakuierung in Troisdorf"}), LABELS)
    assert mit["value"] >= ohne["value"]


def test_evakuierungsbegruendung_steht_an_erster_stelle():
    result = assess_deployment(_scores(
        news={"score": 40, "detail": "Evakuierung in Troisdorf"}), LABELS)
    assert "Evakuierung" in result["reasons"][0]


# --- Verpflegungsprofil ---

def test_brandlage_bringt_die_kueche_ins_spiel():
    """Haeufigster Einsatzanlass: Verpflegung der Einsatzkraefte."""
    result = assess_deployment(_scores(fire=85), LABELS)
    assert any("Verpflegung" in k for k in result["components"])


def test_verpflegung_steht_bei_brand_vor_der_betreuung():
    """Die Reihenfolge spiegelt, was der Standort tatsaechlich stellt."""
    result = assess_deployment(_scores(fire=85), LABELS)
    assert "Verpflegung" in result["components"][0]


def test_veranstaltungen_bringen_den_sanitaetsdienst():
    result = assess_deployment(_scores(events=80), LABELS)
    assert "Sanitaetsdienst" in result["components"]


def test_begruendung_erklaert_das_standortprofil():
    """Wer die Zahl sieht, soll auch verstehen, warum sie gedaempft ist."""
    result = assess_deployment(_scores(manv=80), LABELS)
    assert any("Rettungsdienststandort" in r for r in result["reasons"])


# --- Raeumliche Abstufung ---

def test_siegburg_zaehlt_wie_das_eigene_stadtgebiet():
    """Siegburg ist die wichtigste Nachbarkommune."""
    troisdorf = assess_deployment(_scores(
        news={"score": 80, "detail": "Grossbrand in Troisdorf"}), LABELS)
    siegburg = assess_deployment(_scores(
        news={"score": 80, "detail": "Grossbrand in Siegburg"}), LABELS)
    assert siegburg["value"] == troisdorf["value"]


def test_nachbargemeinden_liegen_knapp_unter_dem_kerngebiet():
    """Niederkassel, Sankt Augustin, Lohmar, Hennef: relevant, aber darunter."""
    kern = assess_deployment(_scores(
        news={"score": 80, "detail": "Lage in Siegburg"}), LABELS)
    nachbar = assess_deployment(_scores(
        news={"score": 80, "detail": "Lage in Lohmar"}), LABELS)
    kreis = assess_deployment(_scores(
        news={"score": 80, "detail": "Lage in Windeck"}), LABELS)
    assert kreis["value"] < nachbar["value"] < kern["value"]


def test_ortsstufen_sind_absteigend_geordnet():
    assert (ORTSFAKTOR_ORT > ORTSFAKTOR_NACHBARSCHAFT > ORTSFAKTOR_KREIS
            > ORTSFAKTOR_AUSSERHALB)


def test_sankt_augustin_wird_in_beiden_schreibweisen_erkannt():
    """Meldungen schreiben den Ort uneinheitlich."""
    lang = assess_deployment(_scores(
        news={"score": 80, "detail": "Lage in Sankt Augustin"}), LABELS)
    kurz = assess_deployment(_scores(
        news={"score": 80, "detail": "Lage in St. Augustin"}), LABELS)
    unbekannt = assess_deployment(_scores(
        news={"score": 80, "detail": "Lage in Windeck"}), LABELS)
    assert lang["value"] == kurz["value"] > unbekannt["value"]


def test_kerngebiet_hat_vorrang_vor_der_nachbarschaft():
    """Nennt ein Text beide, zaehlt das Kerngebiet."""
    result = assess_deployment(_scores(
        news={"score": 40,
              "detail": "Evakuierung in Siegburg und Lohmar"}), LABELS)
    assert result["evacuation"]["zone"] == "kerngebiet"
    assert result["evacuation"]["ort"] == "Siegburg"


def test_evakuierung_in_der_nachbarschaft_wiegt_weniger():
    """Annahme: eine Stufe unter dem Kerngebiet, nicht aus der Einheit belegt."""
    kern = assess_deployment(_scores(
        news={"score": 20, "detail": "Evakuierung in Troisdorf"}), LABELS)
    nachbar = assess_deployment(_scores(
        news={"score": 20, "detail": "Evakuierung in Niederkassel"}), LABELS)
    assert kern["value"] == EVAKUIERUNG_MINDESTWERT
    assert nachbar["value"] == EVAKUIERUNG_MINDESTWERT_NACHBARSCHAFT
    assert nachbar["evacuation"]["zone"] == "nachbarschaft"


# --- Grundrate der Landesalarmierung ---

def test_ueberoertliche_lage_nennt_die_grundrate():
    """Ohne den Hinweis liest sich ein hoher Wert als Alltagserwartung.

    Das Betreuungsgespann wurde zuletzt beim Ahrhochwasser 2021 vom Land
    gezogen, davor ein- bis zweimal in sehr grossen Abstaenden.
    """
    result = assess_deployment(_scores(
        official_warning={"score": 95, "area_scope": "ausserhalb"}), LABELS)
    assert any("Ahrhochwasser" in r for r in result["reasons"])


def test_ortsnahe_lage_nennt_die_grundrate_nicht():
    """Der Hinweis gehoert nur dorthin, wo er die Erwartung korrigiert."""
    result = assess_deployment(_scores(
        water={"score": 85, "detail": "Pegel Troisdorf steigt"}), LABELS)
    assert not any("Ahrhochwasser" in r for r in result["reasons"])


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
