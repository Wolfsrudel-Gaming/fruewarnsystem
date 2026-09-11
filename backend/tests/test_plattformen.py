"""Tests der Zugaenge zu den sozialen Netzen.

Die vier grossen Netze — Facebook, X, Instagram, TikTok — sind nicht mehr
frei abfragbar. Jedes hat einen Weg, aber jeder Weg kostet Geld, einen
Geschaeftszugang oder eine Pruefung durch den Betreiber. Diese Tests halten
zwei Grundsaetze fest:

ERSTENS: Ein Netz ohne Zugangsdaten ist STILL, nicht kaputt. Es darf den
Sammellauf nicht abbrechen und keine Fehlermeldung werfen — aber es darf
auch nicht so aussehen, als hoere es mit.

ZWEITENS: Der Unterschied zwischen "ruhig" und "nicht angeschlossen" muss
sichtbar bleiben. Ein Warnsystem, das ein abgeschaltetes Netz als Ruhe
ausgibt, luegt.
"""

import asyncio
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.collectors.social.plattformen import (
    HASHTAGS_SCHLICHT, PLATTFORMEN, SAMMLER_PLATTFORMEN, SUCHBEGRIFFE,
    _IG_KENNUNGEN, _facebook_abrufen, _instagram_abrufen, _telegram_abrufen,
    _text_von_html, _tiktok_abrufen, _x_abrufen, _zeit, abrufen_alle,
    plattform_status,
    tiktok_suchanfrage, x_suchanfrage,
)
from app.config import settings


class FakeAntwort:
    def __init__(self, status=200, daten=None, text=""):
        self.status_code = status
        self._daten = daten if daten is not None else {}
        self.text = text

    def json(self):
        return self._daten


class FakeClient:
    """Ein Client, der vorgegebene Antworten liefert und mitschreibt."""

    def __init__(self, antworten=None):
        self.antworten = antworten or {}
        self.aufrufe = []

    async def get(self, url, **kw):
        self.aufrufe.append(("GET", url, kw))
        for muster, antwort in self.antworten.items():
            if muster in url:
                return antwort
        return FakeAntwort(404, text="nicht hinterlegt")

    async def post(self, url, **kw):
        self.aufrufe.append(("POST", url, kw))
        for muster, antwort in self.antworten.items():
            if muster in url:
                return antwort
        return FakeAntwort(404, text="nicht hinterlegt")


class Zugangsdaten:
    """Zugangsdaten voruebergehend setzen und danach zurueckdrehen."""

    def __init__(self, **werte):
        self.werte = werte
        self.alt = {}

    def __enter__(self):
        for k, v in self.werte.items():
            self.alt[k] = getattr(settings, k)
            setattr(settings, k, v)
        return self

    def __exit__(self, *a):
        for k, v in self.alt.items():
            setattr(settings, k, v)
        return False


def _leer():
    """Alle Zugangsdaten leeren — der Auslieferungszustand."""
    return Zugangsdaten(
        bluesky_handle="", bluesky_app_password="", telegram_kanaele="",
        x_bearer_token="", meta_access_token="", facebook_seiten="",
        instagram_business_id="", tiktok_client_key="",
        tiktok_client_secret="",
    )


# --- Der Normalfall: kein Schluessel, kein Laerm ---

def test_ohne_zugangsdaten_bleibt_jedes_netz_still():
    with _leer():
        for key, p in PLATTFORMEN.items():
            assert p["fehlend"](), f"{key} gibt sich faelschlich als bereit"


def test_ohne_zugangsdaten_bricht_der_sammellauf_nicht_ab():
    """Ein fehlender Schluessel darf keinen Fehler werfen.

    Sonst faellt mit einem abgelaufenen Token der gesamte Sammellauf aus —
    und mit ihm die Netze, die noch funktionieren.
    """
    with _leer():
        client = FakeClient()
        assert asyncio.run(abrufen_alle(client)) == []
        # Keine einzige Anfrage: ohne Schluessel wird gar nicht erst gefragt.
        assert client.aufrufe == []


