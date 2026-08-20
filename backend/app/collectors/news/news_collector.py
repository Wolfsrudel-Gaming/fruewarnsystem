import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx
import feedparser

from app.config import settings
from app.models.database import async_session
from app.models.schemas import NewsItem

logger = logging.getLogger(__name__)

# Ortsnahe Quellen zuerst — sie sind die wertvollsten. Nach Auskunft der
# Einheit ist die Presse der zuverlaessigste Vorbote eines Einsatzes: Was
# Verpflegung braucht, dauert lange und bindet viele Kraefte, und genau
# darueber wird berichtet.
RSS_FEEDS = [
    # --- Kerngebiet: Troisdorf und Siegburg ---
    {"name": "GA Troisdorf",
     "url": "https://ga.de/region/sieg-und-rhein/troisdorf/feed.rss"},
    {"name": "GA Siegburg",
     "url": "https://ga.de/region/sieg-und-rhein/siegburg/feed.rss"},
    {"name": "Feuerwehr Troisdorf (Verein)",
     "url": "https://www.feuerwehr-troisdorf.de/?format=feed&type=rss"},

    # --- Kreis: Blaulicht und Region ---
    # Kreispolizeibehoerde Rhein-Sieg-Kreis auf presseportal — die einzige
    # dedizierte Blaulicht-Quelle mit Kreisbezug, die verlaesslich liefert.
    {"name": "Polizei Rhein-Sieg-Kreis",
     "url": "https://www.presseportal.de/rss/dienststelle_65853.rss2"},
    {"name": "GA Region Sieg und Rhein",
     "url": "https://ga.de/region/sieg-und-rhein/feed.rss"},

    # --- Bundesweit, wird ueber den Ortsbezug gefiltert ---
    # Nur 15 Eintraege je Abruf, deshalb als Ergaenzung gedacht, nicht als
    # Hauptquelle. Faengt Feuerwehr-Meldungen ab, die sonst nirgends stehen.
    {"name": "Presseportal Feuerwehr", "bundesweit": True,
     "url": "https://www.presseportal.de/rss/feuerwehr.rss2"},
    {"name": "Presseportal Blaulicht", "bundesweit": True,
     "url": "https://www.presseportal.de/rss/blaulicht.rss2"},

    # --- Bestand ---
    {"name": "General-Anzeiger Bonn", "url": "https://ga.de/feed.rss"},
    {"name": "Kölner Stadt-Anzeiger", "url": "https://www.ksta.de/feed/index.rss"},
    {"name": "Kölnische Rundschau", "url": "https://www.rundschau-online.de/feed/index.rss"},
    {"name": "WDR Nachrichten", "url": "https://www1.wdr.de/nachrichten/rheinland/index~_format-mp-100.feed"},
    {"name": "Rhein-Sieg-Anzeiger", "url": "https://www.ksta.de/region/rhein-sieg-bonn/feed.rss"},
    {"name": "Polizei Bonn", "url": "https://bonn.polizei.nrw/presse/feed"},
    {"name": "Feuerwehr Troisdorf", "url": "https://www.troisdorf.de/web/de/rathaus/news/rss.htm"},
    {"name": "Feuerwehr Bonn", "url": "https://www.bonn.de/pressemitteilungen.feed"},
    {"name": "WDR Lokalzeit Bonn", "url": "https://www1.wdr.de/nachrichten/rheinland/lokalzeit-bonn-100~_format-mp-100.feed"},
]

KEYWORDS_HIGH = [
    "hochwasser", "überschwemmung", "evakuierung", "großeinsatz", "katastrophe",
    "explosion", "brand", "feuer", "waldbrand", "unwetter", "tornado",
    "chemieunfall", "gefahrgut", "massenanfall", "manv", "amoklauf",
    "bombenentschärfung", "bombendrohung", "terrorismus", "erdbeben",
    "dammbruch", "deichbruch", "flutwelle", "stromausfall",
    "dürre", "trinkwassernotstand", "wassernotstand",
]

KEYWORDS_MEDIUM = [
    "unfall", "sperrung", "stromausfall", "starkregen", "gewitter",
    "sturmwarnung", "hitzewelle", "drk", "rotes kreuz", "rettungsdienst",
    "feuerwehr", "polizei", "sirene", "warnung", "gefahr",
    "rhein", "sieg", "agger", "troisdorf", "siegburg", "wahner heide",
    "notarzt", "rettungshubschrauber", "schwerverletzt", "tödlich",
    "vermisst", "bergrettung", "wasserrettung", "großübung",
    "niedrigwasser", "trockenheit", "wassermangel", "pegel niedrig",
    "hitzetote", "trinkwasser", "bewässerungsverbot", "fischsterben",
]

