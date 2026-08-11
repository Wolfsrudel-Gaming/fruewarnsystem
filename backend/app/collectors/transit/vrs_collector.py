"""ÖPNV-Störungen: KVB Betriebslage (JSON-LD) + VRR/DELFI ADDINFO (RapidJSON)."""
import hashlib
import json
import logging
import re
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy import select

from app.models.database import async_session
from app.models.schemas import TransitDisruption

logger = logging.getLogger(__name__)

KVB_BETRIEBSLAGE_URL = "https://www.kvb.koeln/fahrtinfo/betriebslage/"
VRR_ADDINFO_URL = "https://openservice.vrr.de/vrr/XML_ADDINFO_REQUEST"

# Linien/Orte für Troisdorf / Rhein-Sieg / Köln / Bonn (exakte Tokens)
RELEVANT_LINES = {
    "S12", "S13", "S19", "RB25", "RE8", "RE9", "RE5", "RB27", "RB48",
    "66", "67", "16", "18", "68",
}
RELEVANT_PLACES = {
    "troisdorf", "siegburg", "porz", "niederkassel", "mondorf",
    "bonn", "köln", "koeln", "cologne", "wahner heide", "spich",
}

REQUEST_TIMEOUT = 40


async def collect_transit_disruptions():
    logger.info("Collecting transit disruptions...")
    all_disruptions = []

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": "DRK-Fruehwarnsystem/1.0"},
    ) as client:
        all_disruptions.extend(await _fetch_kvb(client))
        all_disruptions.extend(await _fetch_vrr(client))

    new_count = 0
    async with async_session() as session:
        for data in all_disruptions:
            did = data.get("disruption_id")
            if did:
                existing = await session.execute(
                    select(TransitDisruption).where(TransitDisruption.disruption_id == did)
                )
                if existing.scalar_one_or_none():
                    continue
            session.add(TransitDisruption(**data))
            new_count += 1
            if data["disruption_type"] in ("cancellation", "closure"):
                logger.warning("TRANSIT: %s (%s)", data["title"][:120], data["line"])
        await session.commit()

    logger.info("Collected %s transit disruptions (%s new)", len(all_disruptions), new_count)
    return all_disruptions


def _clip(value: Optional[str], n: int) -> Optional[str]:
    if value is None:
        return None
    s = str(value)
    return s if len(s) <= n else s[: n - 1] + "…"


async def _fetch_kvb(client: httpx.AsyncClient) -> list[dict]:
    results = []
    try:
        resp = await client.get(KVB_BETRIEBSLAGE_URL)
        resp.raise_for_status()
        blocks = re.findall(
            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            resp.text,
            re.S | re.I,
        )
        for block in blocks:
            try:
                obj = json.loads(block)
            except json.JSONDecodeError:
                continue
            items = obj if isinstance(obj, list) else [obj]
            for item in items:
                types = item.get("@type")
                type_list = types if isinstance(types, list) else [types]
                if "SpecialAnnouncement" not in type_list:
                    continue

                name = (item.get("name") or "").strip()
                if not name:
                    continue
                description = (item.get("description") or "").strip()
                date_posted = _parse_dt(item.get("datePosted"))
                line = _extract_line_from_kvb(item, name)
                did = "kvb_" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:16]

                results.append({
                    "disruption_id": did,
                    "line": _clip(line or "KVB", 100),
                    "route": None,
                    "disruption_type": _classify_type(name, description),
                    "title": _clip(name, 500),
                    "description": _clip(description, 5000) if description else None,
                    "is_active": True,
                    "valid_from": date_posted,
                    "valid_to": None,
                    "source": "kvb_betriebslage",
                    "raw_data": {
                        "name": name,
                        "datePosted": item.get("datePosted"),
                        "url": item.get("url"),
                        "additionalProperty": item.get("additionalProperty"),
                    },
                })
    except Exception as e:
        logger.error("Error fetching KVB Betriebslage: %s", e)
    return results


def _extract_line_from_kvb(item: dict, name: str) -> str:
    props = item.get("additionalProperty") or []
    if isinstance(props, dict):
        props = [props]
    lines = []
    for prop in props:
        if not isinstance(prop, dict):
            continue
        if str(prop.get("name", "")).lower() in ("linie", "line", "lines"):
            val = prop.get("value")
            if val:
                lines.append(str(val))
    if lines:
        return ", ".join(lines)
    m = re.match(r"Linie\s+([A-Za-z0-9/]+)", name)
    return m.group(1) if m else "KVB"


