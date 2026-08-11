import logging
from datetime import datetime

import httpx

from app.models.database import async_session
from app.models.schemas import ICUCapacity

logger = logging.getLogger(__name__)

DIVI_API_URL = "https://www.intensivregister.de/api/public/intensivregister"
DIVI_ZEITREIHEN_URL = "https://diviexchange.blob.core.windows.net/opendata/zeitreihe-tagesdaten.csv"

RELEVANT_KREISE = {
    "05382": "Rhein-Sieg-Kreis",
    "05315": "Köln",
    "05314": "Bonn",
}

REQUEST_TIMEOUT = 30


async def collect_icu_capacity():
    logger.info("Collecting ICU capacity data...")
    results = []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        results = await _fetch_api(client)
        if not results:
            logger.info("API returned no results, trying CSV fallback...")
            results = await _fetch_csv(client)

    critical = [r for r in results if r["occupancy_rate"] > 0.9]
    if critical:
        for r in critical:
            logger.warning(
                f"ICU CAPACITY CRITICAL: {r['region_name']} "
                f"occupancy {r['occupancy_rate']:.0%} ({r['beds_free']} beds free)"
            )

    async with async_session() as session:
        for data in results:
            entry = ICUCapacity(**data)
            session.add(entry)
        await session.commit()

    logger.info(f"Collected {len(results)} ICU capacity readings")
    return results


async def _fetch_api(client: httpx.AsyncClient) -> list[dict]:
    results = []
    try:
        resp = await client.get(DIVI_API_URL, params={"format": "json"})
        resp.raise_for_status()
        data = resp.json()

        entries = data if isinstance(data, list) else data.get("data", data.get("features", []))

        for entry in entries:
            props = entry.get("properties", entry) if isinstance(entry, dict) else {}
            kreis_id = str(props.get("kreis") or props.get("gemeindeschluessel") or props.get("ags", ""))[:5]

            if kreis_id not in RELEVANT_KREISE:
                continue

            beds_total = _int(props.get("betten_gesamt") or props.get("faelle_covid_aktuell_beatmet"))
            beds_occupied = _int(props.get("betten_belegt"))
            beds_free = _int(props.get("betten_frei"))

            if beds_total is None and beds_occupied is not None and beds_free is not None:
                beds_total = beds_occupied + beds_free
            if beds_total is None or beds_total == 0:
                continue

            if beds_free is None and beds_occupied is not None:
                beds_free = beds_total - beds_occupied
            if beds_occupied is None and beds_free is not None:
                beds_occupied = beds_total - beds_free

            occupancy = beds_occupied / beds_total if beds_total > 0 else 0

            results.append({
                "region_id": kreis_id,
                "region_name": RELEVANT_KREISE.get(kreis_id, f"Region {kreis_id}"),
                "beds_total": beds_total,
                "beds_occupied": beds_occupied or 0,
                "beds_free": beds_free or 0,
                "ventilator_occupied": _int(props.get("faelle_covid_aktuell_beatmet")),
                "ventilator_free": _int(props.get("freie_iv_kapazitaet")),
                "occupancy_rate": round(occupancy, 3),
                "timestamp": datetime.utcnow(),
                "source": "divi_api",
                "raw_data": entry,
            })
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            logger.info("DIVI API requires authentication, falling back to CSV")
        else:
            logger.error(f"Error fetching DIVI API: {e}")
    except Exception as e:
        logger.error(f"Error fetching DIVI API: {e}")
    return results


async def _fetch_csv(client: httpx.AsyncClient) -> list[dict]:
    results = []
    try:
        resp = await client.get(DIVI_ZEITREIHEN_URL)
        resp.raise_for_status()
        text = resp.text

        lines = text.strip().split("\n")
        if len(lines) < 2:
            return results

        headers = [h.strip().lower() for h in lines[0].split(",")]

        latest_by_region = {}
        for line in lines[1:]:
            vals = line.split(",")
            if len(vals) < len(headers):
                continue
            row = dict(zip(headers, vals))

            kreis_id = str(row.get("gemeindeschluessel", row.get("kreis", "")))[:5]
            if kreis_id not in RELEVANT_KREISE:
                continue

            date_str = row.get("datum", row.get("date", ""))
            if kreis_id not in latest_by_region or date_str > latest_by_region[kreis_id].get("_date", ""):
                row["_date"] = date_str
                latest_by_region[kreis_id] = row

        for kreis_id, row in latest_by_region.items():
            beds_total = _int(row.get("betten_gesamt"))
            beds_occupied = _int(row.get("betten_belegt"))
            beds_free = _int(row.get("betten_frei"))

            if beds_total is None and beds_occupied is not None and beds_free is not None:
                beds_total = beds_occupied + beds_free
            if not beds_total:
                continue
            if beds_free is None and beds_occupied is not None:
                beds_free = beds_total - beds_occupied
            if beds_occupied is None and beds_free is not None:
                beds_occupied = beds_total - beds_free

            occupancy = (beds_occupied or 0) / beds_total if beds_total > 0 else 0

            results.append({
                "region_id": kreis_id,
                "region_name": RELEVANT_KREISE.get(kreis_id, f"Region {kreis_id}"),
                "beds_total": beds_total,
                "beds_occupied": beds_occupied or 0,
                "beds_free": beds_free or 0,
                "ventilator_occupied": _int(row.get("faelle_covid_aktuell_beatmet")),
                "ventilator_free": _int(row.get("freie_iv_kapazitaet")),
                "occupancy_rate": round(occupancy, 3),
                "timestamp": datetime.utcnow(),
                "source": "divi_csv",
                "raw_data": {k: v for k, v in row.items() if k != "_date"},
            })
    except Exception as e:
        logger.error(f"Error fetching DIVI CSV: {e}")
    return results


def _int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None
