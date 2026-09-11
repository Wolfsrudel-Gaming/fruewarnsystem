"""Die einzelnen Netze, aus denen mitgehoert wird.

Jedes Netz ist eine Plattform mit gleicher Form: Es sagt, was es zum Arbeiten
braucht, ob es das hat, und liefert im Betrieb eine Liste von Beitraegen im
immer selben Format. Der Sammler in social_collector.py fragt nur die Liste
ab und weiss nicht, welches Netz dahinter steckt.

WARUM DIESE FORM
Die vier grossen Netze — Facebook, X, Instagram, TikTok — sind nicht mehr
frei abfragbar. Jedes hat einen Weg, aber jeder Weg kostet Geld, einen
Geschaeftszugang oder eine Pruefung durch den Betreiber. Diese Wege sind hier
vollstaendig gebaut und schalten sich selbst zu, sobald Zugangsdaten
hinterlegt sind. Ohne Zugangsdaten bleibt die Plattform still — das ist kein
Fehler, sondern der eingebaute Normalfall.

Was NICHT gebaut wird: Abgreifen ueber Umwege — Spiegelseiten, ausgelesene
Web-Oberflaechen, gemietete Weiterleitungen. Das verstoesst gegen die
Nutzungsbedingungen, bricht bei jeder Aenderung der Seite, und ein
Warnsystem, dessen frueheste Quelle jederzeit ohne Vorwarnung ausfallen
kann, ist schlimmer als eines, das diese Quelle gar nicht erst verspricht.

STAND DER ZUGAENGE (geprueft am 11.09.2026)
  mastodon   offen, ohne Anmeldung                        LAEUFT
  telegram   offene Kanalvorschau, ohne Anmeldung         LAEUFT
  bluesky    App-Passwort noetig                          bereit
  x          API v2, kostenpflichtig je Abruf             bereit
  facebook   Graph API + Page Public Content Access       bereit
  instagram  Graph API + Geschaeftskonto, 30 Tags/Woche   bereit
  tiktok     Research API, Antrag noetig                  bereit
"""

import html
import logging
import re
from datetime import datetime, timedelta, timezone

from app.config import settings

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
USER_AGENT = "DRK-Fruehwarnsystem/1.0 (Bevoelkerungsschutz Troisdorf)"

# Suchbegriffe mit Ortsbezug. Bewusst knapp gehalten: Jeder weitere Begriff
# bringt mehr Alltagsgeplauder als Signal — und bei den kostenpflichtigen
# Netzen kostet jeder Begriff zusaetzlich Geld.
SUCHBEGRIFFE = ("Troisdorf", "Siegburg", "Pützchens Markt")

# Hashtags ohne Sonderzeichen — Instagram und TikTok verlangen das.
HASHTAGS_SCHLICHT = ("troisdorf", "siegburg", "puetzchensmarkt")


def _liste(roh: str) -> tuple:
    """Kommagetrennte Einstellung in eine Liste zerlegen."""
    return tuple(t.strip() for t in (roh or "").split(",") if t.strip())


def _zeit(roh) -> object:
    """Zeitangabe in eine naive UTC-Zeit uebersetzen."""
    if not roh:
        return None
    if isinstance(roh, (int, float)):
        try:
            return datetime.fromtimestamp(float(roh), timezone.utc).replace(
                tzinfo=None)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(roh).strip()
    # Facebook liefert +0000 statt +00:00
    text = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", text.replace("Z", "+00:00"))
    try:
        gelesen = datetime.fromisoformat(text)
    except ValueError:
        return None
    if gelesen.tzinfo is None:
        return gelesen
    return gelesen.astimezone(timezone.utc).replace(tzinfo=None)


def _text_von_html(roh: str) -> str:
    ohne_tags = re.sub(r"<[^>]+>", " ", roh or "")
    return " ".join(html.unescape(ohne_tags).split())


# ---------------------------------------------------------------------------
# Telegram — offene Kanalvorschau
# ---------------------------------------------------------------------------
# Jeder oeffentliche Kanal ist unter t.me/s/<name> als schlichte HTML-Seite
# lesbar, ohne Anmeldung und ohne Schluessel. Das ist keine Umgehung, sondern
# die von Telegram selbst dafuer vorgesehene Vorschau.
#
# Die Einschraenkung: Es gibt keine Suche. Man muss die Kanaele kennen. Eine
# Suche nach Kanaelen deutscher Behoerden hat am 11.09.2026 keine offiziellen
# Kanaele von Feuerwehr, Polizei oder Kreis ergeben — deutsche Behoerden
# nutzen Telegram kaum. Voreingestellt ist deshalb nur die tagesschau, die
# bei einer ueberoertlichen Lage frueh berichtet. Regionale Kanaele lassen
# sich ueber FWS_TELEGRAM_KANAELE ergaenzen.

