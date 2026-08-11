import json
import logging
from datetime import datetime
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Du bist ein Lageanalyst für das Deutsche Rote Kreuz (DRK) Troisdorf im Rhein-Sieg-Kreis, NRW.

Deine Aufgabe: Analysiere Nachrichtenmeldungen und bewerte ob sie auf einen möglichen DRK-Einsatz hindeuten.

Relevantes Einsatzgebiet: Troisdorf, Siegburg, Sankt Augustin, Niederkassel, Lohmar, Hennef,
gesamter Rhein-Sieg-Kreis, sowie Köln und Bonn bei Großlagen.

Relevante Gewässer: Rhein, Sieg, Agger, Pleisbach, Swistbach.
Besondere Gebiete: Wahner Heide (Waldbrandgefahr), ICE-Strecke Köln-Frankfurt, A3/A59/A565.

DRK-typische Einsatzszenarien:
- Hochwasser / Überschwemmung (Sandsäcke, Evakuierung, Betreuung)
- Unwetter / Sturm (Verletzte, Evakuierung, Notunterkünfte)
- Waldbrand (Verpflegung Einsatzkräfte, Evakuierung)
- Massenanfall von Verletzten (MANV) bei Unfällen oder Veranstaltungen
- Großveranstaltungen (Sanitätsdienst)
- Stromausfall / Infrastrukturausfall (Betreuung)
- Hitzewelle (Versorgung, Trinkwasser)
- Gefahrgutunfall
- Bombenentschärfung (Evakuierung, Betreuung)
- Bahnunglück / Schwere Verkehrsunfälle

Antworte AUSSCHLIESSLICH mit validem JSON in exakt diesem Format:
{
  "relevance_score": <float 0.0-1.0>,
  "is_relevant": <bool>,
  "category": "<hochwasser|unwetter|brand|verkehr|manv|sicherheit|gesundheit|infrastruktur|veranstaltung|sonstiges>",
  "escalation_potential": "<none|low|medium|high|critical>",
  "drk_relevance": "<string: warum ist das für das DRK relevant oder nicht>",
  "expected_actions": [<liste konkreter DRK-Maßnahmen falls relevant>],
  "affected_area": "<string: betroffenes Gebiet>",
  "time_sensitivity": "<none|hours|minutes|immediate>",
  "confidence": <float 0.0-1.0>
}"""

USER_PROMPT_TEMPLATE = """Analysiere diese Nachricht:

Quelle: {source}
Titel: {title}
Inhalt: {summary}
Veröffentlicht: {published}

