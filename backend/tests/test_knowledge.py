"""Tests der DRK-Wissensdatenbank.

Geprueft wird zweierlei: dass der recherchierte Grundbestand in sich stimmig
und belegt ist, und dass die Auswahl zur Lage das Richtige nach oben holt.

Der Grundbestand ist kein Beiwerk — er ist die Grundlage, auf der der
Lagebericht Aussagen ueber Einheiten, Staerken und Stufen trifft. Ein Fehler
hier wandert unbemerkt in jeden Bericht.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.schemas import KnowledgeKind, KnowledgeScope
from app.services.knowledge.knowledge_base import (
    MIN_TERM_LENGTH, SCOPE_WEIGHT, _tokens, score_entry,
)
from app.services.knowledge.seed_data import (
    ALL_ENTRIES, LOCAL_ENTRIES, SEED_ENTRIES,
)


class FakeEntry:
    """Minimale KnowledgeEntry-Oberflaeche fuer die Bewertung."""

    def __init__(self, categories=None, tags=None, trigger=None,
                 scope=KnowledgeScope.TROISDORF, title="", body=""):
        self.categories = categories or []
        self.tags = tags or []
        self.trigger = trigger
        self.scope = scope
        self.title = title
        self.body = body


def _entry(seed_key):
    for e in ALL_ENTRIES:
        if e["seed_key"] == seed_key:
            return e
    raise AssertionError(f"Eintrag {seed_key} fehlt")


# --- Grundbestand: Vollstaendigkeit und Stimmigkeit ---

def test_seed_keys_sind_eindeutig():
    keys = [e["seed_key"] for e in ALL_ENTRIES]
    assert len(keys) == len(set(keys))


def test_alle_eintraege_nutzen_gueltige_arten_und_bereiche():
    for e in ALL_ENTRIES:
        KnowledgeKind(e["kind"])
        KnowledgeScope(e["scope"])


def test_jeder_eintrag_hat_einen_belegten_inhalt():
    for e in ALL_ENTRIES:
        assert e["title"].strip(), e["seed_key"]
        assert len(e["body"]) > 100, f"{e['seed_key']} ist zu duenn"
        assert e["source"], f"{e['seed_key']} ohne Quelle"


def test_recherchierte_eintraege_sind_als_offiziell_markiert():
    """Der recherchierte Teil stammt aus oeffentlichen Dokumenten."""
    assert all(e["is_official"] for e in SEED_ENTRIES)


def test_eigenes_wissen_ist_nicht_als_offiziell_markiert():
    """Wissen der Einheit ist fuer die Bewertung die verlaesslichste Quelle,
    oeffentlich belegbar ist es aber nicht. Die Herkunft muss unterscheidbar
    bleiben — sonst weiss spaeter niemand mehr, was nachpruefbar ist."""
    assert all(not e["is_official"] for e in LOCAL_ENTRIES)
    assert all("DRK Troisdorf" in (e["source"] or "") for e in LOCAL_ENTRIES)
    assert all(e["source_url"] is None for e in LOCAL_ENTRIES)


def test_eigenes_und_recherchiertes_wissen_ueberschneidet_sich_nicht():
    seed = {e["seed_key"] for e in SEED_ENTRIES}
    local = {e["seed_key"] for e in LOCAL_ENTRIES}
    assert not (seed & local)
    assert len(ALL_ENTRIES) == len(SEED_ENTRIES) + len(LOCAL_ENTRIES)


def test_kategorien_sind_echte_scoring_kategorien():
    """Ein Tippfehler hier wuerde den Eintrag unsichtbar machen."""
    from app.services.knowledge.assessment import EINSATZBEZUG
    erlaubt = set(EINSATZBEZUG) | {"custom"}
    for e in ALL_ENTRIES:
        for cat in e["categories"]:
            assert cat in erlaubt, f"{e['seed_key']}: unbekannte Kategorie {cat}"


def test_trigger_bedingungen_sind_wohlgeformt():
    for e in ALL_ENTRIES:
        trigger = e["trigger"]
        if not trigger:
            continue
        assert set(trigger) <= {"category", "categories", "min_score",
                                "any_category_min_score"}, e["seed_key"]
        if "min_score" in trigger:
            assert trigger.get("categories") or trigger.get("category"), e["seed_key"]
            assert 0 <= trigger["min_score"] <= 100


# --- Inhaltliche Stichproben gegen die Quellen ---

def test_manv_stufen_entsprechen_dem_bedarfsplan():
    """Der Kreis staffelt in Zehnerschritten 10/20/30/40/50 — feiner als die
    anderswo uebliche Reihe 10/15/25/50/100."""
    stufen = _entry("stufe.manv.rsk")["facts"]["stufen"]
    assert stufen == [10, 20, 30, 40, 50]


def test_einsatzeinheit_staerke_ist_1_7_25_33():
    facts = _entry("org.einsatzeinheit.nrw")["facts"]
    assert facts["fuehrer"] + facts["unterfuehrer"] + facts["helfer"] == facts["staerke_gesamt"]
    assert facts["staerke_gesamt"] == 33


def test_bhp50_und_btp500_kennzahlen():
    bhp = _entry("org.bhp50")["facts"]
    btp = _entry("org.btp500")["facts"]
    assert bhp["einsatzkraefte"] == 78 and bhp["patienten_2h"] == 50
    assert btp["einsatzkraefte"] == 72 and btp["betroffene"] == 500


def test_sichtungsanteile_ergeben_hundert_prozent():
    facts = _entry("stufe.sichtung")["facts"]
    summe = facts["sk1_anteil"] + facts["sk2_anteil"] + facts["sk3_anteil"]
    assert abs(summe - 1.0) < 0.001


def test_vorlaufzeiten_der_taktischen_reserve():
    """24 Stunden Sonderbedarf, 30 bis 60 Minuten Spitzenbedarf."""
    facts = _entry("stufe.taktische_reserve")["facts"]
    assert facts["sonderbedarf_vorlauf_h"] == 24
    assert facts["spitzenbedarf_bereit_min"] < facts["spitzenbedarf_spaet_min"]


def test_troisdorf_ist_als_industriestandort_erfasst():
    """Troisdorf ist einer von vier Schwerpunkten der chemischen und
    sprengstoffverarbeitenden Industrie im Kreis."""
    body = _entry("gefahr.industrie")["body"]
    assert "TROISDORF" in body


def test_flughafen_koeln_bonn_ist_troisdorfer_gebiet():
    eintrag = _entry("gefahr.flughafen")
    assert eintrag["scope"] == "troisdorf"
    assert "Koeln/Bonn" in eintrag["body"] or "Konrad-Adenauer" in eintrag["body"]


def test_hochwasser_ortslagen_sind_benannt():
    """Bergheim, Muellekoven und Eschmar sind die siegnahen Lagen."""
    body = _entry("ausloeser.hochwasser")["body"]
    for ort in ("Bergheim", "Muellekoven", "Eschmar"):
        assert ort in body


def test_wetterausloeser_verweist_auf_den_vorlauf():
    """Die Bruecke zwischen Vorhersage und Alarmierung — der Kern des Systems."""
    body = _entry("ausloeser.wetter")["body"]
    assert "24 Stunden" in body and "Sonderbedarf" in body


def test_nachbarkreis_regel_ist_hinterlegt():
    """Die Regel, die den Fall Dueren erklaert."""
    eintrag = _entry("ausloeser.grosslage_nachbar")
    assert "UEMANV" in eintrag["body"]
    assert eintrag["trigger"]["min_score"] >= 70


def test_jeder_bereich_ist_vertreten():
    bereiche = {e["scope"] for e in ALL_ENTRIES}
    assert bereiche == {"troisdorf", "nachbarschaft", "rhein_sieg", "nrw",
                        "bund"}


def test_wissensbereiche_entsprechen_den_ortszonen():
    """Wissen und Ortsbewertung muessen dieselbe Einteilung verwenden.

    Laufen sie auseinander, bewertet das System eine Meldung anders, als es
    das Wissen dazu gewichtet.
    """
    from app.services.knowledge.knowledge_base import SCOPE_WEIGHT
    for scope in KnowledgeScope:
        assert scope in SCOPE_WEIGHT, scope


def test_scope_gewichte_bleiben_absteigend():
    from app.services.knowledge.knowledge_base import SCOPE_WEIGHT
    reihe = [KnowledgeScope.TROISDORF, KnowledgeScope.NACHBARSCHAFT,
             KnowledgeScope.RHEIN_SIEG, KnowledgeScope.NRW,
             KnowledgeScope.BUND]
    werte = [SCOPE_WEIGHT[s] for s in reihe]
    assert werte == sorted(werte, reverse=True)


def test_die_wichtigsten_wissensarten_sind_vertreten():
    arten = {e["kind"] for e in ALL_ENTRIES}
    for pflicht in ("doktrin", "organisation", "gefahrenobjekt",
                    "eskalationsstufe", "ausloeser", "ressource"):
        assert pflicht in arten


# --- Eigenes Wissen des Standorts ---

def test_einsatzprofil_haelt_fest_dass_troisdorf_kein_rd_standort_ist():
    body = _entry("eigen.profil.troisdorf")["body"]
    assert "VERPFLEGUNGSSTANDORT" in body
    assert "Kein Rettungsdienststandort" in body


def test_fahrzeugbestand_ist_vollstaendig_erfasst():
    facts = _entry("eigen.fahrzeuge.troisdorf")["facts"]
    assert facts == {"mtf": 1, "mzf": 2, "kuechenanhaenger": 1,
                     "feldkueche": 1, "betreuungsgespann": 1}


def test_betreuungsgespann_ist_als_landesressource_vermerkt():
    """Der Grund, warum Troisdorf auch weit ausserhalb gezogen werden kann."""
    body = _entry("eigen.fahrzeuge.troisdorf")["body"]
    assert "Land NRW" in body and "Betreuungsgespann" in body


def test_brandeintrag_warnt_vor_der_verwechslung_von_gefahr_und_ereignis():
    """Die Kategorie Waldbrand misst den Gefahrenindex, kein laufendes Feuer."""
    body = _entry("eigen.ausloeser.brand")["body"]
    assert "Waldbrandgefahrenindex" in body or "GEFAHR" in body


def test_nachrichteneintrag_begruendet_die_hohe_gewichtung():
    body = _entry("eigen.ausloeser.nachrichten")["body"]
    assert "Presse" in body


def test_evakuierungseintrag_nennt_troisdorf_und_siegburg():
    body = _entry("eigen.ausloeser.evakuierung")["body"]
    assert "TROISDORF" in body and "SIEGBURG" in body


# --- Auswahl zur Lage ---

def test_eintrag_ohne_bezug_zur_lage_wird_nicht_gewaehlt():
    entry = FakeEntry(categories=["shipping"])
    assert score_entry(entry, {"shipping": {"score": 0}}) == 0


def test_hoher_kategoriescore_hebt_den_passenden_eintrag():
    wasser = FakeEntry(categories=["water"])
    schiff = FakeEntry(categories=["shipping"])
    scores = {"water": {"score": 90}, "shipping": {"score": 10}}
    assert score_entry(wasser, scores) > score_entry(schiff, scores)


def test_ortsnaher_eintrag_schlaegt_den_bundesweiten():
    lokal = FakeEntry(categories=["water"], scope=KnowledgeScope.TROISDORF)
    bund = FakeEntry(categories=["water"], scope=KnowledgeScope.BUND)
    scores = {"water": {"score": 80}}
    assert score_entry(lokal, scores) > score_entry(bund, scores)


def test_scope_gewichte_sind_absteigend_nach_naehe():
    assert (SCOPE_WEIGHT[KnowledgeScope.TROISDORF]
            > SCOPE_WEIGHT[KnowledgeScope.RHEIN_SIEG]
            > SCOPE_WEIGHT[KnowledgeScope.NRW]
            >= SCOPE_WEIGHT[KnowledgeScope.BUND])


def test_erfuellter_ausloeser_hebt_den_eintrag_zusaetzlich():
    ohne = FakeEntry(categories=["weather"])
    mit = FakeEntry(categories=["weather"],
                    trigger={"categories": ["weather"], "min_score": 60})
    scores = {"weather": {"score": 75}}
    assert score_entry(mit, scores) > score_entry(ohne, scores)


def test_unerfuellter_ausloeser_hebt_nicht():
    entry = FakeEntry(categories=["weather"],
                      trigger={"categories": ["weather"], "min_score": 90})
    ohne = FakeEntry(categories=["weather"])
    scores = {"weather": {"score": 40}}
    assert score_entry(entry, scores) == score_entry(ohne, scores)


def test_any_category_ausloeser_greift_bei_beliebiger_kategorie():
    entry = FakeEntry(categories=[], trigger={"any_category_min_score": 60})
    assert score_entry(entry, {"fire": {"score": 70}}) > 0
    assert score_entry(entry, {"fire": {"score": 30}}) == 0


def test_textsuche_findet_ueber_schlagworte():
    entry = FakeEntry(categories=["water"], tags=["Hochwasser", "Evakuierung"])
    scores = {"water": {"score": 50}}
    assert score_entry(entry, scores, query="Evakuierung") > score_entry(entry, scores)


def test_kurze_woerter_werden_nicht_gewertet():
    """Sonst treffen "in", "am", "A 3" praktisch jeden Eintrag.

    Die Grenze liegt bei drei Zeichen. Kurze Fuellwoerter wie "der" fallen
    damit nicht heraus — das ist hingenommen: die Suche verlangt Treffer in
    Titel, Text ODER Schlagworten, ein einzelnes Fuellwort als Suchbegriff
    waere ohnehin keine sinnvolle Anfrage.
    """
    assert _tokens("in am A 3") == set()
    assert all(len(t) >= MIN_TERM_LENGTH for t in _tokens("Hochwasser an der Sieg"))
    assert "sieg" in _tokens("Hochwasser an der Sieg")


def test_umlaute_bleiben_erhalten():
    assert "überflutung" in _tokens("Überflutung der Rheinaue")


def test_alarmierungsweg_benennt_beide_wege_und_die_grenze():
    """Der zweite Weg — Anruf der Feuerwehr beim Fuehrungsdienst — ist fuer ein
    Fruehwarnsystem unsichtbar. Das muss dokumentiert sein, sonst wird das
    System an etwas gemessen, das es nicht sehen kann."""
    body = _entry("eigen.alarmierungsweg")["body"]
    assert "Fuehrungsdienst" in body
    assert "KREISLEITSTELLE" in body
    assert "unsichtbar" in body


def test_ortsstufen_sind_im_wissen_hinterlegt():
    body = _entry("eigen.ortsstufen")["body"]
    for ort in ("SIEGBURG", "NIEDERKASSEL", "SANKT AUGUSTIN", "LOHMAR"):
        assert ort in body


def test_landesalarmierung_haelt_die_grundrate_fest():
    facts = _entry("eigen.landesalarmierung")["facts"]
    assert "Ahrhochwasser" in facts["letzte_alarmierung"]
    assert "Jahrzehnt" in facts["haeufigkeit"]


def test_ortsstufen_im_wissen_und_im_code_stimmen_ueberein():
    """Sonst behauptet die Wissensdatenbank etwas anderes als die Bewertung."""
    from app.services.knowledge.assessment import KERNGEBIET, NACHBARSCHAFT
    body = _entry("eigen.ortsstufen")["body"].lower()
    for ort in KERNGEBIET:
        assert ort in body, f"{ort} fehlt im Wissenseintrag"
    for ort in NACHBARSCHAFT:
        if "." in ort:
            continue  # Schreibvariante, im Fliesstext nicht noetig
        assert ort in body, f"{ort} fehlt im Wissenseintrag"


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