_TG_BEITRAG = re.compile(
    r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', re.S)
_TG_POST = re.compile(r'data-post="([^"]+)"')
_TG_ZEIT = re.compile(r'<time datetime="([^"]+)"')


def _telegram_fehlend() -> list:
    return [] if _liste(settings.telegram_kanaele) else ["FWS_TELEGRAM_KANAELE"]


async def _telegram_abrufen(client) -> list:
    ergebnis = []
    for kanal in _liste(settings.telegram_kanaele):
        try:
            resp = await client.get(
                f"https://t.me/s/{kanal}",
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
            )
            if resp.status_code != 200:
                continue
            seite = resp.text
            # Ein Kanal ohne oeffentliche Vorschau leitet auf die Profilseite
            # um; dann steht schlicht kein Beitrag in der Seite.
            texte = _TG_BEITRAG.findall(seite)
            posts = _TG_POST.findall(seite)
            zeiten = _TG_ZEIT.findall(seite)
            for i, roh in enumerate(texte):
                text = _text_von_html(roh)
                if not text:
                    continue
                pfad = posts[i] if i < len(posts) else f"{kanal}/{i}"
                ergebnis.append({
                    "source": "telegram",
                    "post_id": f"tg:{pfad}"[:300],
                    "author": f"@{kanal}"[:200],
                    "content": text[:2000],
                    "url": f"https://t.me/{pfad}"[:1000],
                    "posted_at": _zeit(zeiten[i] if i < len(zeiten) else None),
                })
        except Exception as e:
            logger.debug("Telegram-Kanal %s nicht erreichbar: %s", kanal, e)
    return ergebnis


# ---------------------------------------------------------------------------
# X (Twitter) — API v2, Beitragssuche der letzten sieben Tage
# ---------------------------------------------------------------------------
# Der freie Zugang ist ersatzlos entfallen. Seit Februar 2026 rechnet X je
# Abruf ab (Groessenordnung ein halber Cent je gelesenem Beitrag). Fuer ein
# Warnsystem ist das vertretbar, weil nur wenige Ortsbegriffe abgefragt
# werden — aber es ist eine bewusste Ausgabe und schaltet sich deshalb nur
# mit hinterlegtem Schluessel zu.

def _x_fehlend() -> list:
    return [] if settings.x_bearer_token else ["FWS_X_BEARER_TOKEN"]


def x_suchanfrage(begriffe=SUCHBEGRIFFE) -> str:
    """Suchausdruck fuer die X-Beitragssuche.

    Reine Funktion, damit der Ausdruck pruefbar bleibt — ein Tippfehler darin
    wuerde sonst still nichts liefern und wie Ruhe aussehen.
    """
    oder = " OR ".join(
        f'"{b}"' if " " in b else b for b in begriffe)
    return f"({oder}) -is:retweet lang:de"


async def _x_abrufen(client) -> list:
    try:
        resp = await client.get(
            "https://api.twitter.com/2/tweets/search/recent",
            params={
                "query": x_suchanfrage(),
                "max_results": 50,
                "tweet.fields": "created_at",
                "expansions": "author_id",
                "user.fields": "username",
            },
            timeout=REQUEST_TIMEOUT,
            headers={"Authorization": f"Bearer {settings.x_bearer_token}",
                     "User-Agent": USER_AGENT},
        )
        if resp.status_code != 200:
            logger.warning("X-Beitragssuche: HTTP %s — %s",
                           resp.status_code, resp.text[:200])
            return []
        daten = resp.json() or {}
        namen = {n["id"]: n.get("username", "unbekannt")
                 for n in (daten.get("includes") or {}).get("users", [])}
        ergebnis = []
        for post in daten.get("data") or []:
            text = (post.get("text") or "").strip()
            if not text:
                continue
            autor = namen.get(post.get("author_id"), "unbekannt")
            ergebnis.append({
                "source": "x",
                "post_id": f"x:{post.get('id')}"[:300],
                "author": f"@{autor}"[:200],
                "content": text[:2000],
                "url": f"https://x.com/{autor}/status/{post.get('id')}"[:1000],
                "posted_at": _zeit(post.get("created_at")),
            })
        return ergebnis
    except Exception as e:
        logger.debug("X nicht erreichbar: %s", e)
        return []


# ---------------------------------------------------------------------------
# Facebook — Graph API, Beitraege oeffentlicher Seiten
# ---------------------------------------------------------------------------
# Eine allgemeine Suche ueber Facebook gibt es nicht mehr. Lesbar sind die
# Beitraege benannter Seiten — etwa der Feuerwehr, der Stadt, der Polizei.
# Dafuer braucht die App die Berechtigung "Page Public Content Access", die
# Meta einzeln pruefen und freigeben muss (Unternehmensnachweis, mehrere
# Wochen Bearbeitung). Seiten, die man selbst verwaltet, gehen sofort.
#
# Fuer ein Warnsystem ist das der brauchbarere Weg als eine Suche: Die
# Feuerwehrseite meldet Einsaetze zuverlaessiger als zufaellige Passanten.

GRAPH_VERSION = "v25.0"


def _facebook_fehlend() -> list:
    fehlt = []
    if not settings.meta_access_token:
        fehlt.append("FWS_META_ACCESS_TOKEN")
    if not _liste(settings.facebook_seiten):
        fehlt.append("FWS_FACEBOOK_SEITEN")
    return fehlt


async def _facebook_abrufen(client) -> list:
    ergebnis = []
    for seite in _liste(settings.facebook_seiten):
        try:
            resp = await client.get(
                f"https://graph.facebook.com/{GRAPH_VERSION}/{seite}/feed",
                params={"fields": "message,created_time,permalink_url",
                        "limit": 25,
                        "access_token": settings.meta_access_token},
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
            )
            if resp.status_code != 200:
                logger.warning("Facebook-Seite %s: HTTP %s — %s", seite,
                               resp.status_code, resp.text[:200])
                continue
            for post in (resp.json() or {}).get("data") or []:
                text = (post.get("message") or "").strip()
                if not text:
                    continue
                ergebnis.append({
                    "source": "facebook",
                    "post_id": f"fb:{post.get('id')}"[:300],
                    "author": f"fb/{seite}"[:200],
                    "content": text[:2000],
                    "url": (post.get("permalink_url") or "")[:1000] or None,
                    "posted_at": _zeit(post.get("created_time")),
                })
        except Exception as e:
            logger.debug("Facebook-Seite %s nicht erreichbar: %s", seite, e)
    return ergebnis


# ---------------------------------------------------------------------------
# Instagram — Graph API, Hashtag-Suche
# ---------------------------------------------------------------------------
# Die Hashtag-Suche ist die einzige oeffentliche Suche, die Instagram noch
# anbietet. Sie verlangt ein Geschaeftskonto, das mit einer Facebook-Seite
# verbunden ist, und eine gepruefte App. Harte Grenze: 30 verschiedene
# Hashtags je Woche und Konto. Deshalb wird die knappe Liste
# HASHTAGS_SCHLICHT abgefragt und nicht mehr — und die Hashtag-Kennungen
# werden gemerkt, damit nicht jeder Durchlauf erneut auf das Wochenkontingent
# zaehlt.

_IG_KENNUNGEN: dict = {}


def _instagram_fehlend() -> list:
    fehlt = []
    if not settings.meta_access_token:
        fehlt.append("FWS_META_ACCESS_TOKEN")
    if not settings.instagram_business_id:
        fehlt.append("FWS_INSTAGRAM_BUSINESS_ID")
    return fehlt


async def _instagram_kennung(client, tag: str):
    """Hashtag-Kennung holen und merken (Wochenkontingent schonen)."""
    if tag in _IG_KENNUNGEN:
        return _IG_KENNUNGEN[tag]
    resp = await client.get(
        f"https://graph.facebook.com/{GRAPH_VERSION}/ig_hashtag_search",
        params={"user_id": settings.instagram_business_id, "q": tag,
                "access_token": settings.meta_access_token},
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    )
    if resp.status_code != 200:
        logger.warning("Instagram-Hashtag %s: HTTP %s — %s", tag,
                       resp.status_code, resp.text[:200])
        return None
    eintraege = (resp.json() or {}).get("data") or []
    kennung = eintraege[0].get("id") if eintraege else None
    if kennung:
        _IG_KENNUNGEN[tag] = kennung
    return kennung


async def _instagram_abrufen(client) -> list:
    ergebnis = []
    for tag in HASHTAGS_SCHLICHT:
        try:
            kennung = await _instagram_kennung(client, tag)
            if not kennung:
                continue
            resp = await client.get(
                f"https://graph.facebook.com/{GRAPH_VERSION}/{kennung}"
                f"/recent_media",
                params={"user_id": settings.instagram_business_id,
                        "fields": "caption,permalink,timestamp",
                        "access_token": settings.meta_access_token},
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
            )
            if resp.status_code != 200:
                continue
            for post in (resp.json() or {}).get("data") or []:
                text = (post.get("caption") or "").strip()
                if not text:
                    continue
                ergebnis.append({
                    "source": "instagram",
                    "post_id": f"ig:{post.get('id')}"[:300],
                    # Instagram gibt bei der Hashtag-Suche bewusst keinen
                    # Urheber heraus. Fuer die Aufkommensmessung zaehlt aber
                    # die Zahl UNABHAENGIGER Konten — ohne Urheber waere jeder
                    # Beitrag dasselbe Konto. Der Beitrag selbst dient deshalb
                    # als Ersatzkennung.
                    "author": f"ig:{post.get('id')}"[:200],
                    "content": text[:2000],
                    "url": (post.get("permalink") or "")[:1000] or None,
                    "posted_at": _zeit(post.get("timestamp")),
                })
        except Exception as e:
            logger.debug("Instagram-Hashtag %s nicht erreichbar: %s", tag, e)
    return ergebnis


# ---------------------------------------------------------------------------
# TikTok — Research API
# ---------------------------------------------------------------------------
# TikTok gibt oeffentliche Daten nur ueber die Research API heraus. Zugang
# haben Forschungseinrichtungen und gemeinnuetzige Organisationen mit einem
# Forschungszweck im oeffentlichen Interesse; der Antrag wird einzeln
# geprueft. Ein Hilfsorganisations-Warnsystem kann das begruenden, muss den
# Antrag aber stellen — einen Selbstbedienungszugang gibt es nicht.
#
# Die zweite Schnittstelle (Display API) zeigt ausschliesslich die eigenen
# Videos des angemeldeten Kontos und ist fuer Lagefrueherkennung wertlos.

def _tiktok_fehlend() -> list:
    fehlt = []
    if not settings.tiktok_client_key:
        fehlt.append("FWS_TIKTOK_CLIENT_KEY")
    if not settings.tiktok_client_secret:
        fehlt.append("FWS_TIKTOK_CLIENT_SECRET")
    return fehlt


def tiktok_suchanfrage(begriffe=HASHTAGS_SCHLICHT, tag=None) -> dict:
    """Abfragekoerper fuer die TikTok Research API.

    Reine Funktion — der Aufbau ist verschachtelt genug, dass er einzeln
    pruefbar sein muss.
    """
    heute = tag or datetime.utcnow().date()
    gestern = heute - timedelta(days=1)
    return {
        "query": {"and": [
            {"operation": "IN", "field_name": "region_code",
             "field_values": ["DE"]},
            {"operation": "IN", "field_name": "keyword",
             "field_values": list(begriffe)},
        ]},
        "start_date": gestern.strftime("%Y%m%d"),
        "end_date": heute.strftime("%Y%m%d"),
        "max_count": 100,
    }


async def _tiktok_abrufen(client) -> list:
    try:
        anmeldung = await client.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            data={"client_key": settings.tiktok_client_key,
                  "client_secret": settings.tiktok_client_secret,
                  "grant_type": "client_credentials"},
            timeout=REQUEST_TIMEOUT,
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "User-Agent": USER_AGENT},
        )
        if anmeldung.status_code != 200:
            logger.warning("TikTok-Anmeldung: HTTP %s", anmeldung.status_code)
            return []
        token = (anmeldung.json() or {}).get("access_token")
        if not token:
            return []

        resp = await client.post(
            "https://open.tiktokapis.com/v2/research/video/query/",
            params={"fields": "id,video_description,create_time,username"},
            json=tiktok_suchanfrage(),
            timeout=REQUEST_TIMEOUT,
            headers={"Authorization": f"Bearer {token}",
                     "User-Agent": USER_AGENT},
        )
        if resp.status_code != 200:
            logger.warning("TikTok-Suche: HTTP %s — %s", resp.status_code,
                           resp.text[:200])
            return []

        ergebnis = []
        for video in ((resp.json() or {}).get("data") or {}).get("videos", []):
            text = (video.get("video_description") or "").strip()
            if not text:
                continue
            autor = video.get("username") or "unbekannt"
            ergebnis.append({
                "source": "tiktok",
                "post_id": f"tt:{video.get('id')}"[:300],
                "author": f"@{autor}"[:200],
                "content": text[:2000],
                "url": (f"https://www.tiktok.com/@{autor}"
                        f"/video/{video.get('id')}")[:1000],
                "posted_at": _zeit(video.get("create_time")),
            })
        return ergebnis
    except Exception as e:
        logger.debug("TikTok nicht erreichbar: %s", e)
        return []