KEYWORDS_LOW = [
    "verkehr", "stau", "baustelle", "veranstaltung", "demo",
    "demonstration", "festival", "konzert", "sport", "marathon",
    "karnevalszug", "schützenfest", "stadtfest",
    "pegelstand", "wasserstand",
]


async def collect_news():
    logger.info("Collecting news from RSS feeds...")
    results = []

    async with httpx.AsyncClient() as client:
        for feed_info in RSS_FEEDS:
            try:
                resp = await client.get(feed_info["url"], timeout=20, follow_redirects=True)
                if resp.status_code != 200:
                    continue

                feed = feedparser.parse(resp.text)
                for entry in feed.entries[:20]:
                    title = entry.get("title", "")
                    summary = entry.get("summary", entry.get("description", ""))
                    link = entry.get("link", "")

                    content_hash = hashlib.sha256(
                        f"{title}{link}".encode()
                    ).hexdigest()

                    relevance = _calculate_relevance(
                        title, summary,
                        bundesweit=feed_info.get("bundesweit", False),
                    )

                    published = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        published = datetime(*entry.published_parsed[:6])

                    results.append({
                        "title": title[:500],
                        "summary": _clean_html(summary)[:2000] if summary else None,
                        "url": link[:1000] if link else None,
                        "source": feed_info["name"],
                        "category": _detect_category(title, summary),
                        "relevance_score": relevance,
                        "is_relevant": relevance > 0.3,
                        "published_at": published,
                        "content_hash": content_hash,
                    })
            except Exception as e:
                logger.warning(f"Error fetching feed {feed_info['name']}: {e}")

    new_items = []
    async with async_session() as session:
        from sqlalchemy import select
        for data in results:
            stmt = select(NewsItem).where(NewsItem.content_hash == data["content_hash"])
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                entry = NewsItem(**data)
                session.add(entry)
                new_items.append(data)
        await session.commit()

    if new_items:
        await _run_llm_analysis(new_items)

    logger.info(f"Collected {len(results)} news items, {len(new_items)} new")
    return results


def _apply_analysis(db_item: NewsItem, analysis: dict, keyword_score: float):
    db_item.ai_analysis = analysis
    llm_score = analysis.get("relevance_score", 0)
    db_item.relevance_score = (keyword_score * 0.3) + (llm_score * 0.7)
    db_item.is_relevant = db_item.relevance_score > 0.3
    if analysis.get("category") and analysis["category"] != "sonstiges":
        db_item.category = analysis["category"]

    if analysis.get("escalation_potential") in ("high", "critical"):
        logger.warning(
            f"HIGH ESCALATION NEWS: [{db_item.source}] {db_item.title} "
            f"- {analysis.get('drk_relevance', '')}"
        )


async def _run_llm_analysis(new_items: list[dict]):
    from app.services.analysis.llm_analyzer import analyzer

    candidates = [item for item in new_items if item["relevance_score"] >= 0.1]

    if not candidates:
        logger.info("No candidates for LLM analysis")
        return

    logger.info(f"Running LLM analysis on {len(candidates)} articles...")

    for item in candidates:
        try:
            analysis = await analyzer.analyze_article(
                title=item["title"],
                summary=item.get("summary", ""),
                source=item["source"],
                published=item["published_at"].isoformat() if item.get("published_at") else None,
            )

            if analysis is None:
                continue

            async with async_session() as session:
                from sqlalchemy import select
                stmt = select(NewsItem).where(NewsItem.content_hash == item["content_hash"])
                db_item = (await session.execute(stmt)).scalar_one_or_none()
                if db_item:
                    _apply_analysis(db_item, analysis, keyword_score=item["relevance_score"])
                    await session.commit()

        except Exception as e:
            logger.error(f"LLM analysis failed for '{item['title'][:60]}': {e}")