def test_eine_kaputte_plattform_reisst_die_anderen_nicht_mit():
    """Wenn X einen Fehler wirft, muss Telegram trotzdem liefern."""
    class Kaputt(FakeClient):
        async def get(self, url, **kw):
            if "twitter.com" in url:
                raise RuntimeError("Verbindung abgerissen")
            return await super().get(url, **kw)

    seite = ('<div class="tgme_widget_message_text">Rauch ueber Troisdorf</div>'
             '<div data-post="testkanal/7"></div>'
             '<time datetime="2026-09-11T18:00:00+00:00"></time>')
    with Zugangsdaten(telegram_kanaele="testkanal", x_bearer_token="geheim",
                      meta_access_token="", facebook_seiten="",
                      instagram_business_id="", tiktok_client_key="",
                      tiktok_client_secret=""):
        client = Kaputt({"t.me": FakeAntwort(200, text=seite)})
        # httpx.Response.text ist der Rohtext; FakeAntwort bildet das nach.
        beitraege = asyncio.run(abrufen_alle(client))
    assert [b["source"] for b in beitraege] == ["telegram"]


# --- Uebersicht: still ist nicht dasselbe wie ruhig ---

def test_status_listet_jedes_netz():
    keys = {p["key"] for p in plattform_status()}
    erwartet = {"mastodon", "bluesky", "telegram", "x", "facebook",
                "instagram", "tiktok"}
    assert erwartet <= keys, f"fehlt in der Uebersicht: {erwartet - keys}"


def test_status_nennt_die_fehlenden_zugangsdaten_beim_namen():
    """Nicht nur 'inaktiv' — es muss dastehen, WAS fehlt.

    Sonst sucht im Ernstfall jemand den Fehler an der falschen Stelle.
    """
    with _leer():
        stand = {p["key"]: p for p in plattform_status()}
    for key in ("x", "facebook", "instagram", "tiktok", "bluesky"):
        eintrag = stand[key]
        assert not eintrag["aktiv"]
        assert eintrag["fehlende_zugangsdaten"], key
        for name in eintrag["fehlende_zugangsdaten"]:
            assert name.startswith("FWS_"), f"{key}: {name} ist kein Schalter"


def test_mastodon_laeuft_immer():
    """Mastodon ist die Grundlast — es darf nie von Schluesseln abhaengen."""
    with _leer():
        stand = {p["key"]: p for p in plattform_status()}
    assert stand["mastodon"]["aktiv"]


def test_jedes_netz_erklaert_seinen_zugang():
    for p in plattform_status():
        assert p["zugang"] and len(p["zugang"]) > 20, p["key"]


def test_kosten_werden_benannt_wo_welche_anfallen():
    """X rechnet je gelesenem Beitrag ab. Das darf niemanden ueberraschen."""
    stand = {p["key"]: p for p in plattform_status()}
    assert stand["x"]["kosten"], "X-Kosten sind nicht ausgewiesen"
    assert stand["telegram"]["kosten"] is None
    assert stand["mastodon"]["kosten"] is None


# --- Suchausdruecke ---

def test_x_suchanfrage_verknuepft_mit_oder():
    a = x_suchanfrage(("Troisdorf", "Siegburg"))
    assert "Troisdorf OR Siegburg" in a


def test_x_suchanfrage_setzt_mehrwortbegriffe_in_anfuehrungszeichen():
    """Ohne Anfuehrungszeichen sucht X nach den Woertern einzeln —
    'Markt' allein waere reines Rauschen."""
    a = x_suchanfrage(("Pützchens Markt",))
    assert '"Pützchens Markt"' in a


def test_x_suchanfrage_schliesst_weiterleitungen_aus():
    """Ein tausendfach geteilter Beitrag ist EIN Ereignis, nicht tausend.

    Ohne -is:retweet wuerde die Aufkommensmessung eine einzige Meldung als
    Massenlage lesen.
    """
    assert "-is:retweet" in x_suchanfrage()


def test_tiktok_suchanfrage_bleibt_in_deutschland():
    a = tiktok_suchanfrage(tag=date(2026, 9, 11))
    bedingungen = a["query"]["and"]
    regionen = [b for b in bedingungen if b["field_name"] == "region_code"]
    assert regionen and regionen[0]["field_values"] == ["DE"]


def test_tiktok_suchanfrage_fragt_nur_die_juengste_vergangenheit_ab():
    a = tiktok_suchanfrage(tag=date(2026, 9, 11))
    assert a["start_date"] == "20260910"
    assert a["end_date"] == "20260911"


