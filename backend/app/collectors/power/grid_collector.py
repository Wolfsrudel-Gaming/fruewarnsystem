"""Stromnetz-Status über SMARD (Bundesnetzagentur).

Wichtig zur SMARD-API: Es gibt **keinen** Filter "Erzeugung gesamt". Die
Gesamterzeugung muss aus den einzelnen Erzeugungsarten summiert werden.
Ein früher hier verwendeter Filter (4359) lieferte eine residuallast-artige
Größe, die mit steigender PV-Einspeisung *fällt* — als Erzeugung gelesen
ergab das eine dauerhafte Scheindeckungslücke von ~37 GW und damit
Dauer-Fehlalarme. Deshalb unten die Summenbildung plus Plausibilitätsprüfung.
"""
import asyncio
import logging
from datetime import datetime

import httpx

from app.models.database import async_session
from app.models.schemas import GridStatus

logger = logging.getLogger(__name__)

SMARD_BASE = "https://www.smard.de/app/chart_data"

FILTER_CONSUMPTION = 410  # Stromverbrauch: Netzlast

# Erneuerbare Erzeugung
FILTER_RENEWABLES = {
    1223: "Biomasse",
    4066: "Wasserkraft",
    4067: "Wind Onshore",
    4068: "Photovoltaik",
    4069: "Sonstige Erneuerbare",
    4169: "Wind Offshore",
}

# Konventionelle Erzeugung inkl. Pumpspeicher (Speicher, nicht erneuerbar —
# zaehlt zur Erzeugung, aber nicht in den EE-Anteil)
FILTER_CONVENTIONAL = {
    1224: "Kernenergie",
    1225: "Braunkohle",
    1226: "Steinkohle",
    1227: "Erdgas",
    4070: "Pumpspeicher",
    4071: "Sonstige Konventionelle",
}

RESOLUTION = "hour"
REQUEST_TIMEOUT = 30

# Ab welchem Importanteil an der Netzlast von Netzstress gesprochen wird.
# Deutschland importiert routinemaessig Strom (seit 2023 Nettoimporteur) —
# ein negativer Saldo allein ist daher voellig normal und kein Warnsignal.
IMPORT_SHARE_WARN = 0.15
IMPORT_SHARE_SEVERE = 0.25

# Plausibilitaetsgrenze: Die deutschen Grenzkuppelstellen liegen zusammen bei
# rund 20 GW. Ein groesserer Saldo ist physikalisch unmoeglich und deutet auf
# fehlerhafte Daten hin — dann wird bewusst kein Stress gemeldet.
MAX_PLAUSIBLE_BALANCE_MW = 25000

# Zeitreihen, die mehr als 48h hinter der aktuellsten zurueckliegen, gelten
# als eingestellt (z.B. Kernenergie nach dem Atomausstieg).
STALE_SERIES_TOLERANCE_MS = 48 * 3600 * 1000


async def collect_grid_status():
    logger.info("Collecting grid status from SMARD...")
    results = []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        try:
            all_filters = {
                FILTER_CONSUMPTION: "Netzlast",
                **FILTER_RENEWABLES,
                **FILTER_CONVENTIONAL,
            }

            # Alle Filter parallel holen — jeweils die komplette Zeitreihe,
            # damit anschliessend auf einen gemeinsamen Zeitpunkt ausgerichtet
            # werden kann. Frueher wurde je Filter der letzte verfuegbare Wert
            # genommen; die stammten aus unterschiedlichen Stunden und wurden
            # trotzdem voneinander abgezogen.
            fetched = await asyncio.gather(
                *[_fetch_series(client, fid) for fid in all_filters],
                return_exceptions=True,
            )
            series_by_filter = {}
            for fid, res in zip(all_filters, fetched):
                if isinstance(res, Exception):
                    logger.warning("SMARD-Filter %s fehlgeschlagen: %s", fid, res)
                    continue
                if res:
                    series_by_filter[fid] = res

            aligned, ts_ms = _align_to_common_timestamp(series_by_filter)
            if not aligned or FILTER_CONSUMPTION not in aligned:
                logger.warning("Keine zeitlich konsistenten SMARD-Daten verfuegbar")
                return results

            consumption_mw = aligned[FILTER_CONSUMPTION]

            renewable_parts = {
                name: aligned[fid]
                for fid, name in FILTER_RENEWABLES.items() if fid in aligned
            }
            conventional_parts = {
                name: aligned[fid]
                for fid, name in FILTER_CONVENTIONAL.items() if fid in aligned
            }

            if not renewable_parts and not conventional_parts:
                logger.warning("Keine Erzeugungsdaten von SMARD erhalten")
                return results

            renewable_mw = sum(renewable_parts.values())
            # SMARD kennt keinen Gesamterzeugungs-Filter — Summe der Einzelarten
            generation_mw = renewable_mw + sum(conventional_parts.values())

            renewable_share = None
            if generation_mw > 0:
                renewable_share = round(min(1.0, renewable_mw / generation_mw), 3)

            balance_mw = generation_mw - consumption_mw
            measured_at = datetime.utcfromtimestamp(ts_ms / 1000) if ts_ms else datetime.utcnow()

            is_stressed, stress_indicator = _assess_stress(
                balance_mw, consumption_mw, generation_mw
            )
            if is_stressed:
                logger.warning("Grid stress detected: %s", stress_indicator)

            results.append({
                "region": "DE",
                "generation_mw": round(generation_mw, 1),
                "consumption_mw": round(consumption_mw, 1),
                "balance_mw": round(balance_mw, 1),
                "renewable_share": renewable_share,
                "is_stressed": is_stressed,
                "stress_indicator": stress_indicator,
                "timestamp": measured_at,
                "source": "smard_bundesnetzagentur",
                "raw_data": {
                    "generation_mw": round(generation_mw, 1),
                    "consumption_mw": round(consumption_mw, 1),
                    "balance_mw": round(balance_mw, 1),
                    "renewable_mw": round(renewable_mw, 1),
                    "renewable_parts": renewable_parts,
                    "conventional_parts": conventional_parts,
                    "import_share": round(max(0.0, -balance_mw) / consumption_mw, 4)
                    if consumption_mw > 0 else None,
                    "resolution": RESOLUTION,
                    "measured_at": measured_at.isoformat(),
                },
            })
        except Exception as e:
            logger.error("Error collecting grid status: %s", e, exc_info=True)

    async with async_session() as session:
        for data in results:
            session.add(GridStatus(**data))
        await session.commit()

    logger.info("Collected %s grid status readings", len(results))
    return results


