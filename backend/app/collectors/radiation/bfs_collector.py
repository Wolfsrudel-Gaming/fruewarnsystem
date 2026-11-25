import logging
from datetime import datetime

import httpx

from app.models.database import async_session
from app.models.schemas import RadiationReading

logger = logging.getLogger(__name__)

TROISDORF_LAT = 50.8159
TROISDORF_LON = 7.1533

LAT_MIN = 50.5
LAT_MAX = 51.1
LON_MIN = 6.8
LON_MAX = 7.5

ELEVATED_THRESHOLD_NSV = 300

REQUEST_TIMEOUT = 30


def _is_in_region(lat: float, lon: float) -> bool:
    return LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX


# Am 25.11.2026 geprueft: Der frueher genutzte Pfad odlinfo.bfs.de/json/stat.json
# antwortet mit 404 — er ist nach /daten/json/ umgezogen UND hat dabei die
# Form gewechselt: Dort stehen jetzt nur noch Kennzahlen (Bundesmittelwert,
# Minimum, Maximum), keine Stationsreihen mehr. Die Stationswerte liefert der
# WFS des BfS-IMIS.
#
# Der Abruf lief trotzdem nicht ins Leere: Der WFS war als Rueckfall
# hinterlegt und hat die Luecke gedeckt. Aufgefallen ist der Ausfall nur
# daran, dass bei jedem Durchlauf eine Fehlerzeile ins Protokoll ging und
# vorher 890 KB umsonst angefragt wurden. Radioaktivitaet ist die eine
# Kategorie, die dieses System nie abwertet — hier auf einem Rueckfall zu
# stehen, ohne es zu wissen, war der eigentliche Mangel.
ODL_KENNZAHLEN = "https://odlinfo.bfs.de/daten/json/stat.json"

# Natuerlicher Untergrund in Deutschland: etwa 50 bis 200 nSv/h. Weicht die
# Messung im Umkreis stark vom Bundesmittel ab, ist das entweder eine echte
# Lage oder ein Datenfehler — in beiden Faellen etwas, das man sehen will.
PLAUSIBEL_FAKTOR = 3.0


async def fetch_bundesmittel(client: httpx.AsyncClient):
    """Bundesweiter Mittelwert als Vergleichsgroesse (nSv/h).

    Nicht zur Bewertung, sondern zur Plausibilitaetspruefung: Eine einzelne
    Station, die weit ueber dem Bundesmittel liegt, ist ein Hinweis; liegen
    alle daneben, stimmt eher die Quelle nicht.
    """
    try:
        resp = await client.get(ODL_KENNZAHLEN, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        daten = resp.json() or {}
        mittel = (daten.get("mwavg") or {}).get("mw")
        return float(mittel) * 1000 if mittel is not None else None
    except Exception as e:
        logger.debug("BfS-Kennzahlen nicht abrufbar: %s", e)
        return None


async def _fetch_odl_json(client: httpx.AsyncClient) -> list[dict]:
    """Nicht mehr genutzt — der Endpunkt fuehrt keine Stationsreihen mehr.

    Bleibt als Dokumentation stehen, damit niemand den alten Pfad fuer einen
    Ausfall haelt und ihn "reparieren" will.
    """
    return []


async def _fetch_odl_json_alt(client: httpx.AsyncClient) -> list[dict]:
    results = []
    try:
        url = "https://odlinfo.bfs.de/json/stat.json"
        resp = await client.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        for station_id, station_data in data.items():
            if not isinstance(station_data, dict):
                continue

            lat = station_data.get("lat")
            lon = station_data.get("lon")
            if lat is None or lon is None:
                continue
            if not _is_in_region(lat, lon):
                continue

            mw = station_data.get("mw")
            if mw is None:
                continue

            # BfS reports in uSv/h, convert to nSv/h
            gamma_nsv = mw * 1000

            ts = station_data.get("t")
            timestamp = datetime.utcnow()
            if ts:
                try:
                    timestamp = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).replace(tzinfo=None)
                except (ValueError, AttributeError):
                    pass

            results.append({
                "station_id": station_id,
                "station_name": station_data.get("name", station_id),
                "lat": lat,
                "lon": lon,
                "gamma_dose_rate": gamma_nsv,
                "is_elevated": gamma_nsv > ELEVATED_THRESHOLD_NSV,
                "timestamp": timestamp,
                "source": "bfs_odl",
                "raw_data": station_data,
            })
    except Exception as e:
        logger.error(f"Error fetching BfS ODL JSON data: {e}")
    return results