def test_suchbegriffe_bleiben_knapp():
    """Jeder zusaetzliche Begriff bringt mehr Alltag als Signal — und bei X
    kostet er Geld."""
    assert len(SUCHBEGRIFFE) <= 5
    assert len(HASHTAGS_SCHLICHT) <= 5


def test_hashtags_haben_keine_sonderzeichen():
    """Instagram und TikTok kennen keine Umlaute in Hashtags."""
    for tag in HASHTAGS_SCHLICHT:
        assert tag.isalnum() and tag.islower(), tag


# --- Telegram: das einzige neue Netz, das ohne Schluessel laeuft ---

def test_telegram_liest_beitrag_ort_und_zeit():
    seite = (
        '<div class="tgme_widget_message_text js-message_text">'
        'Gro&#223;einsatz in <b>Troisdorf</b></div>'
        '<div data-post="testkanal/42"></div>'
        '<time datetime="2026-09-11T18:30:00+00:00"></time>'
    )
    with Zugangsdaten(telegram_kanaele="testkanal"):
        client = FakeClient({"t.me": FakeAntwort(200, text=seite)})
        beitraege = asyncio.run(_telegram_abrufen(client))
    assert len(beitraege) == 1
    b = beitraege[0]
    assert b["content"] == "Großeinsatz in Troisdorf"
    assert b["post_id"] == "tg:testkanal/42"
    assert b["url"] == "https://t.me/testkanal/42"
    assert b["posted_at"] == datetime(2026, 9, 11, 18, 30)
    assert b["author"] == "@testkanal"


def test_telegram_kanal_ohne_vorschau_liefert_nichts_statt_fehler():
    """Ein Kanal ohne oeffentliche Vorschau leitet auf die Profilseite um.
    Dort steht kein Beitrag — das ist kein Fehler, nur nichts."""
    with Zugangsdaten(telegram_kanaele="gibtesnicht"):
        client = FakeClient({"t.me": FakeAntwort(200, text="<html></html>")})
        assert asyncio.run(_telegram_abrufen(client)) == []


def test_telegram_ohne_kanaele_ist_still():
    with Zugangsdaten(telegram_kanaele=""):
        assert PLATTFORMEN["telegram"]["fehlend"]()


# --- Form der gelieferten Beitraege ---

def test_alle_netze_liefern_dieselben_felder():
    """Der Sammler darf nicht wissen muessen, aus welchem Netz ein Beitrag
    kommt. Jede Abweichung im Aufbau faellt ihm sonst auf die Fuesse."""
    seite = ('<div class="tgme_widget_message_text">Brand in Troisdorf</div>'
             '<div data-post="k/1"></div>'
             '<time datetime="2026-09-11T18:00:00+00:00"></time>')
    with Zugangsdaten(telegram_kanaele="k"):
        client = FakeClient({"t.me": FakeAntwort(200, text=seite)})
        beitraege = asyncio.run(_telegram_abrufen(client))
    pflicht = {"source", "post_id", "author", "content", "url", "posted_at"}
    for b in beitraege:
        assert pflicht <= set(b), f"fehlende Felder: {pflicht - set(b)}"


def test_beitragskennungen_tragen_das_netz_im_namen():
    """Zwei Netze koennen dieselbe Zahl als Kennung vergeben. Ohne Vorsilbe
    wuerde ein Beitrag den eines anderen Netzes verdraengen."""
    vorsilben = {"telegram": "tg:", "x": "x:", "facebook": "fb:",
                 "instagram": "ig:", "tiktok": "tt:"}
    quelltext = Path(__file__).resolve().parents[1].joinpath(
        "app/collectors/social/plattformen.py").read_text(encoding="utf-8")
    for netz, vorsilbe in vorsilben.items():
        assert f'"{vorsilbe}' in quelltext or f"'{vorsilbe}" in quelltext, netz


