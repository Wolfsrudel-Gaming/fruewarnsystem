"""Quellengesundheit festhalten und auswerten.

Die Bewertungsregeln stehen in services/knowledge/quellen.py und arbeiten
ohne Datenbank. Hier liegt nur das Gedaechtnis: Wann hat eine Quelle zuletzt
WIRKLICH etwas geliefert — nicht, wann sie zuletzt geantwortet hat.
"""

import logging
from datetime import datetime

from sqlalchemy import select

from app.models.database import async_session
from app.models.schemas import SourceHealth
from app.services.knowledge.quellen import (
    STATUS_UNBEKANNT, bewerte_abruf, bewerte_quelle, gesamtbild, ist_erfolg,
)

logger = logging.getLogger(__name__)


async def melde_abruf(name, collector=None, bereich=None, url=None,
                      status_code=None, eintraege=0, fehler=None):
    """Einen Abruf festhalten.

    Wird von den Sammlern nach JEDEM Abruf aufgerufen — auch und gerade bei
    Misserfolg. Ein Abruf, der nicht gemeldet wird, ist ein Ausfall, den
    niemand sieht.
    """
    status = bewerte_abruf(status_code, eintraege, fehler)
    jetzt = datetime.utcnow()
    try:
        async with async_session() as session:
            eintrag = (await session.execute(
                select(SourceHealth).where(SourceHealth.name == name)
            )).scalar_one_or_none()
            if eintrag is None:
                eintrag = SourceHealth(name=name)
                session.add(eintrag)

            eintrag.collector = collector or eintrag.collector
            eintrag.bereich = bereich or eintrag.bereich
            eintrag.url = url or eintrag.url
            eintrag.last_status = status
            eintrag.last_http_code = status_code
            eintrag.last_entry_count = eintrage_zahl(eintraege)
            eintrag.last_error = (str(fehler)[:500] if fehler else None)
            eintrag.last_checked_at = jetzt

            if ist_erfolg(status):
                eintrag.last_success_at = jetzt
                eintrag.consecutive_failures = 0
            else:
                eintrag.consecutive_failures = (
                    eintrag.consecutive_failures or 0) + 1
                # Laut werden, nicht nur mitschreiben. Eine stumme Quelle
                # sieht im Ergebnis aus wie Ruhe — deshalb hier eine Warnung.
                logger.warning(
                    "Quelle '%s' liefert nicht (%s, HTTP %s, %d Fehlversuche "
                    "in Folge)", name, status, status_code,
                    eintrag.consecutive_failures)
            await session.commit()
    except Exception as e:
        # Die Gesundheitsmeldung darf niemals den Sammellauf abbrechen.
        logger.debug("Quellenmeldung fuer '%s' fehlgeschlagen: %s", name, e)
    return status


def eintrage_zahl(eintraege) -> int:
    try:
        return max(0, int(eintraege))
    except (TypeError, ValueError):
        return 0


async def quellenlage(jetzt=None) -> dict:
    """Der aktuelle Stand aller Quellen, fertig bewertet."""
    jetzt = jetzt or datetime.utcnow()
    async with async_session() as session:
        eintraege = (await session.execute(
            select(SourceHealth).order_by(SourceHealth.name)
        )).scalars().all()

    bewertet = []
    for e in eintraege:
        b = bewerte_quelle(
            e.last_status or STATUS_UNBEKANNT,
            fehlversuche_in_folge=e.consecutive_failures or 0,
            letzter_erfolg=e.last_success_at,
            jetzt=jetzt,
            bereich=e.bereich,
        )
        b.update({
            "name": e.name,
            "collector": e.collector,
            "bereich": e.bereich,
            "url": e.url,
            "http_code": e.last_http_code,
            "eintraege": e.last_entry_count,
            "fehler": e.last_error,
            "zuletzt_geprueft": (e.last_checked_at.isoformat()
                                 if e.last_checked_at else None),
            "zuletzt_geliefert": (e.last_success_at.isoformat()
                                  if e.last_success_at else None),
        })
        bewertet.append(b)

    bild = gesamtbild(bewertet, jetzt=jetzt)
    # Kaputtes zuerst — wer hier hinschaut, sucht Probleme, nicht Bestaetigung.
    rang = {"ausgefallen": 0, "wackelt": 1, "ok": 2}
    bewertet.sort(key=lambda q: (rang.get(q["stufe"], 3), -q["gewicht"],
                                 q["name"]))
    return {"gesamt": bild, "quellen": bewertet}
