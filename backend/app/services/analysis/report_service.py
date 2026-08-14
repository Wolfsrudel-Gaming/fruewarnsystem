"""Erzeugung und Zwischenspeicherung des KI-Lageberichts.

Das lokale LLM braucht für einen Bericht bis zu drei Minuten. Direkt hinter
einem HTTP-Request ist das nicht haltbar: Die App gibt nach 90 Sekunden auf,
Nginx meist schon nach 60. Der Bericht lief deshalb regelmäßig ins Timeout,
statt wenigstens den regelbasierten Fallback zu zeigen.

Deshalb: Der Bericht wird periodisch im Hintergrund erzeugt und abgelegt.
Der Endpunkt liefert immer sofort den letzten Stand samt Alter.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta

from sqlalchemy import and_, desc, select

from app.config import settings
from app.models.database import async_session
from app.models.schemas import Alert, NewsItem, RiskScore, SituationReportCache

logger = logging.getLogger(__name__)

# Ab diesem Alter gilt der gespeicherte Bericht als überholt
MAX_AGE = timedelta(minutes=30)

# Verhindert, dass mehrere Läufe gleichzeitig das LLM belegen
_generation_lock = asyncio.Lock()


async def _build_context() -> dict:
    """Sammelt die Datengrundlage für den Bericht."""
    cutoff = datetime.utcnow() - timedelta(hours=24)

    async with async_session() as session:
        rows = (await session.execute(
            select(RiskScore)
            .where(RiskScore.calculated_at > cutoff)
            .order_by(desc(RiskScore.calculated_at))
            .limit(100)
        )).scalars().all()

        risk_scores = {}
        for r in rows:
            cat = r.category.value
            if cat not in risk_scores:
                risk_scores[cat] = {
                    "score": r.score,
                    "detail": (r.components or {}).get("detail", ""),
                }

        alerts = (await session.execute(
            select(Alert).where(Alert.is_active == True).order_by(desc(Alert.score))
        )).scalars().all()

        news = (await session.execute(
            select(NewsItem)
            .where(and_(NewsItem.is_relevant == True, NewsItem.created_at > cutoff))
            .order_by(desc(NewsItem.relevance_score))
            .limit(15)
        )).scalars().all()

    # Einsatzwissen zur Lage dazuholen: Was bedeuten diese Werte fuer die
    # Bereitschaft? Ohne diesen Teil kann das LLM nur die Zahlen nacherzaehlen.
    from app.api.routes.dashboard import CATEGORY_LABELS
    from app.services.knowledge.assessment import assess_deployment
    from app.services.knowledge.knowledge_base import (
        relevant_for_situation, serialize,
    )

    deployment = assess_deployment(risk_scores, CATEGORY_LABELS)
    try:
        knowledge = [
            serialize(e) for e in await relevant_for_situation(risk_scores, limit=6)
        ]
    except Exception as e:  # Wissensbasis darf den Bericht nie blockieren
        logger.warning("Wissensabruf fehlgeschlagen: %s", e)
        knowledge = []

    return {
        "risk_scores": risk_scores,
        "deployment": deployment,
        "knowledge": knowledge,
        "active_alerts": [
            {"category": a.category.value, "title": a.title, "score": a.score}
            for a in alerts
        ],
        "relevant_news": [
            {
                "title": n.title,
                "source": n.source,
                "category": n.category,
                "relevance_score": n.relevance_score,
                "ai_analysis": n.ai_analysis,
            }
            for n in news
        ],
    }


async def generate_and_store() -> dict:
    """Erzeugt einen neuen Bericht und legt ihn ab.

    Fällt das LLM aus, wird der regelbasierte Bericht gespeichert — besser
    ein einfacher Lagebericht als gar keiner.
    """
    if _generation_lock.locked():
        logger.info("Berichtserzeugung laeuft bereits, ueberspringe")
        return {}

    async with _generation_lock:
        from app.api.routes.analysis import _generate_fallback_report
        from app.services.analysis.llm_analyzer import analyzer

        started = time.monotonic()
        context = await _build_context()

        report = None
        llm_generated = False
        try:
            if await analyzer.check_availability():
                report = await analyzer.generate_situation_report(context)
                llm_generated = report is not None
        except Exception as e:
            logger.error("LLM-Bericht fehlgeschlagen: %s", e)

        if not report:
            report = _generate_fallback_report(context)

        duration = round(time.monotonic() - started, 1)

        entry = SituationReportCache(
            report=report,
            llm_generated=llm_generated,
            model=settings.ollama_model if llm_generated else None,
            context_summary={
                "risk_categories": len(context["risk_scores"]),
                "active_alerts": len(context["active_alerts"]),
                "relevant_news": len(context["relevant_news"]),
            },
            generation_seconds=duration,
        )

        async with async_session() as session:
            session.add(entry)
            # Historie begrenzen — der Bericht ist ein Momentbild, kein Archiv
            old = (await session.execute(
                select(SituationReportCache)
                .order_by(desc(SituationReportCache.generated_at))
                .offset(50)
            )).scalars().all()
            for o in old:
                await session.delete(o)
            await session.commit()
            await session.refresh(entry)

        logger.info(
            "Lagebericht erzeugt in %.1fs (%s)",
            duration, "LLM" if llm_generated else "regelbasiert",
        )
        return _serialize(entry)


async def get_latest(max_age: timedelta = MAX_AGE) -> dict:
    """Letzten Bericht liefern; bei fehlendem Bericht sofort einen erzeugen.

    Ist der gespeicherte Bericht überholt, wird im Hintergrund ein neuer
    angestoßen — der Aufrufer bekommt trotzdem sofort eine Antwort.
    """
    async with async_session() as session:
        entry = (await session.execute(
            select(SituationReportCache)
            .order_by(desc(SituationReportCache.generated_at))
            .limit(1)
        )).scalar_one_or_none()

    if entry is None:
        # Noch nie erzeugt: der regelbasierte Bericht ist schnell genug,
        # um ihn direkt zu liefern.
        return await _generate_fallback_now()

    data = _serialize(entry)
    if data["age_minutes"] > max_age.total_seconds() / 60:
        data["refreshing"] = True
        asyncio.create_task(_safe_generate())
    return data


async def _generate_fallback_now() -> dict:
    """Regelbasierter Sofortbericht, wenn noch keiner vorliegt."""
    from app.api.routes.analysis import _generate_fallback_report

    context = await _build_context()
    entry = SituationReportCache(
        report=_generate_fallback_report(context),
        llm_generated=False,
        context_summary={
            "risk_categories": len(context["risk_scores"]),
            "active_alerts": len(context["active_alerts"]),
            "relevant_news": len(context["relevant_news"]),
        },
        generation_seconds=0.0,
    )
    async with async_session() as session:
        session.add(entry)
        await session.commit()
        await session.refresh(entry)

    data = _serialize(entry)
    data["refreshing"] = True
    asyncio.create_task(_safe_generate())
    return data


async def _safe_generate() -> None:
    """Hintergrundlauf — darf den Aufrufer nie mitreissen."""
    try:
        await generate_and_store()
    except Exception as e:
        logger.error("Hintergrund-Berichtserzeugung fehlgeschlagen: %s", e, exc_info=True)


def _serialize(entry: SituationReportCache) -> dict:
    generated = entry.generated_at or datetime.utcnow()
    age = (datetime.utcnow() - generated).total_seconds() / 60
    return {
        "report": entry.report,
        "generated_at": generated.isoformat(),
        "age_minutes": round(max(0.0, age), 1),
        "llm_generated": bool(entry.llm_generated),
        "model": entry.model,
        "generation_seconds": entry.generation_seconds,
        "context_summary": entry.context_summary or {},
        "refreshing": False,
    }
