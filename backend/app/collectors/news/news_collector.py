import hashlib
import logging
from datetime import datetime
from typing import Optional

import httpx
import feedparser

from app.config import settings
from app.models.database import async_session
from app.models.schemas import NewsItem

logger = logging.getLogger(__name__)

RSS_FEEDS = [
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

                    relevance = _calculate_relevance(title, summary)

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
                    db_item.ai_analysis = analysis
                    llm_score = analysis.get("relevance_score", 0)
                    keyword_score = item["relevance_score"]
                    db_item.relevance_score = (keyword_score * 0.3) + (llm_score * 0.7)
                    db_item.is_relevant = db_item.relevance_score > 0.3
                    if analysis.get("category") and analysis["category"] != "sonstiges":
                        db_item.category = analysis["category"]
                    await session.commit()

                    if analysis.get("escalation_potential") in ("high", "critical"):
                        logger.warning(
                            f"HIGH ESCALATION NEWS: [{item['source']}] {item['title']} "
                            f"- {analysis.get('drk_relevance', '')}"
                        )

        except Exception as e:
            logger.error(f"LLM analysis failed for '{item['title'][:60]}': {e}")


def _calculate_relevance(title: str, summary: str) -> float:
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

    return min(1.0, score)


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
