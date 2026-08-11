import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy import select

from app.models.database import async_session
from app.models.schemas import RiverShippingWarning

logger = logging.getLogger(__name__)

ELWIS_RHEIN_RSS = "https://www.elwis.de/DE/dynamisch/nif/rss/nif_rss.php?region=RHEIN"
ELWIS_MOSEL_RSS = "https://www.elwis.de/DE/dynamisch/nif/rss/nif_rss.php?region=MOSEL"

REQUEST_TIMEOUT = 30


async def collect_shipping_warnings():
    logger.info("Collecting Rhine shipping warnings...")
    all_warnings = []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        for url, river in [(ELWIS_RHEIN_RSS, "Rhein"), (ELWIS_MOSEL_RSS, "Mosel")]:
            warnings = await _fetch_rss(client, url, river)
            all_warnings.extend(warnings)

    new_count = 0
    async with async_session() as session:
        existing_ids_result = await session.execute(
            select(RiverShippingWarning.warning_id).where(
                RiverShippingWarning.warning_id.in_([w["warning_id"] for w in all_warnings])
            )
        )
        existing_ids = {row[0] for row in existing_ids_result}

        for data in all_warnings:
            if data["warning_id"] not in existing_ids:
                entry = RiverShippingWarning(**data)
                session.add(entry)
                new_count += 1
                if "sperrung" in data["title"].lower() or "hochwasser" in data["title"].lower():
                    logger.warning(f"SHIPPING: {data['title']} ({data['river']})")
        await session.commit()

    logger.info(f"Collected {len(all_warnings)} shipping warnings ({new_count} new)")
    return all_warnings


async def _fetch_rss(client: httpx.AsyncClient, url: str, river: str) -> list[dict]:
    results = []
    try:
        resp = await client.get(url)
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        items = root.findall(".//item")
        if not items:
            items = root.findall(".//entry", ns) or root.findall(".//{http://www.w3.org/2005/Atom}entry")

        for item in items:
            title = _get_text(item, "title")
            description = _get_text(item, "description") or _get_text(item, "summary", ns)
            link = _get_text(item, "link") or _get_text(item, "guid")
            pub_date = _get_text(item, "pubDate") or _get_text(item, "updated", ns)

            if not title:
                continue

            warning_id = f"elwis_{hash(f'{title}_{pub_date}')}"
            if link:
                warning_id = f"elwis_{link.split('/')[-1]}" if "/" in link else f"elwis_{hash(link)}"

            warning_type = _classify_warning(title, description or "")
            section = _extract_section(title, description or "")

            results.append({
                "warning_id": warning_id,
                "river": river,
                "section": section,
                "warning_type": warning_type,
                "title": title,
                "description": description,
                "is_active": True,
                "valid_from": _parse_datetime(pub_date),
                "valid_to": None,
                "source": "elwis",
                "raw_data": {"title": title, "description": description, "link": link, "pubDate": pub_date},
            })
    except Exception as e:
        logger.error(f"Error fetching ELWIS RSS for {river}: {e}")
    return results


def _classify_warning(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    if "sperrung" in text:
        return "closure"
    if "hochwasser" in text or "hoch" in text:
        return "high_water"
    if "niedrigwasser" in text or "niedrig" in text:
        return "low_water"
    if "eis" in text:
        return "ice"
    if "baustelle" in text or "arbeit" in text:
        return "construction"
    return "general"


def _extract_section(title: str, description: str) -> Optional[str]:
    text = f"{title} {description}"
    markers = ["km ", "Km ", "KM ", "Rhein-km", "Mosel-km"]
    for marker in markers:
        idx = text.find(marker)
        if idx != -1:
            return text[max(0, idx - 20):idx + 30].strip()
    return None


def _get_text(element, tag: str, ns: dict = None) -> Optional[str]:
    child = element.find(tag, ns) if ns else element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return None


def _parse_datetime(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        pass
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(value).replace(tzinfo=None)
    except Exception:
        pass
    return None
