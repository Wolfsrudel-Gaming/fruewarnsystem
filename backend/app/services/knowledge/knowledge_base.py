"""Zugriff auf die DRK-Wissensdatenbank.

Das Fruehwarnsystem misst Werte. Was ein Wert bedeutet — ob daraus ein Einsatz
wird, welche Einheit dann laeuft, welches Gefahrenobjekt in der Naehe liegt —
steht hier. Dieses Modul spielt den recherchierten Grundbestand ein, sucht
passende Eintraege zu einer Lage heraus und stellt sie fuer den Lagebericht
bereit.

Eigene, nicht-oeffentliche Eintraege (AAO, interne Einsatzplanung) stehen
gleichberechtigt neben den recherchierten. Sie werden nur beim Einspielen
nicht angefasst: Ein erneutes Seeding aktualisiert ausschliesslich Eintraege
mit ``seed_key``.
"""

import logging
import re
from typing import Optional

from sqlalchemy import select

from app.models.database import async_session
from app.models.schemas import KnowledgeEntry, KnowledgeKind, KnowledgeScope
from app.services.knowledge.seed_data import ALL_ENTRIES

logger = logging.getLogger(__name__)

# Wie stark ein Eintrag zaehlt, je nach raeumlicher Naehe. Ein Gefahrenobjekt
# in Troisdorf ist fuer die eigene Lage wichtiger als ein Landeskonzept.
SCOPE_WEIGHT = {
    KnowledgeScope.TROISDORF: 1.0,
    # Direkte Nachbarschaft — Siegburg, Sankt Augustin, Niederkassel, Lohmar,
    # Hennef und Grosslagen unmittelbar an der Kreisgrenze.
    KnowledgeScope.NACHBARSCHAFT: 0.9,
    KnowledgeScope.RHEIN_SIEG: 0.8,
    KnowledgeScope.NRW: 0.5,
    KnowledgeScope.BUND: 0.4,
}

# Wortlaenge, ab der ein Suchbegriff ueberhaupt gewertet wird — kuerzere
# Woerter ("A 3", "in", "am") treffen sonst fast jeden Eintrag.
MIN_TERM_LENGTH = 3


async def seed_knowledge_base() -> dict:
    """Recherchierten Grundbestand einspielen bzw. auffrischen.

    Idempotent: Eintraege werden ueber ``seed_key`` wiedergefunden und
    aktualisiert, nicht doppelt angelegt. Selbst eingepflegte Eintraege
    (ohne ``seed_key``) bleiben unberuehrt.
    """
    created = updated = 0
    async with async_session() as session:
        existing = {
            row.seed_key: row
            for row in (await session.execute(
                select(KnowledgeEntry).where(KnowledgeEntry.seed_key.isnot(None))
            )).scalars().all()
        }

        for data in ALL_ENTRIES:
            key = data["seed_key"]
            row = existing.get(key)
            values = {
                "kind": KnowledgeKind(data["kind"]),
                "scope": KnowledgeScope(data["scope"]),
                "title": data["title"],
                "body": data["body"],
                "categories": data["categories"],
                "tags": data["tags"],
                "trigger": data["trigger"],
                "facts": data["facts"],
                "source": data["source"],
                "source_url": data["source_url"],
                "source_date": data["source_date"],
                "is_official": data["is_official"],
            }
            if row is None:
                session.add(KnowledgeEntry(seed_key=key, **values))
                created += 1
            else:
                for field, value in values.items():
                    setattr(row, field, value)
                updated += 1

        await session.commit()

    logger.info("Wissensdatenbank: %d neu, %d aktualisiert", created, updated)
    return {"created": created, "updated": updated, "total": len(ALL_ENTRIES)}


def _tokens(text: str) -> set:
    """Wortstamm-nahe Zerlegung fuer die Textsuche.

    Bewusst simpel gehalten: keine Abhaengigkeit von Sprachmodellen, damit die
    Suche auch ohne laufendes LLM funktioniert.
    """
    return {
        t for t in re.split(r"[^a-z0-9äöüß]+", (text or "").lower())
        if len(t) >= MIN_TERM_LENGTH
    }


def score_entry(entry: KnowledgeEntry, scores: dict, query: str = "") -> float:
    """Wie gut passt dieser Eintrag zur aktuellen Lage?

    Drei Beitraege:

    * Kategoriebezug — der Eintrag nennt eine Kategorie, die gerade hoch ist.
      Das ist der wichtigste Teil und skaliert mit dem Score.
    * Ausloeserbedingung — ``trigger`` ist erfuellt.
    * Texttreffer — nur wenn eine Suchanfrage vorliegt.

    Alles gewichtet mit der raeumlichen Naehe.
    """
    relevance = 0.0
    cats = entry.categories or []

    for cat in cats:
        current = (scores.get(cat) or {}).get("score", 0)
        if current > 0:
            relevance += current / 100.0

    trigger = entry.trigger or {}
    if trigger:
        min_score = trigger.get("min_score")
        target = trigger.get("categories") or ([trigger["category"]]
                                               if trigger.get("category") else [])
        if min_score is not None and target:
            if any((scores.get(c) or {}).get("score", 0) >= min_score for c in target):
                relevance += 1.0
        any_min = trigger.get("any_category_min_score")
        if any_min is not None and any(
            (v or {}).get("score", 0) >= any_min for v in scores.values()
        ):
            relevance += 1.0

    if query:
        terms = _tokens(query)
        if terms:
            haystack = _tokens(
                f"{entry.title} {entry.body} {' '.join(entry.tags or [])}"
            )
            hits = len(terms & haystack)
            if hits:
                relevance += 2.0 * hits / len(terms)

    return relevance * SCOPE_WEIGHT.get(entry.scope, 0.5)


async def relevant_for_situation(
    scores: dict,
    limit: int = 8,
    query: str = "",
    kinds: Optional[list] = None,
) -> list:
    """Die zur Lage passenden Wissenseintraege, absteigend nach Relevanz."""
    async with async_session() as session:
        stmt = select(KnowledgeEntry)
        if kinds:
            stmt = stmt.where(KnowledgeEntry.kind.in_(
                [KnowledgeKind(k) if isinstance(k, str) else k for k in kinds]
            ))
        entries = (await session.execute(stmt)).scalars().all()

    ranked = [(score_entry(e, scores, query), e) for e in entries]
    ranked = [(r, e) for r, e in ranked if r > 0]
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in ranked[:limit]]


def serialize(entry: KnowledgeEntry, include_body: bool = True) -> dict:
    data = {
        "id": entry.id,
        "kind": entry.kind.value,
        "scope": entry.scope.value,
        "title": entry.title,
        "categories": entry.categories or [],
        "tags": entry.tags or [],
        "facts": entry.facts,
        "source": entry.source,
        "source_url": entry.source_url,
        "source_date": entry.source_date,
        "is_official": bool(entry.is_official),
        "is_seed": entry.seed_key is not None,
        "created_by": entry.created_by,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
    }
    if include_body:
        data["body"] = entry.body
    return data