def test_instagram_gibt_jedem_beitrag_einen_eigenen_urheber():
    """Instagram gibt bei der Hashtag-Suche keinen Urheber heraus.

    Die Aufkommensmessung zaehlt aber UNABHAENGIGE Konten. Waere der Urheber
    fuer alle Beitraege derselbe, wuerden hundert Beitraege als ein Konto
    zaehlen und das Aufkommen nie ausloesen.
    """
    antworten = {
        "ig_hashtag_search": FakeAntwort(200, {"data": [{"id": "17841"}]}),
        "recent_media": FakeAntwort(200, {"data": [
            {"id": "111", "caption": "Rauch ueber Troisdorf",
             "permalink": "https://instagram.com/p/a",
             "timestamp": "2026-09-11T18:30:00+0000"},
            {"id": "222", "caption": "Feuerwehr in Troisdorf",
             "permalink": "https://instagram.com/p/b",
             "timestamp": "2026-09-11T18:31:00+0000"},
        ]}),
    }
    with Zugangsdaten(meta_access_token="token",
                      instagram_business_id="12345"):
        _IG_KENNUNGEN.clear()
        beitraege = asyncio.run(_instagram_abrufen(FakeClient(antworten)))
    # Derselbe Beitrag kommt unter mehreren Hashtags zurueck; der Sammler
    # fasst ihn ueber die Kennung zusammen. Geprueft wird deshalb die
    # zusammengefasste Menge.
    eindeutig = {b["post_id"]: b for b in beitraege}
    urheber = {b["author"] for b in eindeutig.values()}
    assert len(urheber) == len(eindeutig) > 1, \
        "alle Instagram-Beitraege teilen sich einen Urheber"


def test_instagram_merkt_sich_die_hashtag_kennung():
    """Instagram erlaubt nur 30 verschiedene Hashtags je Woche. Wuerde jeder
    Durchlauf die Kennung neu abfragen, waere das Kontingent binnen Stunden
    aufgebraucht und die Quelle fuer den Rest der Woche tot."""
    antworten = {
        "ig_hashtag_search": FakeAntwort(200, {"data": [{"id": "17841"}]}),
        "recent_media": FakeAntwort(200, {"data": []}),
    }
    with Zugangsdaten(meta_access_token="token",
                      instagram_business_id="12345"):
        _IG_KENNUNGEN.clear()
        client = FakeClient(antworten)
        asyncio.run(_instagram_abrufen(client))
        erste_runde = sum(1 for a in client.aufrufe
                          if "ig_hashtag_search" in a[1])
        client2 = FakeClient(antworten)
        asyncio.run(_instagram_abrufen(client2))
        zweite_runde = sum(1 for a in client2.aufrufe
                           if "ig_hashtag_search" in a[1])
    assert erste_runde == len(HASHTAGS_SCHLICHT)
    assert zweite_runde == 0, "Hashtag-Kennung wird unnoetig neu abgefragt"


def test_x_liest_beitrag_urheber_und_zeit():
    antworten = {"tweets/search/recent": FakeAntwort(200, {
        "data": [{"id": "999", "text": "Grosseinsatz in Troisdorf",
                  "author_id": "7", "created_at": "2026-09-11T18:30:00.000Z"}],
        "includes": {"users": [{"id": "7", "username": "melder"}]},
    })}
    with Zugangsdaten(x_bearer_token="geheim"):
        beitraege = asyncio.run(_x_abrufen(FakeClient(antworten)))
    assert len(beitraege) == 1
    b = beitraege[0]
    assert b["source"] == "x" and b["author"] == "@melder"
    assert b["post_id"] == "x:999"
    assert b["posted_at"] == datetime(2026, 9, 11, 18, 30)
    assert b["url"] == "https://x.com/melder/status/999"


def test_facebook_liest_beitraege_benannter_seiten():
    antworten = {"/feed": FakeAntwort(200, {"data": [
        {"id": "1_2", "message": "Brand in Troisdorf",
         "created_time": "2026-09-11T18:30:00+0000",
         "permalink_url": "https://facebook.com/1_2"},
        # Ein Beitrag ohne Text (nur Bild) darf nicht als leerer Beitrag
        # durchrutschen — er waere ein Konto mehr im Aufkommen ohne Inhalt.
        {"id": "1_3", "created_time": "2026-09-11T18:31:00+0000"},
    ]})}
    with Zugangsdaten(meta_access_token="token",
                      facebook_seiten="feuerwehrtroisdorf"):
        beitraege = asyncio.run(_facebook_abrufen(FakeClient(antworten)))
    assert len(beitraege) == 1
    assert beitraege[0]["post_id"] == "fb:1_2"
    assert beitraege[0]["posted_at"] == datetime(2026, 9, 11, 18, 30)


