import logging
from datetime import datetime
from typing import Optional

import httpx

from app.config import settings
from app.models.database import async_session
from app.models.schemas import OfficialWarning

logger = logging.getLogger(__name__)

# Die offizielle Warn-API des Bundes. Der frueher genutzte Proxy
# (nina.api.proxy.bund.dev) antwortet nicht mehr zuverlaessig.
NINA_BASE = "https://warnung.bund.de/api31"

# Der Dashboard-Endpunkt erwartet den **12-stelligen** ARS, nicht den
# 5-stelligen AGS. Mit "05382" antwortet er mit HTTP 400 — genau daran
# scheiterte die Abfrage bisher lautlos.
REGIONS = {
    "053820000000": "Rhein-Sieg-Kreis",
    "053140000000": "Bonn",
    "053150000000": "Koeln",
}

# mapData-Listen als Ergaenzung. Achtung: Diese Eintraege enthalten **kein**
# ``info``-Objekt — nur ``i18nTitle``, ``severity`` und ``id``. Wer hier nach
# ``info`` greift, bekommt ueberall leere Felder ("Unbekannt").
MAPDATA_URLS = {
    "katwarn": f"{NINA_BASE}/katwarn/mapData.json",
    "mowas": f"{NINA_BASE}/mowas/mapData.json",
    "biwapp": f"{NINA_BASE}/biwapp/mapData.json",
    "dwd": f"{NINA_BASE}/dwd/mapData.json",
}

REQUEST_TIMEOUT = 30