async def analyze_news_backlog(batch_size: int = 4, max_age_days: int = 7):
    """Analysiert Bestandsmeldungen ohne ai_analysis nachträglich (CPU-schonend in kleinen Batches).

    Wird vom Scheduler periodisch aufgerufen. Meldungen, deren Analyse fehlschlägt,
    bekommen einen Fehlermarker, damit sie die Warteschlange nicht dauerhaft blockieren.
    """
    from sqlalchemy import select
    from app.services.analysis.llm_analyzer import analyzer

    if not await analyzer.check_availability():
        logger.debug("News backlog: Ollama nicht verfügbar, überspringe Lauf")
        return

    cutoff = datetime.utcnow() - timedelta(days=max_age_days)
    async with async_session() as session:
        stmt = (
            select(NewsItem)
            .where(NewsItem.ai_analysis.is_(None))
            .where(NewsItem.relevance_score >= 0.1)
            .where(NewsItem.created_at > cutoff)
            .order_by(NewsItem.relevance_score.desc(), NewsItem.created_at.desc())
            .limit(batch_size)
        )
        pending = (await session.execute(stmt)).scalars().all()

    if not pending:
        return

    logger.info(f"News backlog: analysiere {len(pending)} unanalysierte Meldungen...")

    for item in pending:
        try:
            analysis = await analyzer.analyze_article(
                title=item.title,
                summary=item.summary or "",
                source=item.source or "",
                published=item.published_at.isoformat() if item.published_at else None,
            )
        except Exception as e:
            logger.error(f"Backlog-Analyse fehlgeschlagen für '{item.title[:60]}': {e}")
            analysis = None

        async with async_session() as session:
            db_item = await session.get(NewsItem, item.id)
            if not db_item:
                continue
            if analysis is None:
                # Fehlermarker statt Endlos-Retry (Timeout oder unparsbare Antwort)
                db_item.ai_analysis = {
                    "error": "analysis_failed",
                    "failed_at": datetime.utcnow().isoformat(),
                }
            else:
                _apply_analysis(db_item, analysis, keyword_score=db_item.relevance_score or 0.0)
            await session.commit()


# Wie stark der Ortsbezug die Relevanz einer Meldung veraendert.
# Ohne diese Daempfung wuerden die bundesweiten Blaulicht-Quellen die
# Nachrichtenlage mit Ereignissen fluten, die Troisdorf nichts angehen —
# und die Kategorie wiegt seit der Profilkorrektur voll.
ORTSGEWICHT = {
    "troisdorf": 1.0,
    "nachbarschaft": 0.9,
    "rhein_sieg": 0.75,
    # Ohne erkennbaren Ort: mittlere Einstufung. Viele regionale Feeds nennen
    # den Ort nur im Fliesstext, den wir hier nicht immer vorliegen haben.
    "unbekannt": 0.6,
    "ausserhalb": 0.35,
}


def _calculate_relevance(title: str, summary: str,
                         bundesweit: bool = False) -> float:
    text = f"{title} {summary}".lower()
    score = 0.0

    for kw in KEYWORDS_HIGH:
        if kw in text:
            score += 0.4

    for kw in KEYWORDS_MEDIUM:
        if kw in text:
            score += 0.15

    for kw in KEYWORDS_LOW:
        if kw in text:
            score += 0.05

    score = min(1.0, score)

    from app.services.knowledge.geo import detect_scope
    scope = detect_scope(title, summary)["scope"]
    if scope == "unbekannt" and bundesweit:
        # Bundesweite Quellen berichten per Definition ueberall her. Fehlt der
        # Ortsbezug, ist die Meldung mit hoher Wahrscheinlichkeit nicht von
        # hier — anders als bei einem Regionalfeed, wo das Gegenteil gilt.
        scope = "ausserhalb"
    return round(score * ORTSGEWICHT.get(scope, 0.6), 4)


def _detect_category(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    categories = {
        "hochwasser": ["hochwasser", "überschwemmung", "pegel", "rhein", "sieg", "deich", "damm",
                       "niedrigwasser", "dürre", "trockenheit", "wassermangel", "fischsterben"],
        "brand": ["brand", "feuer", "waldbrand", "explosion", "rauch"],
        "unwetter": ["unwetter", "sturm", "gewitter", "starkregen", "tornado", "hagel", "orkan",
                     "hitzewelle", "hitzewarnung"],
        "verkehr": ["unfall", "sperrung", "stau", "verkehr", "autobahn", "bahnstrecke"],
        "sicherheit": ["polizei", "bomben", "terror", "amoklauf", "gefahrgut", "schuss"],
        "gesundheit": ["drk", "rettung", "manv", "krankenhaus", "notfall", "verletzt",
                       "hitzetote", "trinkwasser"],
        "infrastruktur": ["stromausfall", "wasserausfall", "gasaustritt", "infrastruktur",
                          "trinkwassernotstand", "wassernotstand"],
        "veranstaltung": ["festival", "konzert", "marathon", "karnevalszug", "schützenfest"],
    }
    for cat, keywords in categories.items():
        if any(kw in text for kw in keywords):
            return cat
    return "sonstiges"


def _clean_html(text: str) -> str:
    if not text:
        return ""
    from html import unescape
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
