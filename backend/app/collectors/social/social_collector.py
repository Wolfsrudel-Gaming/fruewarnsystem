"""Soziale Netze mithoeren.

Der frueheste Kanal ueberhaupt. Wer auf einem Volksfest steht und etwas sieht,
schreibt darueber — oft Minuten bis Viertelstunden, bevor eine Leitstelle eine
Meldung herausgibt. Bei einer Grosslage entscheidet genau diese Vorlaufzeit.

Und der unzuverlaessigste Kanal. Ein einzelner Beitrag ist ein Geruecht, kein
Ereignis. Die Auswertung arbeitet deshalb NIE mit einem einzelnen Beitrag,
sondern mit dem Aufkommen: Mehrere unabhaengige Konten, die binnen kurzer Zeit
dasselbe zu einem Ort schreiben, sind das Signal. Die Burst-Erkennung steht in
services/knowledge/social_burst.py.

QUELLEN
Mastodon liefert oeffentliche Hashtag-Zeitleisten ohne Anmeldung — geprueft
gegen mastodon.social, nrw.social und troet.cafe. Das ist die verlaessliche
Grundlage.

Bluesky bietet eine oeffentliche API, verlangt fuer die Beitragssuche aber
inzwischen eine Anmeldung. Der Abruf ist vorbereitet und schaltet sich selbst
zu, sobald Zugangsdaten hinterlegt sind — ohne sie bleibt er still.

Twitter/X und Instagram haben keine brauchbare offene Schnittstelle mehr und
sind bewusst nicht enthalten.
"""

import hashlib
import html
import logging
import re
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.models.database import async_session
from app.models.schemas import SocialPost

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
USER_AGENT = "DRK-Fruehwarnsystem/1.0 (Bevoelkerungsschutz Troisdorf)"

# Mehrere Instanzen, weil jede nur sieht, was ihre eigenen Nutzer und deren
# Verbindungen verbreiten. Regionale Instanzen liefern den lokalen Bezug.
MASTODON_INSTANZEN = ("nrw.social", "mastodon.social", "troet.cafe")

# Hashtags mit Ortsbezug. Bewusst knapp: Jeder weitere Tag bringt mehr
# Alltagsgeplauder als Signal.
HASHTAGS = (
    "troisdorf", "siegburg", "rheinsieg", "bonn", "puetzchensmarkt",
    "koeln",
)

# Worte, die auf ein Ereignis hindeuten. Ein Beitrag ohne eines davon ist
# Alltag und wird gar nicht erst gespeichert.
EREIGNIS_BEGRIFFE = (
    "feuer", "brand", "brennt", "explosion", "knall", "rauch", "qualm",
    "unfall", "verletzt", "notarzt", "rettungswagen", "krankenwagen",
    "feuerwehr", "polizei", "hubschrauber", "sirene", "martinshorn",
    "evakuier", "räumung", "raeumung", "geräumt", "gesperrt", "sperrung",
    "panik", "massenpanik", "gedränge", "gedraenge", "zusammenbruch",
    "vermisst", "schüsse", "schuesse", "messer", "angriff", "amok",
    "hochwasser", "überflutet", "ueberflutet", "sturm", "unwetter",
    "stromausfall", "blackout", "großeinsatz", "grosseinsatz",
    "vollsperrung", "einsatzkräfte", "einsatzkraefte",
)

# Begriffe, die einen Treffer entwerten. Ohne sie wuerde jede Ankuendigung
# einer Uebung und jeder Rueckblick als laufendes Ereignis gelesen.
ENTWERTENDE_BEGRIFFE = (
    "übung", "uebung", "probealarm", "jahrestag", "gedenken", "vor jahren",
    "damals", "rückblick", "rueckblick", "film", "serie", "roman",
    "stellenangebot", "stellenanzeige", "sucht ein", "bewerbung",
)


def _text_von_html(roh: str) -> str:
    """Mastodon liefert HTML. Fuer die Auswertung zaehlt der reine Text."""
    ohne_tags = re.sub(r"<[^>]+>", " ", roh or "")
    return " ".join(html.unescape(ohne_tags).split())


def bewerte_beitrag(text: str) -> dict:
    """Ereignisbezug und Ortsbezug eines Beitrags.

    Reine Funktion, damit die Einstufung pruefbar bleibt.
    """
    from app.services.knowledge.geo import detect_scope

    klein = (text or "").lower()
    treffer = [w for w in EREIGNIS_BEGRIFFE if w in klein]
    entwertend = [w for w in ENTWERTENDE_BEGRIFFE if w in klein]
    ort = detect_scope(text)

    # Ein Beitrag zaehlt nur, wenn er ein Ereignis nennt UND einen Ort hat.
    # Beides zusammen — sonst waere jede Feuerwehr-Erwaehnung irgendwo auf der
    # Welt ein Treffer.
    ist_ereignis = bool(treffer) and not entwertend and ort["ort"] is not None

    relevanz = 0.0
    if ist_ereignis:
        relevanz = min(1.0, 0.35 + 0.15 * len(treffer))

    return {
        "keywords": treffer,
        "entwertet": entwertend,
        "place": ort["ort"],
        "scope": ort["scope"],
        "is_incident": ist_ereignis,
        "relevance": round(relevanz, 3),
    }


