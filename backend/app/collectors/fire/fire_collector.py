import gzip
import logging
from datetime import datetime

import httpx

from app.config import settings
from app.models.database import async_session
from app.models.schemas import FireRisk

logger = logging.getLogger(__name__)

# Offizieller DWD-Waldbrandgefahrenindex (WBI), täglich ~05:00 UTC aktualisiert.
# CSV pro Station: StationsID;Termin;wbi_0..wbi_6 (heute + 6 Folgetage, Stufen 1-5)
DWD_WBI_BASE = "https://opendata.dwd.de/climate_environment/CDC/derived_germany/fire_danger_index/woodland/forecast/recent"
DWD_WBI_VERSION = "v2-3--0"
# Station 2667 = Köln/Bonn, liegt direkt in der Wahner Heide
DWD_WBI_STATIONS = {"2667": "Köln/Bonn (Wahner Heide)"}
NASA_FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

WAHNER_HEIDE_BBOX = {
    "min_lat": 50.83,
    "max_lat": 50.91,
    "min_lon": 7.10,
    "max_lon": 7.20,
}


async def collect_fire_risk():
    logger.info("Collecting fire risk data...")
    results = []

    async with httpx.AsyncClient() as client:
        dwd_results = await _fetch_dwd_fire_index(client)
        results.extend(dwd_results)

        satellite_results = await _fetch_nasa_firms(client)
        results.extend(satellite_results)

    async with async_session() as session:
        for data in results:
            entry = FireRisk(**data)
            session.add(entry)
        await session.commit()

    logger.info(f"Collected {len(results)} fire risk entries")
    return results


async def _fetch_dwd_fire_index(client: httpx.AsyncClient) -> list:
    results = []
    for station_id, station_name in DWD_WBI_STATIONS.items():
        try:
            url = (
                f"{DWD_WBI_BASE}/derived_germany_fire_danger_index_woodland_"
                f"forecast_recent_{station_id}_{DWD_WBI_VERSION}.csv.gz"
            )
            resp = await client.get(url, timeout=30)
            resp.raise_for_status()

            lines = gzip.decompress(resp.content).decode("latin-1").strip().splitlines()
            if len(lines) < 2:
                continue

            header = [h.strip() for h in lines[0].split(";")]
            latest = [v.strip() for v in lines[-1].split(";")]
            row = dict(zip(header, latest))

            issued = datetime.strptime(row["Termin"], "%Y%m%d %H:%M")
            # wbi_0 gilt für den Ausgabetag; liegt der zurück, entsprechend
            # in die Vorhersagespalten verschieben (Ausgabe nur 1x täglich)
            offset = max(0, (datetime.utcnow().date() - issued.date()).days)
            if offset > 6:
                logger.warning(f"DWD WBI für Station {station_id} veraltet (Ausgabe {issued})")
                continue

            today_index = int(row[f"wbi_{offset}"])
            forecast = {
                f"+{i - offset}d": int(row[f"wbi_{i}"])
                for i in range(offset, 7)
                if row.get(f"wbi_{i}", "").isdigit()
            }

            results.append({
                "region": station_name,
                "risk_index": today_index,
                "source": "dwd_fire_index",
                "timestamp": datetime.utcnow(),
                "raw_data": {
                    "station_id": station_id,
                    "issued": issued.isoformat(),
                    "forecast": forecast,
                },
            })
        except Exception as e:
            logger.warning(f"Error fetching DWD fire index for station {station_id}: {e}")

    return results


async def _fetch_nasa_firms(client: httpx.AsyncClient) -> list:
    results = []
    try:
        bbox = WAHNER_HEIDE_BBOX
        area = f"{bbox['min_lon']},{bbox['min_lat']},{bbox['max_lon']},{bbox['max_lat']}"
        extended_bbox = {
            "min_lat": settings.center_lat - 0.5,
            "max_lat": settings.center_lat + 0.5,
            "min_lon": settings.center_lon - 0.5,
            "max_lon": settings.center_lon + 0.5,
        }
        area_wide = f"{extended_bbox['min_lon']},{extended_bbox['min_lat']},{extended_bbox['max_lon']},{extended_bbox['max_lat']}"

        url = f"{NASA_FIRMS_URL}/VIIRS_SNPP_NRT/{area_wide}/1"
        resp = await client.get(url, timeout=30)

        hotspots = []
        if resp.status_code == 200 and resp.text.strip():
            lines = resp.text.strip().split("\n")
            if len(lines) > 1:
                headers = lines[0].split(",")
                for line in lines[1:]:
                    vals = line.split(",")
                    if len(vals) >= len(headers):
                        spot = dict(zip(headers, vals))
                        hotspots.append(spot)

        if hotspots:
            wahner_heide_spots = [
                s for s in hotspots
                if (bbox["min_lat"] <= float(s.get("latitude", 0)) <= bbox["max_lat"]
                    and bbox["min_lon"] <= float(s.get("longitude", 0)) <= bbox["max_lon"])
            ]

            results.append({
                "region": f"{settings.region} (Satellit)",
                "risk_index": min(5, len(hotspots) + 1),
                "satellite_hotspots": hotspots,
                "source": "nasa_firms",
                "timestamp": datetime.utcnow(),
                "raw_data": {
                    "total_hotspots": len(hotspots),
                    "wahner_heide_hotspots": len(wahner_heide_spots),
                },
            })
    except Exception as e:
        logger.warning(f"Error fetching NASA FIRMS data: {e}")

    return results