def test_tiktok_liest_videobeschreibungen():
    antworten = {
        "oauth/token": FakeAntwort(200, {"access_token": "abc"}),
        "research/video/query": FakeAntwort(200, {"data": {"videos": [
            {"id": "555", "video_description": "Rauch ueber Troisdorf",
             "create_time": 1789151400, "username": "melder"},
        ]}}),
    }
    with Zugangsdaten(tiktok_client_key="k", tiktok_client_secret="s"):
        beitraege = asyncio.run(_tiktok_abrufen(FakeClient(antworten)))
    assert len(beitraege) == 1
    b = beitraege[0]
    assert b["source"] == "tiktok" and b["post_id"] == "tt:555"
    assert b["posted_at"] == datetime(2026, 9, 11, 18, 30)


def test_abgelehnter_zugang_liefert_nichts_statt_muell():
    """Ein abgelaufenes Token beantwortet jede Anfrage mit einem Fehler.
    Daraus darf kein Beitrag entstehen — und kein Absturz."""
    abgelehnt = FakeAntwort(401, {"error": "token expired"}, "abgelaufen")
    with Zugangsdaten(x_bearer_token="alt", meta_access_token="alt",
                      facebook_seiten="seite", instagram_business_id="1",
                      tiktok_client_key="k", tiktok_client_secret="s"):
        client = FakeClient({"": abgelehnt})
        _IG_KENNUNGEN.clear()
        assert asyncio.run(_x_abrufen(client)) == []
        assert asyncio.run(_facebook_abrufen(client)) == []
        assert asyncio.run(_instagram_abrufen(client)) == []
        assert asyncio.run(_tiktok_abrufen(client)) == []


# --- Zeitangaben: jedes Netz schreibt sie anders ---

def test_zeit_versteht_die_schreibweisen_aller_netze():
    erwartet = datetime(2026, 9, 11, 18, 30)
    # Mastodon/Bluesky/Instagram
    assert _zeit("2026-09-11T18:30:00Z") == erwartet
    # X
    assert _zeit("2026-09-11T18:30:00.000Z") == erwartet
    # Facebook schreibt +0000 statt +00:00
    assert _zeit("2026-09-11T18:30:00+0000") == erwartet
    # TikTok liefert Sekunden seit 1970
    assert _zeit(1789151400) == erwartet


def test_zeit_rechnet_zeitzonen_um():
    """Ein Beitrag mit Ortszeit darf nicht zwei Stunden in der Zukunft
    landen — sonst faellt er aus jedem Zeitfenster heraus."""
    assert _zeit("2026-09-11T20:30:00+02:00") == datetime(2026, 9, 11, 18, 30)


def test_zeit_bricht_bei_unsinn_nicht():
    for unsinn in (None, "", "morgen", "2026-13-45", {}):
        assert _zeit(unsinn) is None


def test_text_von_html_entfernt_auszeichnungen():
    assert _text_von_html("<b>Feuer</b> in&nbsp;Troisdorf") == \
        "Feuer in Troisdorf"


# --- Was bewusst NICHT gebaut wurde ---

def test_keine_umgehung_ueber_spiegelseiten():
    """Nitter, RSSHub und aehnliche Weiterleitungen sind bewusst nicht
    eingebaut: Sie verstossen gegen die Nutzungsbedingungen und fallen ohne
    Vorwarnung aus. Eine Fruehwarnquelle, die jederzeit verschwinden kann,
    ist schlimmer als eine, die es gar nicht erst verspricht.
    """
    quelltext = Path(__file__).resolve().parents[1].joinpath(
        "app/collectors/social/plattformen.py").read_text(encoding="utf-8")
    for umweg in ("nitter", "rsshub", "syndication.twitter",
                  "mbasic.facebook", "instagram.com/api/v1"):
        # Im erklaerenden Text duerfen sie vorkommen, aber nicht als Adresse.
        assert f"https://{umweg}" not in quelltext.lower(), umweg


def test_registrierte_netze_haben_alle_pflichtfelder():
    for key, p in PLATTFORMEN.items():
        for feld in ("label", "zugang", "kosten", "fehlend", "abrufen"):
            assert feld in p, f"{key} fehlt {feld}"
    for key, p in SAMMLER_PLATTFORMEN.items():
        for feld in ("label", "zugang", "kosten", "fehlend"):
            assert feld in p, f"{key} fehlt {feld}"


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