async def _mastodon_hashtag(client: httpx.AsyncClient, instanz: str,
                            tag: str) -> list:
    """Oeffentliche Hashtag-Zeitleiste einer Mastodon-Instanz."""
    ergebnis = []
    try:
        resp = await client.get(
            f"https://{instanz}/api/v1/timelines/tag/{tag}",
            params={"limit": 40},
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        if resp.status_code != 200:
            logger.debug("Mastodon %s/#%s: HTTP %s", instanz, tag,
                         resp.status_code)
            return ergebnis

        for post in resp.json() or []:
            text = _text_von_html(post.get("content", ""))
            if not text:
                continue
            konto = (post.get("account") or {}).get("acct") or "unbekannt"
            ergebnis.append({
                "source": "mastodon",
                # Beitraege erscheinen auf mehreren Instanzen. Die URL ist der
                # stabile Schluessel, die lokale ID waere je Instanz anders.
                "post_id": _stabile_id(post.get("url") or post.get("uri") or "",
                                       konto, text),
                "author": konto[:200],
                "content": text[:2000],
                "url": (post.get("url") or "")[:1000] or None,
                "posted_at": _zeit(post.get("created_at")),
            })
    except Exception as e:
        logger.debug("Mastodon %s/#%s nicht erreichbar: %s", instanz, tag, e)
    return ergebnis


def _stabile_id(url: str, autor: str, text: str) -> str:
    grundlage = url or f"{autor}|{text[:200]}"
    return hashlib.sha256(grundlage.encode()).hexdigest()[:60]


def _zeit(roh) -> object:
    if not roh:
        return None
    try:
        gelesen = datetime.fromisoformat(str(roh).replace("Z", "+00:00"))
        return gelesen.astimezone(timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


async def _bluesky(client: httpx.AsyncClient, begriff: str) -> list:
    """Beitragssuche bei Bluesky.

    Die oeffentliche API ist erreichbar, die Suche verlangt inzwischen aber
    eine Anmeldung. Ohne hinterlegte Zugangsdaten bleibt der Abruf still —
    das ist kein Fehler, sondern der Normalfall.
    """
    handle = getattr(settings, "bluesky_handle", None)
    passwort = getattr(settings, "bluesky_app_password", None)
    if not handle or not passwort:
        return []

    try:
        anmeldung = await client.post(
            "https://bsky.social/xrpc/com.atproto.server.createSession",
            json={"identifier": handle, "password": passwort},
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        if anmeldung.status_code != 200:
            logger.warning("Bluesky-Anmeldung fehlgeschlagen: HTTP %s",
                           anmeldung.status_code)
            return []
        token = (anmeldung.json() or {}).get("accessJwt")
        if not token:
            return []

        resp = await client.get(
            "https://bsky.social/xrpc/app.bsky.feed.searchPosts",
            params={"q": begriff, "limit": 40},
            timeout=REQUEST_TIMEOUT,
            headers={"Authorization": f"Bearer {token}",
                     "User-Agent": USER_AGENT},
        )
        if resp.status_code != 200:
            return []

        ergebnis = []
        for post in (resp.json() or {}).get("posts", []):
            text = ((post.get("record") or {}).get("text") or "").strip()
            if not text:
                continue
            autor = (post.get("author") or {}).get("handle") or "unbekannt"
            ergebnis.append({
                "source": "bluesky",
                "post_id": _stabile_id(post.get("uri") or "", autor, text),
                "author": autor[:200],
                "content": text[:2000],
                "url": None,
                "posted_at": _zeit((post.get("record") or {}).get("createdAt")),
            })
        return ergebnis
    except Exception as e:
        logger.debug("Bluesky nicht erreichbar: %s", e)
        return []


async def collect_social():
    """Beitraege einsammeln, einstufen und die relevanten speichern."""
    logger.info("Collecting social media posts...")
    roh = []

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for instanz in MASTODON_INSTANZEN:
            for tag in HASHTAGS:
                roh.extend(await _mastodon_hashtag(client, instanz, tag))
        for begriff in ("Troisdorf", "Siegburg", "Puetzchens Markt"):
            roh.extend(await _bluesky(client, begriff))

    # Gleiche Beitraege von mehreren Instanzen zusammenfassen
    nach_id = {}
    for eintrag in roh:
        nach_id.setdefault(eintrag["post_id"], eintrag)

    relevant = []
    for eintrag in nach_id.values():
        bewertung = bewerte_beitrag(eintrag["content"])
        # Nur Beitraege mit Ereignis- UND Ortsbezug werden ueberhaupt
        # gespeichert. Alles andere ist Alltagsgeplauder und wuerde die
        # Aufkommensmessung verwaessern.
        if not bewertung["is_incident"]:
            continue
        eintrag.update({
            "place": bewertung["place"],
            "scope": bewertung["scope"],
            "keywords": bewertung["keywords"],
            "relevance": bewertung["relevance"],
            "is_incident": True,
        })
        relevant.append(eintrag)

    neu = 0
    async with async_session() as session:
        from sqlalchemy import select
        for daten in relevant:
            vorhanden = (await session.execute(
                select(SocialPost).where(SocialPost.post_id == daten["post_id"])
            )).scalar_one_or_none()
            if vorhanden:
                continue
            session.add(SocialPost(**daten))
            neu += 1

        # Alte Beitraege entfernen. Fuer die Aufkommensmessung zaehlt nur die
        # juengste Vergangenheit; als Archiv taugen Geruechte ohnehin nicht.
        grenze = datetime.utcnow() - timedelta(days=3)
        for alt in (await session.execute(
            select(SocialPost).where(SocialPost.created_at < grenze)
        )).scalars().all():
            await session.delete(alt)

        await session.commit()

    logger.info(
        "Social: %d Beitraege gesichtet, %d mit Ereignisbezug, %d neu",
        len(nach_id), len(relevant), neu,
    )
    return relevant