# ---------------------------------------------------------------------------
# Verzeichnis
# ---------------------------------------------------------------------------

PLATTFORMEN = {
    "telegram": {
        "label": "Telegram",
        "zugang": "Offene Kanalvorschau, keine Anmeldung. Keine Suche — "
                  "Kanaele muessen benannt werden (FWS_TELEGRAM_KANAELE).",
        "kosten": None,
        "fehlend": _telegram_fehlend,
        "abrufen": _telegram_abrufen,
    },
    "x": {
        "label": "X (Twitter)",
        "zugang": "API v2, Beitragssuche der letzten 7 Tage. Freier Zugang "
                  "entfallen; Abrechnung je gelesenem Beitrag.",
        "kosten": "rund 0,005 USD je gelesenem Beitrag (Stand 09/2026)",
        "fehlend": _x_fehlend,
        "abrufen": _x_abrufen,
    },
    "facebook": {
        "label": "Facebook",
        "zugang": "Graph API, Beitraege benannter Seiten. Fremde Seiten "
                  "brauchen die von Meta einzeln freigegebene Berechtigung "
                  "Page Public Content Access; eigene Seiten sofort.",
        "kosten": None,
        "fehlend": _facebook_fehlend,
        "abrufen": _facebook_abrufen,
    },
    "instagram": {
        "label": "Instagram",
        "zugang": "Graph API, Hashtag-Suche. Geschaeftskonto mit verbundener "
                  "Facebook-Seite und gepruefte App noetig. Hoechstens 30 "
                  "verschiedene Hashtags je Woche.",
        "kosten": None,
        "fehlend": _instagram_fehlend,
        "abrufen": _instagram_abrufen,
    },
    "tiktok": {
        "label": "TikTok",
        "zugang": "Research API. Nur fuer Forschung und gemeinnuetzige "
                  "Organisationen mit oeffentlichem Zweck, Antrag wird "
                  "einzeln geprueft.",
        "kosten": None,
        "fehlend": _tiktok_fehlend,
        "abrufen": _tiktok_abrufen,
    },
}