async def collect_official_warnings():
    logger.info("Collecting official warnings (NINA/MoWaS/KATWARN)...")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        # 1) Amtlich zugeordnete Warnungen je Gebietskoerperschaft. Das ist die
        #    massgebliche Quelle: der Bund sagt selbst, welche Warnung fuer den
        #    Rhein-Sieg-Kreis gilt — unabhaengig davon, wo das Ereignis liegt.
        #    Der Brandrauch aus Dueren etwa betrifft den Kreis, nennt ihn im
        #    Titel aber nicht als Ereignisort.
        by_id = {}
        for ars, region_name in REGIONS.items():
            for entry in await _fetch_region_warnings(client, ars, region_name):
                by_id.setdefault(entry["warning_id"], entry)

        # 2) Bundesweite Listen als Ergaenzung, gefiltert auf die Region
        for source, url in MAPDATA_URLS.items():
            for entry in await _fetch_mapdata(client, source, url):
                by_id.setdefault(entry["warning_id"], entry)

        # 3) Details nachladen, wo nur der Titel bekannt ist
        incomplete = [e for e in by_id.values() if not e.get("description")]
        for entry in incomplete[:40]:
            await _enrich_with_details(client, entry)

    unique_results = list(by_id.values())

    async with async_session() as session:
        from sqlalchemy import select
        for data in unique_results:
            stmt = select(OfficialWarning).where(
                OfficialWarning.warning_id == data["warning_id"]
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing:
                # Warnungen werden fortgeschrieben (msgType "Update") — Inhalt
                # aktualisieren statt eine zweite Zeile anzulegen.
                for field in ("severity", "urgency", "category", "headline",
                              "description", "instruction", "area_description",
                              "expires"):
                    value = data.get(field)
                    if value:
                        setattr(existing, field, value)
                existing.is_active = True
            else:
                session.add(OfficialWarning(**data))

        # Was nicht mehr geliefert wird, gilt als aufgehoben
        current_ids = {d["warning_id"] for d in unique_results}
        active = (await session.execute(
            select(OfficialWarning).where(OfficialWarning.is_active == True)
        )).scalars().all()
        for old in active:
            if old.warning_id not in current_ids:
                old.is_active = False

        await session.commit()

    with_text = sum(1 for r in unique_results if r.get("headline"))
    logger.info(
        "Collected %s official warnings (%s mit Volltext)",
        len(unique_results), with_text,
    )
    return unique_results


async def _fetch_region_warnings(client: httpx.AsyncClient, ars: str, region_name: str) -> list:
    """Warnungen, die der Bund dieser Gebietskoerperschaft zuordnet."""
    results = []
    try:
        resp = await client.get(f"{NINA_BASE}/dashboard/{ars}.json",
                                timeout=REQUEST_TIMEOUT,
                                headers={"Accept": "application/json"})
        if resp.status_code != 200:
            logger.warning("NINA-Dashboard %s: HTTP %s", ars, resp.status_code)
            return results

        for item in resp.json() or []:
            payload = (item.get("payload") or {}).get("data") or {}
            results.append({
                "warning_id": item.get("id", ""),
                "source_system": (payload.get("provider") or "nina").lower(),
                "severity": payload.get("severity", "Unknown"),
                "urgency": payload.get("urgency", "Unknown"),
                "category": _first(payload.get("category")) or "Unknown",
                "headline": payload.get("headline") or _title_of(item),
                "description": "",
                "instruction": None,
                "area_description": region_name,
                "effective": _parse_time(item.get("sent")),
                "expires": None,
                "is_active": True,
                "raw_data": item,
            })
    except Exception as e:
        logger.error("Fehler beim Abruf der NINA-Warnungen fuer %s: %s", ars, e)
    return results


async def _fetch_mapdata(client: httpx.AsyncClient, source: str, url: str) -> list:
    """Bundesweite Liste, auf die Region gefiltert.

    Diese Eintraege haben nur einen Titel — Details kommen spaeter per
    Einzelabruf dazu.
    """
    results = []
    try:
        resp = await client.get(url, timeout=REQUEST_TIMEOUT,
                                headers={"Accept": "application/json"})
        if resp.status_code != 200:
            return results

        for w in resp.json() or []:
            title = _title_of(w)
            if not _is_in_region(title):
                continue
            results.append({
                "warning_id": w.get("id", ""),
                "source_system": source,
                "severity": w.get("severity", "Unknown"),
                "urgency": w.get("urgency", "Unknown"),
                "category": "Unknown",
                "headline": title,
                "description": "",
                "instruction": None,
                "area_description": "",
                "effective": _parse_time(w.get("startDate")),
                "expires": None,
                "is_active": True,
                "raw_data": w,
            })
    except Exception as e:
        logger.warning("Fehler beim Abruf von %s: %s", source, e)
    return results


async def _enrich_with_details(client: httpx.AsyncClient, entry: dict) -> None:
    """Volltext einer Warnung nachladen (CAP-Struktur mit info/area)."""
    wid = entry.get("warning_id")
    if not wid:
        return
    try:
        resp = await client.get(f"{NINA_BASE}/warnings/{wid}.json",
                                timeout=REQUEST_TIMEOUT,
                                headers={"Accept": "application/json"})
        if resp.status_code != 200:
            return

        detail = resp.json() or {}
        infos = detail.get("info") or []
        info = _pick_german(infos)
        if not info:
            return

        areas = info.get("area") or []
        area_desc = ", ".join(
            a.get("areaDesc", "") for a in areas if a.get("areaDesc")
        )

        entry["headline"] = info.get("headline") or entry.get("headline") or ""
        entry["description"] = info.get("description") or ""
        entry["instruction"] = info.get("instruction")
        entry["severity"] = info.get("severity") or entry.get("severity")
        entry["urgency"] = info.get("urgency") or entry.get("urgency")
        entry["category"] = _first(info.get("category")) or entry.get("category")
        if area_desc:
            entry["area_description"] = area_desc
        if info.get("expires"):
            entry["expires"] = _parse_time(info["expires"])
        entry["area_geocode"] = areas or None
    except Exception as e:
        logger.debug("Detailabruf fuer %s fehlgeschlagen: %s", wid, e)


def _pick_german(infos: list) -> dict:
    """CAP liefert mehrere Sprachvarianten — die deutsche bevorzugen."""
    if not isinstance(infos, list) or not infos:
        return {}
    for info in infos:
        if str(info.get("language", "")).lower().startswith("de"):
            return info
    return infos[0]


def _title_of(item: dict) -> str:
    """Titel aus i18nTitle. mapData-Eintraege haben kein info-Objekt."""
    titles = item.get("i18nTitle")
    if isinstance(titles, dict):
        return titles.get("de") or next(iter(titles.values()), "")
    return item.get("headline", "") or ""


def _first(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


# Ortsbezug fuer die bundesweiten Listen. Nur ein grober Vorfilter — die
# verlaessliche Zuordnung kommt aus den Dashboard-Endpunkten je Kreis.
REGION_KEYWORDS = [
    "troisdorf", "siegburg", "rhein-sieg", "rhein sieg", "sankt augustin",
    "sankt-augustin", "niederkassel", "hennef", "lohmar", "much",
    "neunkirchen-seelscheid", "ruppichteroth", "eitorf", "windeck",
    "koenigswinter", "königswinter", "bad honnef", "bornheim", "alfter",
    "meckenheim", "rheinbach", "swisttal", "wachtberg",
    "bonn", "köln", "koeln",
]


def _is_in_region(text: str) -> bool:
    lowered = (text or "").lower()
    return any(k in lowered for k in REGION_KEYWORDS)


def _parse_time(time_str) -> Optional[datetime]:
    if not time_str:
        return None
    try:
        return datetime.fromisoformat(time_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None