def _assess_stress(balance_mw: float, consumption_mw: float, generation_mw: float):
    """Bewertet, ob echte Netzanspannung vorliegt.

    Ein Importsaldo ist im europaeischen Verbundnetz Normalbetrieb. Gewarnt
    wird erst, wenn der Import einen erheblichen Anteil der Netzlast ausmacht.
    """
    if consumption_mw <= 0:
        return False, None

    # Datenfehler duerfen nie zu Dauer-Alarmen fuehren
    if abs(balance_mw) > MAX_PLAUSIBLE_BALANCE_MW:
        logger.error(
            "SMARD-Werte unplausibel (Saldo %.0f MW bei Last %.0f MW, Erzeugung %.0f MW) "
            "— kein Netzstress gemeldet, Datenquelle pruefen",
            balance_mw, consumption_mw, generation_mw,
        )
        return False, None

    if balance_mw >= 0:
        return False, None

    import_share = -balance_mw / consumption_mw
    if import_share < IMPORT_SHARE_WARN:
        return False, None

    level = "hoher" if import_share >= IMPORT_SHARE_SEVERE else "erhoehter"
    return True, (
        f"{level} Importbedarf: {abs(balance_mw):.0f} MW "
        f"({import_share * 100:.0f}% der Netzlast)"
    )


def _align_to_common_timestamp(series_by_filter: dict):
    """Waehlt den neuesten Zeitpunkt, zu dem alle *aktiven* Filter Werte haben.

    SMARD veroeffentlicht die Zeitreihen unterschiedlich schnell; ohne diese
    Ausrichtung werden Werte aus verschiedenen Stunden miteinander verrechnet.

    Eingestellte Zeitreihen werden dabei uebersprungen: Kernenergie etwa
    endet mit dem Atomausstieg. Wuerde man sie in den Schnitt einbeziehen,
    gaebe es keinen gemeinsamen Zeitpunkt mehr und der Collector lieferte
    dauerhaft nichts. Solche Reihen tragen 0 MW bei — was fachlich stimmt.
    """
    if not series_by_filter:
        return {}, None

    newest_overall = max(max(v.keys()) for v in series_by_filter.values() if v)

    active, retired = {}, []
    for fid, values in series_by_filter.items():
        if not values:
            continue
        if newest_overall - max(values.keys()) > STALE_SERIES_TOLERANCE_MS:
            retired.append(fid)
            continue
        active[fid] = values

    if retired:
        logger.info("SMARD-Zeitreihen ohne aktuelle Daten (zaehlen als 0 MW): %s", retired)

    common = None
    for values in active.values():
        keys = set(values.keys())
        common = keys if common is None else (common & keys)

    if not common:
        logger.warning("Kein gemeinsamer Zeitpunkt ueber die aktiven SMARD-Reihen")
        return {}, None

    newest = max(common)
    return {fid: values[newest] for fid, values in active.items()}, newest


async def _fetch_series(client: httpx.AsyncClient, filter_id: int) -> dict:
    """Liefert {timestamp_ms: wert} der letzten verfuegbaren SMARD-Bloecke."""
    result = {}
    try:
        index_url = f"{SMARD_BASE}/{filter_id}/DE/index_{RESOLUTION}.json"
        resp = await client.get(index_url)
        resp.raise_for_status()
        timestamps = resp.json().get("timestamps", [])
        if not timestamps:
            return result

        for ts in reversed(timestamps[-2:]):
            data_url = f"{SMARD_BASE}/{filter_id}/DE/{filter_id}_DE_{RESOLUTION}_{ts}.json"
            resp = await client.get(data_url)
            if resp.status_code != 200:
                continue
            for entry in resp.json().get("series", []):
                if isinstance(entry, list) and len(entry) >= 2 and entry[1] is not None:
                    result[entry[0]] = float(entry[1])
            if result:
                break
    except Exception as e:
        logger.error("Error fetching SMARD data for filter %s: %s", filter_id, e)
    return result
