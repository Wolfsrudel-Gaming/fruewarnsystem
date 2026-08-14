from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import get_db
from app.models.schemas import NewsItem, Alert, RiskScore
from app.services.analysis.llm_analyzer import analyzer
from app.api.routes.auth import get_current_user

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class AnalyzeRequest(BaseModel):
    title: str
    summary: str = ""
    source: str = "manual"


@router.get("/status")
async def analysis_status():
    available = await analyzer.check_availability()
    return {
        "llm_available": available,
        "model": analyzer._available and settings.ollama_model or None,
        "ollama_url": settings.ollama_url,
    }


@router.post("/article")
async def analyze_single_article(req: AnalyzeRequest, user=Depends(get_current_user)):
    result = await analyzer.analyze_article(
        title=req.title,
        summary=req.summary,
        source=req.source,
    )
    if result is None:
        return {"error": "LLM nicht verfügbar oder Analyse fehlgeschlagen", "fallback": _keyword_fallback(req.title, req.summary)}
    return {"analysis": result}


@router.post("/reanalyze")
async def reanalyze_recent_news(
    hours: int = Query(24, ge=1, le=168),
    min_keyword_score: float = Query(0.1, ge=0, le=1),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    stmt = (
        select(NewsItem)
        .where(and_(
            NewsItem.created_at > cutoff,
            NewsItem.relevance_score >= min_keyword_score,
            NewsItem.ai_analysis.is_(None),
        ))
        .order_by(desc(NewsItem.relevance_score))
        .limit(50)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()

    analyzed = 0
    for item in items:
        analysis = await analyzer.analyze_article(
            title=item.title,
            summary=item.summary or "",
            source=item.source or "",
            published=item.published_at.isoformat() if item.published_at else None,
        )
        if analysis:
            item.ai_analysis = analysis
            llm_score = analysis.get("relevance_score", 0)
            item.relevance_score = (item.relevance_score * 0.3) + (llm_score * 0.7)
            item.is_relevant = item.relevance_score > 0.3
            if analysis.get("category") and analysis["category"] != "sonstiges":
                item.category = analysis["category"]
            analyzed += 1

    await db.commit()
    return {"reanalyzed": analyzed, "total_candidates": len(items)}


@router.get("/report")
async def generate_situation_report(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(hours=24)

    risk_stmt = select(RiskScore).order_by(desc(RiskScore.calculated_at)).limit(10)
    risk_result = await db.execute(risk_stmt)
    risk_scores = {}
    for r in risk_result.scalars().all():
        cat = r.category.value
        if cat not in risk_scores:
            risk_scores[cat] = {"score": r.score, "detail": r.components.get("detail", "") if r.components else ""}

    alert_stmt = select(Alert).where(Alert.is_active == True).order_by(desc(Alert.score))
    alert_result = await db.execute(alert_stmt)
    active_alerts = [
        {"category": a.category.value, "title": a.title, "score": a.score}
        for a in alert_result.scalars().all()
    ]

    news_stmt = (
        select(NewsItem)
        .where(and_(NewsItem.is_relevant == True, NewsItem.created_at > cutoff))
        .order_by(desc(NewsItem.relevance_score))
        .limit(15)
    )
    news_result = await db.execute(news_stmt)
    relevant_news = [
        {
            "title": n.title,
            "source": n.source,
            "category": n.category,
            "relevance_score": n.relevance_score,
            "ai_analysis": n.ai_analysis,
        }
        for n in news_result.scalars().all()
    ]

    context = {
        "risk_scores": risk_scores,
        "active_alerts": active_alerts,
        "relevant_news": relevant_news,
    }

    report = await analyzer.generate_situation_report(context)
    if report is None:
        report = _generate_fallback_report(context)

    return {
        "report": report,
        "generated_at": datetime.utcnow().isoformat(),
        "llm_generated": report is not None and await analyzer.check_availability(),
        "context_summary": {
            "risk_categories": len(risk_scores),
            "active_alerts": len(active_alerts),
            "relevant_news": len(relevant_news),
        },
    }


@router.get("/news/analyzed")
async def get_analyzed_news(
    hours: int = Query(24, ge=1, le=720),
    escalation: str = Query(None, description="Filter: none, low, medium, high, critical"),
    category: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    stmt = (
        select(NewsItem)
        .where(and_(
            NewsItem.created_at > cutoff,
            NewsItem.ai_analysis.isnot(None),
        ))
        .order_by(desc(NewsItem.relevance_score))
        .limit(limit)
    )

    result = await db.execute(stmt)
    items = result.scalars().all()

    filtered = []
    for n in items:
        ai = n.ai_analysis or {}
        if escalation and ai.get("escalation_potential") != escalation:
            continue
        if category and ai.get("category") != category:
            continue

        filtered.append({
            "id": n.id,
            "title": n.title,
            "summary": n.summary[:300] if n.summary else None,
            "url": n.url,
            "source": n.source,
            "published_at": n.published_at.isoformat() if n.published_at else None,
            "keyword_category": n.category,
            "combined_score": n.relevance_score,
            "analysis": {
                "relevance_score": ai.get("relevance_score"),
                "category": ai.get("category"),
                "escalation_potential": ai.get("escalation_potential"),
                "drk_relevance": ai.get("drk_relevance"),
                "expected_actions": ai.get("expected_actions", []),
                "affected_area": ai.get("affected_area"),
                "time_sensitivity": ai.get("time_sensitivity"),
                "confidence": ai.get("confidence"),
            },
        })

    return {"items": filtered, "total": len(filtered)}


@router.get("/stats")
async def analysis_stats(
    hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    all_stmt = select(NewsItem).where(NewsItem.created_at > cutoff)
    all_result = await db.execute(all_stmt)
    all_items = all_result.scalars().all()

    total = len(all_items)
    analyzed = sum(1 for i in all_items if i.ai_analysis is not None)
    relevant = sum(1 for i in all_items if i.is_relevant)

    category_counts = {}
    escalation_counts = {"none": 0, "low": 0, "medium": 0, "high": 0, "critical": 0}
    high_confidence = []

    for item in all_items:
        if item.ai_analysis:
            cat = item.ai_analysis.get("category", "sonstiges")
            category_counts[cat] = category_counts.get(cat, 0) + 1

            esc = item.ai_analysis.get("escalation_potential", "none")
            if esc in escalation_counts:
                escalation_counts[esc] += 1

            if (item.ai_analysis.get("escalation_potential") in ("high", "critical")
                    and item.ai_analysis.get("confidence", 0) >= 0.7):
                high_confidence.append({
                    "title": item.title,
                    "source": item.source,
                    "escalation": item.ai_analysis["escalation_potential"],
                    "confidence": item.ai_analysis["confidence"],
                    "drk_relevance": item.ai_analysis.get("drk_relevance", ""),
                })

    return {
        "period_hours": hours,
        "total_articles": total,
        "analyzed": analyzed,
        "relevant": relevant,
        "analysis_rate": f"{analyzed/total*100:.1f}%" if total > 0 else "0%",
        "by_category": category_counts,
        "by_escalation": escalation_counts,
        "high_priority": high_confidence,
    }


def _keyword_fallback(title: str, summary: str) -> dict:
    from app.collectors.news.news_collector import _calculate_relevance, _detect_category
    score = _calculate_relevance(title, summary)
    category = _detect_category(title, summary)
    return {
        "relevance_score": score,
        "is_relevant": score > 0.3,
        "category": category,
        "escalation_potential": "high" if score > 0.7 else "medium" if score > 0.4 else "low" if score > 0.2 else "none",
        "method": "keyword_fallback",
    }


def _generate_fallback_report(context: dict) -> str:
    lines = [
        f"# Lagebericht DRK Troisdorf",
        f"Erstellt: {datetime.utcnow().strftime('%d.%m.%Y %H:%M')} UTC",
        f"(Automatisch generiert - LLM nicht verfügbar)",
        "",
        "## Risikobewertung",
    ]

    scores = context.get("risk_scores", {})
    for cat, data in sorted(scores.items(), key=lambda x: x[1].get("score", 0), reverse=True):
        score = data.get("score", 0)
        bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
        lines.append(f"- {cat}: {bar} {score:.0f}/100 - {data.get('detail', '')}")

    # Die Einsatzerwartung ist der Teil, der die Zahlen erst nutzbar macht —
    # sie gehört auch dann in den Bericht, wenn kein LLM läuft.
    deployment = context.get("deployment") or {}
    if deployment.get("label"):
        lines.append("")
        lines.append("## Bedeutung für die Bereitschaft Troisdorf")
        lines.append(f"**{deployment['label']}** — {deployment.get('description', '')}")
        for reason in deployment.get("reasons", []):
            lines.append(f"- {reason}")
        if deployment.get("components"):
            lines.append(
                "- Voraussichtlich gebraucht: "
                + ", ".join(deployment["components"])
            )

    alerts = context.get("active_alerts", [])
    if alerts:
        lines.append("")
        lines.append("## Aktive Alarme")
        for a in alerts:
            lines.append(f"- [{a['category']}] {a['title']} (Score: {a['score']:.0f})")
    else:
        lines.append("\nKeine aktiven Alarme.")

    knowledge = context.get("knowledge") or []
    if knowledge:
        lines.append("")
        lines.append("## Einsatzwissen zur Lage")
        for k in knowledge[:5]:
            lines.append(f"- **{k.get('title', '')}** ({k.get('source') or 'intern'})")

    news = context.get("relevant_news", [])
    if news:
        lines.append("")
        lines.append("## Relevante Nachrichten")
        for n in news[:10]:
            lines.append(f"- [{n.get('source', '')}] {n['title']}")
            ai = n.get("ai_analysis") or {}
            if ai.get("drk_relevance"):
                lines.append(f"  → {ai['drk_relevance']}")
            if ai.get("expected_actions"):
                lines.append(f"  Maßnahmen: {', '.join(ai['expected_actions'][:3])}")

    return "\n".join(lines)
