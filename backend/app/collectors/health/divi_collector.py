"""ICU-Kapazitäten über RKI Open Data (Intensivregister)."""
import csv
import logging
from datetime import datetime

import httpx

from app.models.database import async_session
from app.models.schemas import ICUCapacity

logger = logging.getLogger(__name__)

RKI_BUNDESLAND_CSV = (
    "https://raw.githubusercontent.com/robert-koch-institut/"
    "Intensivkapazitaeten_und_COVID-19-Intensivbettenbelegung_in_Deutschland/main/"
    "Intensivregister_Bundeslaender_Kapazitaeten.csv"
)
RKI_LANDKREIS_CSV = (
    "https://raw.githubusercontent.com/robert-koch-institut/"
    "Intensivkapazitaeten_und_COVID-19-Intensivbettenbelegung_in_Deutschland/main/"
    "Intensivregister_Landkreise_Kapazitaeten.csv"
)

# AGS / RKI-IDs der Region
REGIONS = {
    "05": "Nordrhein-Westfalen",
    "05382": "Rhein-Sieg-Kreis",
    "05315": "Köln",
    "05314": "Bonn",
}

REQUEST_TIMEOUT = 45


def _int(value) -> int | None:
    if value is None or value == "" or value == "NA":
        return None
    try:
        return int(float(str(value).replace(",", ".")))
    except (ValueError, TypeError):
        return None


async def collect_icu_capacity():
    logger.info("Collecting ICU capacity data (RKI Intensivregister)...")
    results = []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        # Landkreise zuerst (feiner), Bundesland als Fallback/Ergänzung
        kreis = await _fetch_csv(client, RKI_LANDKREIS_CSV, id_field="landkreis_id", name_field="landkreis_name")
        land = await _fetch_csv(client, RKI_BUNDESLAND_CSV, id_field="bundesland_id", name_field="bundesland_name")
        results = kreis + land

    critical = [r for r in results if r["occupancy_rate"] and r["occupancy_rate"] > 0.9]
    for r in critical:
        logger.warning(
            "ICU CAPACITY CRITICAL: %s occupancy %.0f%% (%s beds free)",
            r["region_name"], r["occupancy_rate"] * 100, r["beds_free"],
        )

    async with async_session() as session:
        for data in results:
            session.add(ICUCapacity(**data))
        await session.commit()

    logger.info("Collected %s ICU capacity readings", len(results))
    return results


async def _fetch_csv(client: httpx.AsyncClient, url: str, id_field: str, name_field: str) -> list[dict]:
    results = []
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        rows = list(csv.DictReader(resp.text.splitlines()))
        latest_by_region: dict[str, dict] = {}

        for row in rows:
            region_id = str(row.get(id_field, "")).strip()
            if region_id not in REGIONS:
                continue
            # Nur Erwachsene (Hauptindikator); Kinder ggf. separat
            gruppe = (row.get("behandlungsgruppe") or "").strip()
            if gruppe and gruppe != "Erwachsene":
                continue
            date_str = row.get("datum") or ""
            prev = latest_by_region.get(region_id)
            if prev is None or date_str > prev.get("_date", ""):
                row["_date"] = date_str
                latest_by_region[region_id] = row

        for region_id, row in latest_by_region.items():
            occupied = _int(row.get("intensivbetten_belegt"))
            free = _int(row.get("intensivbetten_frei"))
            if occupied is None and free is None:
                continue
            total = (occupied or 0) + (free or 0)
            if total <= 0:
                continue
            occupancy = (occupied or 0) / total
            vent_free = _int(row.get("kapazitaeten_frei_invasive_beatmung_gesamt"))

            results.append({
                "region_id": region_id,
                "region_name": REGIONS.get(region_id) or row.get(name_field) or region_id,
                "beds_total": total,
                "beds_occupied": occupied or 0,
                "beds_free": free or 0,
                "ventilator_occupied": None,
                "ventilator_free": vent_free,
                "occupancy_rate": round(occupancy, 3),
                "timestamp": datetime.utcnow(),
                "source": "rki_intensivregister",
                "raw_data": {k: v for k, v in row.items() if k != "_date"},
            })
    except Exception as e:
        logger.error("Error fetching RKI ICU CSV %s: %s", url, e)
    return results
