"""Hochwasser-Meldestufen NRW über OpenHygon (LANUV) + Rhein über PEGELONLINE."""
import csv
import io
import logging
import zipfile
from datetime import datetime
from typing import Optional

import httpx

from app.models.database import async_session
from app.models.schemas import FloodWarningLevel

logger = logging.getLogger(__name__)

OPENHYGON_STATIONS = (
    "https://www.opengeodata.nrw.de/produkte/umwelt_klima/wasser/"
    "oberflaechengewaesser/hygon/OpenHygon-Pegel-Stationen_EPSG4326.txt"
)
OPENHYGON_VALUES_ZIP = (
    "https://www.opengeodata.nrw.de/produkte/umwelt_klima/wasser/"
    "oberflaechengewaesser/hygon/OpenHygon-Pegel-aktuell_CSV.zip"
)

# Stationen Sieg/Agger rund um Troisdorf
LOCAL_STATIONS = {
    "2729100000100": {"name": "Menden (Sieg)", "river": "Sieg"},
    "2727500000100": {"name": "Siegburg Kaldenhausen", "river": "Sieg"},
    "2728930000200": {"name": "Lohmar (Agger)", "river": "Agger"},
    "2725910000100": {"name": "Eitorf (Sieg)", "river": "Sieg"},
}

# Rhein-Bundespegel (PEGELONLINE) – HSW/MHW als Meldestufen-Proxy
RHEIN_STATIONS = {
    "Bonn": "593647aa-9fea-43ec-a7d6-6476a76ae868",
    "Köln": "a6ee8177-107b-47dd-bcfd-30960ccc6e9c",
}

PEGELONLINE = "https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations"
REQUEST_TIMEOUT = 45


async def collect_flood_warnings():
    logger.info("Collecting flood warning levels (OpenHygon + PEGELONLINE)...")
    all_results = []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        all_results.extend(await _fetch_openhygon(client))
        all_results.extend(await _fetch_rhein_pegelonline(client))

    for r in all_results:
        if r["warning_level"] >= 2:
            logger.warning(
                "HOCHWASSER Warnstufe %s: %s (%s) - %s cm",
                r["warning_level"], r["station_name"], r["river"], r.get("level_cm"),
            )

    async with async_session() as session:
        for data in all_results:
            session.add(FloodWarningLevel(**data))
        await session.commit()

    logger.info("Collected %s flood warning readings", len(all_results))
    return all_results


async def _fetch_openhygon(client: httpx.AsyncClient) -> list[dict]:
    results = []
    try:
        # Stationen inkl. LANUV_Info_1/2/3 (= Meldestufen)
        st_resp = await client.get(OPENHYGON_STATIONS)
        st_resp.raise_for_status()
        # Encoding: oft latin-1 / utf-8
        text = st_resp.content.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        thresholds = {}
        for row in reader:
            sno = (row.get("station_no") or "").strip()
            if sno not in LOCAL_STATIONS:
                continue
            thresholds[sno] = {
                "i1": _float(row.get("LANUV_Info_1")),
                "i2": _float(row.get("LANUV_Info_2")),
                "i3": _float(row.get("LANUV_Info_3")),
                "name": row.get("station_name") or LOCAL_STATIONS[sno]["name"],
            }

        # Aktuelle Messwerte (ZIP)
        zip_resp = await client.get(OPENHYGON_VALUES_ZIP)
        zip_resp.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(zip_resp.content))
        # Erste Datei
        name = zf.namelist()[0]
        data = zf.read(name).decode("utf-8", errors="replace").splitlines()
        latest = {}
        for line in data[1:]:
            parts = line.split(";")
            if len(parts) < 3:
                continue
            sno, t, v = parts[0].strip(), parts[1].strip(), parts[2].strip()
            if sno not in LOCAL_STATIONS or not v:
                continue
            if sno not in latest or t > latest[sno][0]:
                latest[sno] = (t, _float(v))

        for sno, (t, level) in latest.items():
            meta = LOCAL_STATIONS[sno]
            thr = thresholds.get(sno, {})
            level_cm = level
            warning_level = _level_from_thresholds(
                level_cm, thr.get("i1"), thr.get("i2"), thr.get("i3")
            )
            results.append({
                "station_id": sno,
                "station_name": thr.get("name") or meta["name"],
                "river": meta["river"],
                "warning_level": warning_level,
                "level_cm": level_cm,
                "trend": None,
                "state": "NW",
                "timestamp": _parse_ts(t),
                "source": "openhygon_lanuv",
                "raw_data": {
                    "station_no": sno,
                    "time": t,
                    "value_cm": level_cm,
                    "LANUV_Info_1": thr.get("i1"),
                    "LANUV_Info_2": thr.get("i2"),
                    "LANUV_Info_3": thr.get("i3"),
                },
            })
    except Exception as e:
        logger.error("Error fetching OpenHygon flood data: %s", e)
    return results


async def _fetch_rhein_pegelonline(client: httpx.AsyncClient) -> list[dict]:
    results = []
    for name, uuid in RHEIN_STATIONS.items():
        try:
            resp = await client.get(
                f"{PEGELONLINE}/{uuid}.json",
                params={
                    "includeTimeseries": "true",
                    "includeCurrentMeasurement": "true",
                    "includeCharacteristicValues": "true",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            w_ts = next((t for t in data.get("timeseries", []) if t.get("shortname") == "W"), None)
            if not w_ts:
                continue
            current = w_ts.get("currentMeasurement") or {}
            level = current.get("value")
            if level is None:
                continue
            chars = {c.get("shortname"): c.get("value") for c in w_ts.get("characteristicValues", [])}
            # Proxy-Meldestufen aus Kennwerten
            mnw, mw, mhw, hhw = chars.get("MNW"), chars.get("MW"), chars.get("MHW"), chars.get("HHW")
            # Heuristik: >MW leicht erhöht, >MHW Stufe 2, >HHW*0.8 Stufe 3, >HHW Stufe 4
            warning_level = 0
            if mhw is not None and level >= mhw:
                warning_level = 2
            if hhw is not None and level >= hhw * 0.8:
                warning_level = 3
            if hhw is not None and level >= hhw:
                warning_level = 4
            if warning_level == 0 and mw is not None and level >= mw * 1.5:
                warning_level = 1

            # Auch bei Niedrigwasser dokumentieren (Stufe 0)
            results.append({
                "station_id": uuid,
                "station_name": name,
                "river": "Rhein",
                "warning_level": warning_level,
                "level_cm": float(level),
                "trend": None,
                "state": "NW",
                "timestamp": _parse_ts(current.get("timestamp")) or datetime.utcnow(),
                "source": "pegelonline",
                "raw_data": {
                    "current": current,
                    "chars": chars,
                    "stateMnwMhw": current.get("stateMnwMhw"),
                },
            })
        except Exception as e:
            logger.error("Error fetching PEGELONLINE flood data for %s: %s", name, e)
    return results


def _level_from_thresholds(level: Optional[float], i1, i2, i3) -> int:
    if level is None:
        return 0
    if i3 is not None and level >= i3:
        return 3
    if i2 is not None and level >= i2:
        return 2
    if i1 is not None and level >= i1:
        return 1
    return 0


def _float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except (ValueError, TypeError):
        return None


def _parse_ts(ts) -> datetime:
    if not ts:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return datetime.utcnow()
