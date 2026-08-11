import logging
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy import select

from app.models.database import async_session
from app.models.schemas import OfficialWarning

logger = logging.getLogger(__name__)

BONN_CKAN_URL = "https://opendata.bonn.de/api/3/action/package_show?id=warnmeldung-feuerwehr-bonn"


async def collect_feuerwehr_bonn():
    logger.info("Collecting Feuerwehr Bonn warnings...")
    results = []

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(BONN_CKAN_URL)
            resp.raise_for_status()
            ckan_data = resp.json()

            if not ckan_data.get("success"):
                logger.warning("CKAN Feuerwehr Bonn request was not successful")
                return results

            resources = ckan_data.get("result", {}).get("resources", [])
            data_url = None
            resource_id = None
            for resource in resources:
                fmt = resource.get("format", "").upper()
                if fmt in ("JSON", "GEOJSON"):
                    data_url = resource.get("url")
                    resource_id = resource.get("id")
                    break

            if not data_url and resource_id:
                data_url = (
                    f"https://opendata.bonn.de/api/3/action/datastore_search"
                    f"?resource_id={resource_id}"
                )

            if not data_url and resources:
                resource_id = resources[0].get("id")
                if resource_id:
                    data_url = (
                        f"https://opendata.bonn.de/api/3/action/datastore_search"
                        f"?resource_id={resource_id}"
                    )

            if not data_url:
                logger.warning("No suitable resource found for Feuerwehr Bonn warnings")
                return results

            resp = await client.get(data_url)
            resp.raise_for_status()
            data = resp.json()

            warnings = _extract_warnings(data)

            for w in warnings:
                warning_id = _build_warning_id(w)
                if not warning_id:
                    continue

                results.append({
                    "warning_id": warning_id,
                    "source_system": "feuerwehr_bonn",
                    "severity": w.get("severity", w.get("Schwere", w.get("schweregrad", "Unknown"))),
                    "urgency": w.get("urgency", w.get("Dringlichkeit", "Unknown")),
                    "category": w.get("category", w.get("Kategorie", w.get("typ", "fire"))),
                    "headline": w.get("headline", w.get("Titel", w.get("titel", w.get("title", "")))),
                    "description": w.get("description", w.get("Beschreibung", w.get("beschreibung", w.get("text", "")))),
                    "instruction": w.get("instruction", w.get("Handlungsempfehlung", w.get("hinweis"))),
                    "area_description": w.get("area", w.get("Ort", w.get("ort", w.get("location", "Bonn")))),
                    "area_geocode": w.get("geocode"),
                    "effective": _parse_time(w.get("effective", w.get("Datum", w.get("datum", w.get("start"))))),
                    "expires": _parse_time(w.get("expires", w.get("Ende", w.get("ende", w.get("end"))))),
                    "is_active": True,
                    "raw_data": w,
                })
        except Exception as e:
            logger.error(f"Error fetching Feuerwehr Bonn warnings: {e}")

    new_count = 0
    async with async_session() as session:
        for data in results:
            stmt = select(OfficialWarning).where(
                OfficialWarning.warning_id == data["warning_id"]
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                entry = OfficialWarning(**data)
                session.add(entry)
                new_count += 1
                logger.info(f"New Feuerwehr Bonn warning: {data['headline']}")
        await session.commit()

    logger.info(f"Collected {len(results)} Feuerwehr Bonn warnings, {new_count} new")
    return results


def _extract_warnings(data: dict) -> list:
    if isinstance(data, list):
        return data

    if "result" in data:
        result = data["result"]
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            records = result.get("records", result.get("results", []))
            if isinstance(records, list):
                return records

    if "records" in data:
        return data["records"]

    if "data" in data and isinstance(data["data"], list):
        return data["data"]

    return [data] if data else []


def _build_warning_id(warning: dict) -> Optional[str]:
    wid = warning.get("id", warning.get("_id", warning.get("identifier")))
    if wid:
        return f"feuerwehr_bonn_{wid}"

    title = warning.get("headline", warning.get("Titel", warning.get("titel", warning.get("title", ""))))
    date = warning.get("effective", warning.get("Datum", warning.get("datum", warning.get("start", ""))))
    if title:
        return f"feuerwehr_bonn_{hash(f'{title}_{date}')}"

    return None


def _parse_time(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        pass
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(value), fmt)
        except (ValueError, TypeError):
            continue
    return None