Ist diese Meldung für das DRK Troisdorf einsatzrelevant? Antworte NUR mit JSON."""


class OllamaAnalyzer:
    def __init__(self):
        self._available = None

    async def check_availability(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{settings.ollama_url}/api/tags", timeout=5)
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    model_names = [m.get("name", "") for m in models]
                    self._available = any(settings.ollama_model in n for n in model_names)
                    if not self._available:
                        logger.warning(
                            f"Ollama model '{settings.ollama_model}' not found. "
                            f"Available: {model_names}. Run: docker exec fws-ollama ollama pull {settings.ollama_model}"
                        )
                    return self._available
        except Exception as e:
            logger.debug(f"Ollama not reachable: {e}")
            self._available = False
        return False

    async def analyze_article(self, title: str, summary: str, source: str,
                              published: str = None) -> Optional[dict]:
        if self._available is None:
            await self.check_availability()
        if not self._available:
            return None

        prompt = USER_PROMPT_TEMPLATE.format(
            source=source,
            title=title,
            summary=(summary or "")[:1500],
            published=published or "unbekannt",
        )

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{settings.ollama_url}/api/chat",
                    json={
                        "model": settings.ollama_model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                            "num_predict": 512,
                        },
                    },
                    timeout=120,
                )

                if resp.status_code != 200:
                    logger.warning(f"Ollama returned {resp.status_code}")
                    return None

                data = resp.json()
                content = data.get("message", {}).get("content", "")
                return _parse_llm_response(content)

        except httpx.TimeoutException:
            logger.warning("Ollama analysis timed out")
            return None
        except Exception as e:
            logger.error(f"Ollama analysis failed: {e}")
            return None

    async def generate_situation_report(self, context: dict) -> Optional[str]:
        if self._available is None:
            await self.check_availability()
        if not self._available:
            return None

        report_prompt = _build_report_prompt(context)

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{settings.ollama_url}/api/chat",
                    json={
                        "model": settings.ollama_model,
                        "messages": [
                            {"role": "system", "content": (
                                "Du bist ein Lageberichtserstatter für das DRK Troisdorf. "
                                "Erstelle einen prägnanten, strukturierten Lagebericht auf Deutsch. "
                                "Fokussiere auf einsatzrelevante Fakten. Keine Floskeln."
                            )},
                            {"role": "user", "content": report_prompt},
                        ],
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "num_predict": 1024,
                        },
                    },
                    timeout=180,
                )

                if resp.status_code != 200:
                    return None

                data = resp.json()
                return data.get("message", {}).get("content", "")

        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            return None

    async def analyze_batch(self, articles: list[dict]) -> list[dict]:
        results = []
        for article in articles:
            analysis = await self.analyze_article(
                title=article.get("title", ""),
                summary=article.get("summary", ""),
                source=article.get("source", ""),
                published=article.get("published_at", ""),
            )
            results.append({
                "content_hash": article.get("content_hash"),
                "analysis": analysis,
            })
        return results


def _parse_llm_response(content: str) -> Optional[dict]:
    content = content.strip()

    start = content.find("{")
    end = content.rfind("}") + 1
    if start == -1 or end == 0:
        logger.warning(f"No JSON found in LLM response: {content[:200]}")
        return None

    json_str = content[start:end]

    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError:
        json_str = json_str.replace("'", '"')
        json_str = json_str.replace(",\n}", "\n}")
        json_str = json_str.replace(",\r\n}", "\r\n}")
        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM JSON: {e} - Content: {json_str[:200]}")
            return None

    required_fields = ["relevance_score", "is_relevant", "category"]
    for field in required_fields:
        if field not in parsed:
            logger.warning(f"Missing required field '{field}' in LLM response")
            return None

    parsed["relevance_score"] = max(0.0, min(1.0, float(parsed.get("relevance_score", 0))))
    parsed["confidence"] = max(0.0, min(1.0, float(parsed.get("confidence", 0.5))))
    parsed["is_relevant"] = bool(parsed.get("is_relevant", False))

    valid_categories = {
        "hochwasser", "unwetter", "brand", "verkehr", "manv",
        "sicherheit", "gesundheit", "infrastruktur", "veranstaltung", "sonstiges",
    }
    if parsed.get("category") not in valid_categories:
        parsed["category"] = "sonstiges"

    valid_escalation = {"none", "low", "medium", "high", "critical"}
    if parsed.get("escalation_potential") not in valid_escalation:
        parsed["escalation_potential"] = "none"

    valid_time = {"none", "hours", "minutes", "immediate"}
    if parsed.get("time_sensitivity") not in valid_time:
        parsed["time_sensitivity"] = "none"

    if not isinstance(parsed.get("expected_actions"), list):
        parsed["expected_actions"] = []

    parsed["analyzed_at"] = datetime.utcnow().isoformat()

    return parsed


def _build_report_prompt(context: dict) -> str:
    sections = [
        f"Erstelle einen Lagebericht für das DRK Troisdorf.",
        f"Datum: {datetime.utcnow().strftime('%d.%m.%Y %H:%M')} UTC",
        "",
    ]

    scores = context.get("risk_scores", {})
    if scores:
        sections.append("## Aktuelle Risikobewertung:")
        for cat, data in scores.items():
            if isinstance(data, dict) and cat != "overall":
                sections.append(f"- {cat}: Score {data.get('score', 0):.0f}/100 ({data.get('detail', '')})")
        overall = scores.get("overall", {})
        if isinstance(overall, dict):
            sections.append(f"\nGesamt-Score: {overall.get('score', 0):.0f}/100")

    alerts = context.get("active_alerts", [])
    if alerts:
        sections.append("\n## Aktive Alarme:")
        for a in alerts[:10]:
            sections.append(f"- [{a.get('category', '')}] {a.get('title', '')} (Score: {a.get('score', 0):.0f})")

    news = context.get("relevant_news", [])
    if news:
        sections.append("\n## Relevante Nachrichten:")
        for n in news[:10]:
            sections.append(f"- [{n.get('source', '')}] {n.get('title', '')}")
            if n.get("ai_analysis", {}).get("drk_relevance"):
                sections.append(f"  DRK-Relevanz: {n['ai_analysis']['drk_relevance']}")

    sections.append("\nErstelle einen strukturierten Lagebericht mit:")
    sections.append("1. Zusammenfassung der aktuellen Lage")
    sections.append("2. Identifizierte Risiken und Gefahren")
    sections.append("3. Empfohlene Maßnahmen für das DRK")
    sections.append("4. Ausblick auf die nächsten 24 Stunden")

    return "\n".join(sections)


analyzer = OllamaAnalyzer()