# Mastodon und Bluesky werden im Sammler selbst abgerufen (historisch
# gewachsen, gut geprueft, kein Grund sie zu verschieben). Fuer die
# Gesamtuebersicht muessen sie aber mitgezaehlt werden — sonst sieht es aus,
# als hoerte das System auf Mastodon gar nicht.
SAMMLER_PLATTFORMEN = {
    "mastodon": {
        "label": "Mastodon",
        "zugang": "Oeffentliche Hashtag-Zeitleisten, keine Anmeldung.",
        "kosten": None,
        "fehlend": lambda: [],
    },
    "bluesky": {
        "label": "Bluesky",
        "zugang": "Beitragssuche ueber das AT-Protokoll, verlangt eine "
                  "Anmeldung. App-Passwort verwenden, nie das Kontopasswort.",
        "kosten": None,
        "fehlend": lambda: (
            [] if settings.bluesky_handle and settings.bluesky_app_password
            else ["FWS_BLUESKY_HANDLE", "FWS_BLUESKY_APP_PASSWORD"]),
    },
}


def plattform_status() -> list:
    """Welches Netz hoert gerade mit — und woran fehlt es sonst?

    Damit im Betrieb sichtbar ist, ob eine stille Plattform deshalb still ist,
    weil nichts passiert, oder weil ihr ein Schluessel fehlt. Ein Warnsystem
    darf diesen Unterschied nicht verwischen.
    """
    stand = []
    for key, p in {**SAMMLER_PLATTFORMEN, **PLATTFORMEN}.items():
        fehlt = p["fehlend"]()
        stand.append({
            "key": key,
            "label": p["label"],
            "aktiv": not fehlt,
            "fehlende_zugangsdaten": fehlt,
            "zugang": p["zugang"],
            "kosten": p["kosten"],
        })
    return stand


async def abrufen_alle(client) -> list:
    """Alle Plattformen abfragen, die Zugangsdaten haben."""
    beitraege = []
    for key, p in PLATTFORMEN.items():
        if p["fehlend"]():
            continue
        try:
            gefunden = await p["abrufen"](client)
        except Exception as e:
            logger.warning("Plattform %s fehlgeschlagen: %s", key, e)
            continue
        logger.debug("Plattform %s: %d Beitraege", key, len(gefunden))
        beitraege.extend(gefunden)
    return beitraege