async def _fetch_vrr(client: httpx.AsyncClient) -> list[dict]:
    results = []
    try:
        resp = await client.get(
            VRR_ADDINFO_URL,
            params={"outputFormat": "rapidJSON", "filterPublicationStatus": "current"},
        )
        resp.raise_for_status()
        data = resp.json()
        current = (data.get("infos") or {}).get("current") or []
        if isinstance(current, dict):
            current = [current]

        for info in current:
            if not _is_relevant(info):
                continue
            parsed = _parse_vrr_info(info)
            if parsed:
                results.append(parsed)
    except Exception as e:
        logger.error("Error fetching VRR ADDINFO: %s", e)
    return results


def _is_relevant(info: dict) -> bool:
    """Nur Meldungen mit klarer Linien-/Ortsrelevanz für die Region.

    Kurze Nummernlinien (16/18/66…) nur akzeptieren, wenn auch ein Ortsbezug
    zu Köln/Bonn/Troisdorf etc. besteht – sonst matchen sie NRW-weit falsch.
    """
    affected = info.get("affected") or {}
    line_tokens = set()
    for line in affected.get("lines") or []:
        if isinstance(line, dict):
            for key in ("number", "name"):
                val = (line.get(key) or "").strip().upper()
                if val:
                    token = re.split(r"[\s(/]", val, 1)[0]
                    line_tokens.add(token)
        elif isinstance(line, str):
            line_tokens.add(line.strip().upper())

    blob = json.dumps(info, ensure_ascii=False).lower()
    place_hit = any(re.search(rf"\b{re.escape(place)}\b", blob) for place in RELEVANT_PLACES)

    named = {l.upper() for l in RELEVANT_LINES if not l.isdigit()}
    numeric = {l.upper() for l in RELEVANT_LINES if l.isdigit()}

    if line_tokens & named:
        return True
    if (line_tokens & numeric) and place_hit:
        return True
    # Ortsbezug allein (z. B. Bahnhof Troisdorf ohne Linienliste)
    if place_hit and (line_tokens or "troisdorf" in blob or "siegburg" in blob):
        return True
    return False


def _parse_vrr_info(info: dict) -> Optional[dict]:
    links = info.get("infoLinks") or []
    link = links[0] if links else {}
    title = (link.get("title") or link.get("subtitle") or info.get("type") or "Störung").strip()
    description = (link.get("smsText") or link.get("content") or "").strip()
    description = re.sub(r"<[^>]+>", " ", description)
    description = re.sub(r"\s+", " ", description).strip()

    affected = info.get("affected") or {}
    lines = []
    for line in affected.get("lines") or []:
        if isinstance(line, dict):
            lines.append(line.get("number") or line.get("name") or "")
        elif isinstance(line, str):
            lines.append(line)
    # dedupe preserving order
    seen = set()
    uniq = []
    for l in lines:
        t = l.strip()
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    line_str = ", ".join(uniq) or "ÖPNV"

    timestamps = info.get("timestamps") or {}
    validity = timestamps.get("validity") or []
    valid_from = valid_to = None
    if validity and isinstance(validity, list):
        valid_from = _parse_dt(validity[0].get("from"))
        valid_to = _parse_dt(validity[0].get("to"))
    if not valid_from:
        valid_from = _parse_dt((timestamps.get("availability") or {}).get("from"))

    did_raw = info.get("id") or title
    return {
        "disruption_id": f"vrr_{did_raw}"[:200],
        "line": _clip(line_str, 100),
        "route": _clip(link.get("subtitle"), 500),
        "disruption_type": _classify_type(title, description),
        "title": _clip(title, 500),
        "description": _clip(description, 5000) if description else None,
        "is_active": True,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "source": "vrr_addinfo",
        "raw_data": {
            "id": info.get("id"),
            "type": info.get("type"),
            "title": title,
            "lines": uniq,
        },
    }


def _classify_type(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    if "ausfall" in text or "fällt aus" in text:
        return "cancellation"
    if "sperrung" in text or "gesperrt" in text:
        return "closure"
    if "umleitung" in text or "getrennt" in text:
        return "diversion"
    if "verspätung" in text or "verzögerung" in text:
        return "delay"
    if "bauarbeit" in text or "baumaßnahme" in text or "baustelle" in text:
        return "construction"
    if "einschränkung" in text or "beeinträchtigung" in text:
        return "restriction"
    return "general"


def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        pass
    for fmt in ("%d.%m.%Y %H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(value)[:19], fmt)
        except (ValueError, TypeError):
            continue
    return None