async def _fetch_wfs(client: httpx.AsyncClient) -> list[dict]:
    results = []
    try:
        url = "https://www.imis.bfs.de/ogc/opendata/ows"
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            # WFS 2.0.0 heisst der Parameter typeNames; dieser Server nimmt
            # beide Schreibweisen, die richtige ist belastbarer.
            "typeNames": "opendata:odlinfo_odl_1h_latest",
            "outputFormat": "application/json",
        }
        resp = await client.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        geojson = resp.json()

        for feature in geojson.get("features", []):
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [])

            if len(coords) < 2:
                continue

            lon, lat = coords[0], coords[1]
            if not _is_in_region(lat, lon):
                continue

            mw = props.get("value") or props.get("mw") or props.get("value_cosmic")
            if mw is None:
                continue

            gamma_nsv = float(mw) * 1000

            ts = props.get("end_measure") or props.get("timestamp")
            timestamp = datetime.utcnow()
            if ts:
                try:
                    timestamp = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).replace(tzinfo=None)
                except (ValueError, AttributeError):
                    pass

            sid = props.get("kenn") or props.get("id") or feature.get("id", "")

            results.append({
                "station_id": str(sid),
                "station_name": props.get("name", str(sid)),
                "lat": lat,
                "lon": lon,
                "gamma_dose_rate": gamma_nsv,
                "is_elevated": gamma_nsv > ELEVATED_THRESHOLD_NSV,
                "timestamp": timestamp,
                "source": "bfs_wfs",
                "raw_data": feature,
            })
    except Exception as e:
        logger.error(f"Error fetching BfS WFS data: {e}")
    return results


async def collect_radiation():
    logger.info("Collecting radiation data...")
    results = []

    bundesmittel = None
    # follow_redirects: Der BfS-Kennzahlenpfad leitet weiter, und httpx folgt
    # ohne dieses Flag nicht — der Abruf lief damit still ins Leere.
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # WFS ist die Hauptquelle. Er liefert Stundenwerte je Station,
        # deutschlandweit, und wird hier auf den Umkreis gefiltert.
        results = await _fetch_wfs(client)
        bundesmittel = await fetch_bundesmittel(client)

    if results and bundesmittel:
        hoechster = max(r["gamma_dose_rate"] for r in results)
        if hoechster > bundesmittel * PLAUSIBEL_FAKTOR:
            logger.warning(
                "Radioaktivitaet: hoechster Messwert %.0f nSv/h liegt mehr als "
                "das %.1f-fache ueber dem Bundesmittel (%.0f nSv/h)",
                hoechster, PLAUSIBEL_FAKTOR, bundesmittel)
        for r in results:
            r["raw_data"] = {"feature": r.get("raw_data"),
                             "bundesmittel_nsv": round(bundesmittel, 1)}

    elevated = [r for r in results if r["is_elevated"]]
    if elevated:
        for r in elevated:
            logger.warning(
                f"ELEVATED RADIATION: {r['station_name']} ({r['station_id']}) "
                f"at {r['gamma_dose_rate']:.0f} nSv/h (threshold: {ELEVATED_THRESHOLD_NSV} nSv/h)"
            )

    async with async_session() as session:
        for data in results:
            entry = RadiationReading(**data)
            session.add(entry)
        await session.commit()

    logger.info(f"Collected {len(results)} radiation readings ({len(elevated)} elevated)")
    return results
