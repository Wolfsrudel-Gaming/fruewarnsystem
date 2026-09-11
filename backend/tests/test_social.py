"""Tests des Mithoerens in sozialen Netzen.

Soziale Netze sind der frueheste Kanal — wer auf einem Volksfest steht und
etwas sieht, schreibt darueber, lange bevor eine Leitstelle eine Meldung
herausgibt. Und sie sind der unzuverlaessigste.

Der Grundsatz, den diese Tests festhalten: EIN Beitrag ist ein Geruecht.
Alarmiert wird nie auf einen einzelnen Beitrag, sondern erst, wenn mehrere
UNABHAENGIGE Konten binnen kurzer Zeit dasselbe zu einem Ort schreiben.
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.collectors.social.social_collector import (
    ENTWERTENDE_BEGRIFFE, EREIGNIS_BEGRIFFE, _text_von_html, bewerte_beitrag,
)
from app.services.knowledge.social_burst import (
    MIN_BEITRAEGE, MIN_KONTEN, RELEVANTE_ZONEN, STARKES_AUFKOMMEN_KONTEN,
    beschreibe, finde_aufkommen,
)

JETZT = datetime(2026, 9, 11, 20, 0)
RUHIGER_TAG = date(2026, 3, 15)


class FakePost:
    def __init__(self, place, scope, author, vor_minuten,
                 keywords=(), content=""):
        self.place = place
        self.scope = scope
        self.author = author
        self.posted_at = JETZT - timedelta(minutes=vor_minuten)
        self.created_at = self.posted_at
        self.keywords = list(keywords)
        self.content = content


def _gruppe(anzahl, scope="nachbarschaft", ort="Puetzchen",
            konten=None, keywords=("rauch", "feuerwehr")):
    konten = konten if konten is not None else anzahl
    return [
        FakePost(ort, scope, f"konto{i % konten}", i * 3, keywords,
                 "Rauch ueber dem Platz")
        for i in range(anzahl)
    ]


# --- Einstufung einzelner Beitraege ---

def test_ereignis_mit_ort_wird_erkannt():
    b = bewerte_beitrag("Riesiger Feuerwehreinsatz in Troisdorf, alles voll Rauch")
    assert b["is_incident"]
    assert b["place"] == "Troisdorf"
    assert "feuerwehr" in b["keywords"]


def test_ereignis_ohne_ort_zaehlt_nicht():
    """Sonst waere jeder Brand irgendwo auf der Welt ein Treffer."""
    assert not bewerte_beitrag("Grosser Brand, viel Rauch")["is_incident"]


def test_ort_ohne_ereignis_zaehlt_nicht():
    """Alltagsgeplauder wuerde die Aufkommensmessung verwaessern."""
    assert not bewerte_beitrag("Schoenes Wetter heute in Troisdorf")["is_incident"]


def test_uebung_wird_entwertet():
    """Eine angekuendigte Uebung ist kein Ereignis."""
    assert not bewerte_beitrag(
        "Feuerwehruebung in Troisdorf am Samstag")["is_incident"]


def test_stellenanzeige_wird_entwertet():
    """Echter Fall aus der Mastodon-Zeitleiste vom 11.09.2026."""
    assert not bewerte_beitrag(
        "Die Stadt Troisdorf sucht ein Geoinformatiker*in, Stellenangebot"
    )["is_incident"]


def test_rueckblick_wird_entwertet():
    assert not bewerte_beitrag(
        "Vor Jahren gab es in Siegburg einen grossen Brand, ein Rueckblick"
    )["is_incident"]


def test_mehr_stichworte_erhoehen_die_relevanz():
    wenig = bewerte_beitrag("Sirene in Troisdorf")
    viel = bewerte_beitrag(
        "Sirene, Feuerwehr, Notarzt und Hubschrauber in Troisdorf, alles gesperrt")
    assert viel["relevance"] > wenig["relevance"]


def test_relevanz_bleibt_begrenzt():
    text = "Troisdorf " + " ".join(EREIGNIS_BEGRIFFE)
    assert bewerte_beitrag(text)["relevance"] <= 1.0


def test_puetzchens_markt_zaehlt_als_nachbarschaft():
    """Puetzchen gehoert zu Bonn, grenzt aber an Sankt Augustin — und es
    faehrt eine Sonderbuslinie aus Troisdorf."""
    b = bewerte_beitrag("Grosseinsatz auf Puetzchens Markt, Panik im Gedraenge")
    assert b["is_incident"]
    assert b["scope"] == "nachbarschaft"


def test_entwertende_begriffe_schlagen_ereignisbegriffe():
    for wort in ENTWERTENDE_BEGRIFFE[:4]:
        text = f"Feuer in Troisdorf {wort}"
        assert not bewerte_beitrag(text)["is_incident"], wort


def test_html_wird_zu_text():
    roh = '<p>Rauch ueber <a href="#">#Troisdorf</a>&nbsp;&amp; Sirenen</p>'
    text = _text_von_html(roh)
    assert "<" not in text and "&amp;" not in text
    assert "Troisdorf" in text


def test_leerer_beitrag_bricht_nicht():
    for text in ("", None):
        assert not bewerte_beitrag(text)["is_incident"]


# --- Aufkommen: der eigentliche Schutz vor Fehlalarmen ---

def test_mehrere_konten_loesen_aufkommen_aus():
    treffer = finde_aufkommen(_gruppe(3), jetzt=JETZT)
    assert treffer is not None
    assert treffer["konten"] == 3


def test_ein_einzelnes_konto_loest_nichts_aus():
    """Wer fuenfmal dasselbe schreibt, bleibt eine Quelle."""
    assert finde_aufkommen(_gruppe(5, konten=1), jetzt=JETZT) is None


def test_zu_wenige_beitraege_loesen_nichts_aus():
    assert finde_aufkommen(_gruppe(MIN_BEITRAEGE - 1), jetzt=JETZT) is None


def test_schwellen_sind_bewusst_niedrig_aber_nicht_eins():
    """Ein einzelner Beitrag darf nie genuegen — das ist der Kern."""
    assert MIN_BEITRAEGE >= 2
    assert MIN_KONTEN >= 2


def test_alte_beitraege_zaehlen_nicht():
    alt = [FakePost("Troisdorf", "troisdorf", f"k{i}", 120 + i, ["feuer"])
           for i in range(5)]
    assert finde_aufkommen(alt, jetzt=JETZT) is None


def test_beitraege_aus_der_zukunft_zaehlen_nicht():
    """Falsche Zeitstempel kommen vor und duerfen nichts ausloesen."""
    zukunft = [FakePost("Troisdorf", "troisdorf", f"k{i}", -60, ["feuer"])
               for i in range(5)]
    assert finde_aufkommen(zukunft, jetzt=JETZT) is None


def test_entfernte_orte_loesen_nichts_aus():
    """Ein Grossbrand in Hamburg erzeugt ebenfalls Aufkommen."""
    assert finde_aufkommen(
        _gruppe(6, scope="ausserhalb", ort="Hamburg"), jetzt=JETZT) is None
    assert "ausserhalb" not in RELEVANTE_ZONEN


def test_starkes_aufkommen_wird_gekennzeichnet():
    schwach = finde_aufkommen(_gruppe(3), jetzt=JETZT)
    stark = finde_aufkommen(_gruppe(STARKES_AUFKOMMEN_KONTEN + 2), jetzt=JETZT)
    assert not schwach["stark"]
    assert stark["stark"]


def test_ort_mit_mehr_konten_gewinnt():
    posts = _gruppe(3, ort="Troisdorf", scope="troisdorf") + \
            _gruppe(6, ort="Puetzchen", scope="nachbarschaft")
    assert finde_aufkommen(posts, jetzt=JETZT)["ort"] == "Puetzchen"


def test_leere_eingabe_bricht_nicht():
    assert finde_aufkommen([], jetzt=JETZT) is None


def test_beschreibung_nennt_die_unsicherheit():
    """Das Wichtigste am Text: Es ist unbestaetigt."""
    text = beschreibe(finde_aufkommen(_gruppe(4), jetzt=JETZT))
    assert "UNBESTAETIGT" in text
    assert "Amtliche Quellen" in text


# --- Wirkung auf die Einsatzerwartung ---

def _lage_mit_aufkommen(konten=5):
    treffer = finde_aufkommen(_gruppe(konten + 1, konten=konten), jetzt=JETZT)
    return {"social": {"score": 0, "weight": 0.0, "detail": "Aufkommen",
                       "burst": treffer, "contributions": []}}


def test_aufkommen_hebt_auf_bereitstellung_nicht_auf_einsatz():
    """Solange nichts bestaetigt ist, ist Nachsehen die richtige Reaktion."""
    from app.services.knowledge.assessment import assess_deployment
    ergebnis = assess_deployment(_lage_mit_aufkommen(), {}, tag=RUHIGER_TAG)
    assert ergebnis["level"] == "bereitstellung_moeglich"
    assert ergebnis["level"] != "einsatz_wahrscheinlich"


def test_aufkommen_waehrend_einer_grosslage_wiegt_schwerer():
    """Auf einem Volksfest mit sechsstelliger Besucherzahl ist ein
    ploetzliches Aufkommen deutlich wahrscheinlicher echt."""
    from app.services.knowledge.assessment import assess_deployment
    ruhig = assess_deployment(_lage_mit_aufkommen(), {}, tag=RUHIGER_TAG)
    wachsam = assess_deployment(_lage_mit_aufkommen(), {},
                                tag=date(2026, 9, 11))
    assert wachsam["value"] > ruhig["value"]
    assert wachsam["level"] == "bereitstellung_wahrscheinlich"


def test_ohne_aufkommen_kein_signal():
    from app.services.knowledge.signals import social_signal
    assert social_signal({}) is None
    assert social_signal({"social": {"burst": None}}) is None


def test_signal_ist_als_unbestaetigt_gekennzeichnet():
    from app.services.knowledge.signals import social_signal
    signal = social_signal(_lage_mit_aufkommen())
    assert signal["unbestaetigt"] is True
    assert "UNBESTAETIGT" in signal["hinweis"]


def test_social_traegt_nichts_zum_gesamtrisiko_bei():
    """Ein unbestaetigtes Geruecht darf die Gesamtlage nicht anheben.

    Die Wirkung laeuft ausschliesslich ueber das Signal, das die Unsicherheit
    ausdruecklich benennt.
    """
    from app.services.alert.alert_engine import aggregate_overall_score
    lage = _lage_mit_aufkommen()
    ergebnis = aggregate_overall_score(
        {k: {"score": v["score"], "weight": v["weight"]}
         for k, v in lage.items()})
    assert ergebnis["score"] == 0


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
