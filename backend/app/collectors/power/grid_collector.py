"""Stromnetz-Daten über SMARD (Bundesnetzagentur).

Alle Filter-IDs unten sind empirisch gegen die Live-API verifiziert. Zwei
Fallstricke, die hier schon Fehler verursacht haben:

  * Es gibt **keinen** Filter "Erzeugung gesamt". Die Gesamterzeugung muss
    aus den Einzelarten summiert werden. Filter 4359 liefert eine
    residuallast-artige Groesse, die mit steigender PV-Einspeisung faellt —
    als Erzeugung gelesen ergab das eine Scheindeckungsluecke von ~37 GW.
  * Filter 4169 ist **kein** Wind Offshore, sondern eine Preiszeitreihe
    (EUR/MWh, laeuft im Gleichlauf mit 252). Wind Offshore ist 124.
    Als Erzeugung summiert fehlten bis zu 5 GW Offshore-Leistung, dafuer
    floss ein Boersenpreis in die Bilanz ein.

Verifiziert: Summe der Einzelarten (72,4 GW) deckt sich mit der
SMARD-Gesamtprognose Filter 122 (73,9 GW).
"""
import asyncio
import logging
from datetime import datetime

import httpx

from app.models.database import async_session
from app.models.schemas import GridStatus

logger = logging.getLogger(__name__)

SMARD_BASE = "https://www.smard.de/app/chart_data"
RESOLUTION = "hour"
REQUEST_TIMEOUT = 30

# --- Realisierte Erzeugung (MW), alle verifiziert ---
FILTER_GENERATION = {
    1223: "Biomasse",
    1225: "Braunkohle",
    1226: "Steinkohle",
    1227: "Erdgas",
    4066: "Wasserkraft",
    4067: "Wind Onshore",
    124: "Wind Offshore",
    4068: "Photovoltaik",
    4069: "Sonstige Erneuerbare",
    4070: "Pumpspeicher",
    4071: "Sonstige Konventionelle",
    1224: "Kernenergie",  # seit Atomausstieg ohne neue Werte
}

# Erneuerbar im engeren Sinn — Pumpspeicher ist Speicher, kein EE-Erzeuger
RENEWABLE_IDS = {1223, 4066, 4067, 124, 4068, 4069}

FILTER_CONSUMPTION = 410      # Stromverbrauch: Netzlast
FILTER_FORECAST_TOTAL = 122   # Prognostizierte Erzeugung: Gesamt
FILTER_PRICE = 252            # Grosshandelspreis Deutschland/Luxemburg (EUR/MWh)

# Regelzonen. Troisdorf liegt im Amprion-Gebiet — die regionale Last ist
# fuer die Lagebewertung aussagekraeftiger als der Bundeswert.
REGIONS = {
    "DE": "Deutschland",
    "Amprion": "Regelzone Amprion (Rhein-Sieg)",
}

# Ab welchem Importanteil an der Netzlast von Netzstress gesprochen wird.
# Deutschland importiert routinemaessig Strom (seit 2023 Nettoimporteur) —
# ein negativer Saldo allein ist kein Warnsignal.
IMPORT_SHARE_WARN = 0.15
IMPORT_SHARE_SEVERE = 0.25

# Die deutschen Grenzkuppelstellen liegen zusammen bei rund 20 GW. Groessere
# Saldi sind physikalisch unmoeglich und deuten auf fehlerhafte Daten hin.
MAX_PLAUSIBLE_BALANCE_MW = 25000

# Zeitreihen, die mehr als 48h hinter der aktuellsten zurueckliegen, gelten
# als eingestellt (z.B. Kernenergie nach dem Atomausstieg).
STALE_SERIES_TOLERANCE_MS = 48 * 3600 * 1000


async def collect_grid_status():
    logger.info("Collecting grid status from SMARD...")
    results = []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        for region, region_label in REGIONS.items():
            try:
                entry = await _collect_region(client, region, region_label)
                if entry:
                    results.append(entry)
            except Exception as e:
                logger.error("Region %s fehlgeschlagen: %s", region, e, exc_info=True)

    async with async_session() as session:
        for data in results:
            session.add(GridStatus(**data))
        await session.commit()

    logger.info("Collected %s grid status readings", len(results))
    return results


async def _collect_region(client: httpx.AsyncClient, region: str, region_label: str):
    core_filters = [FILTER_CONSUMPTION, *FILTER_GENERATION]
    extra_filters = [FILTER_FORECAST_TOTAL, FILTER_PRICE]

    fetched = await asyncio.gather(
        *[_fetch_series(client, fid, region) for fid in core_filters + extra_filters],
        return_exceptions=True,
    )
    series_by_filter = {}
    for fid, res in zip(core_filters + extra_filters, fetched):
        if isinstance(res, Exception):
            logger.warning("SMARD-Filter %s (%s) fehlgeschlagen: %s", fid, region, res)
            continue
        if res:
            series_by_filter[fid] = res

    # Preis und Prognose nicht in die Ausrichtung zwingen — sie haben eigene
    # Veroeffentlichungsrhythmen und wuerden den gemeinsamen Zeitpunkt
    # unnoetig nach hinten ziehen.
    core_series = {f: s for f, s in series_by_filter.items() if f in core_filters}
    aligned, ts_ms = _align_to_common_timestamp(core_series)

    if not aligned or FILTER_CONSUMPTION not in aligned:
        logger.warning("Keine zeitlich konsistenten SMARD-Daten fuer %s", region)
        return None

    consumption_mw = aligned[FILTER_CONSUMPTION]

    generation_parts = {
        FILTER_GENERATION[fid]: round(aligned[fid], 1)
        for fid in FILTER_GENERATION if fid in aligned
    }
    if not generation_parts:
        logger.warning("Keine Erzeugungsdaten fuer %s", region)
        return None

    renewable_mw = sum(aligned[fid] for fid in RENEWABLE_IDS if fid in aligned)
    generation_mw = sum(aligned[fid] for fid in FILTER_GENERATION if fid in aligned)

    renewable_share = None
    if generation_mw > 0:
        renewable_share = round(min(1.0, renewable_mw / generation_mw), 3)

    balance_mw = generation_mw - consumption_mw
    measured_at = datetime.utcfromtimestamp(ts_ms / 1000)

    # Preis/Prognose zum selben Zeitpunkt, sonst letzter Wert davor
    price = _value_at_or_before(series_by_filter.get(FILTER_PRICE), ts_ms)
    forecast_total = _value_at_or_before(series_by_filter.get(FILTER_FORECAST_TOTAL), ts_ms)

    # Netzstress wird nur bundesweit bewertet: eine Regelzone allein hat keine
    # eigene Bilanz, ihr Saldo sagt nichts ueber Versorgungssicherheit aus.
    if region == "DE":
        is_stressed, stress_indicator = _assess_stress(
            balance_mw, consumption_mw, generation_mw
        )
        if is_stressed:
            logger.warning("Grid stress detected: %s", stress_indicator)
    else:
        is_stressed, stress_indicator = False, None

    renewable_parts = {
        FILTER_GENERATION[fid]: round(aligned[fid], 1)
        for fid in RENEWABLE_IDS if fid in aligned
    }
    conventional_parts = {
        name: val for name, val in generation_parts.items()
        if name not in renewable_parts
    }

    return {
        "region": region,
        "generation_mw": round(generation_mw, 1),
        "consumption_mw": round(consumption_mw, 1),
        "balance_mw": round(balance_mw, 1),
        "renewable_share": renewable_share,
        "price_eur_mwh": round(price, 2) if price is not None else None,
        "is_stressed": is_stressed,
        "stress_indicator": stress_indicator,
        "timestamp": measured_at,
        "source": "smard_bundesnetzagentur",
        "raw_data": {
            "region_label": region_label,
            "measured_at": measured_at.isoformat(),
            "resolution": RESOLUTION,
            "generation_parts": generation_parts,
            "renewable_parts": renewable_parts,
            "conventional_parts": conventional_parts,
            "renewable_mw": round(renewable_mw, 1),
            "generation_mw": round(generation_mw, 1),
            "consumption_mw": round(consumption_mw, 1),
            "balance_mw": round(balance_mw, 1),
            "forecast_total_mw": round(forecast_total, 1) if forecast_total is not None else None,
            "price_eur_mwh": round(price, 2) if price is not None else None,
            "import_share": round(max(0.0, -balance_mw) / consumption_mw, 4)
            if consumption_mw > 0 else None,
        },
    }


def _value_at_or_before(series: dict, ts_ms: int):
    """Wert zum Zeitpunkt, sonst der juengste davor."""
    if not series:
        return None
    if ts_ms in series:
        return series[ts_ms]
    earlier = [t for t in series if t <= ts_ms]
    return series[max(earlier)] if earlier else None


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

    Eingestellte Zeitreihen werden uebersprungen: Kernenergie etwa endet mit
    dem Atomausstieg. Wuerde man sie in den Schnitt einbeziehen, gaebe es
    keinen gemeinsamen Zeitpunkt mehr und der Collector lieferte dauerhaft
    nichts. Solche Reihen tragen 0 MW bei — was fachlich stimmt.
    """
    if not series_by_filter:
        return {}, None

    populated = {f: v for f, v in series_by_filter.items() if v}
    if not populated:
        return {}, None

    newest_overall = max(max(v.keys()) for v in populated.values())

    active, retired = {}, []
    for fid, values in populated.items():
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


async def _fetch_series(client: httpx.AsyncClient, filter_id: int, region: str = "DE") -> dict:
    """Liefert {timestamp_ms: wert} der letzten verfuegbaren SMARD-Bloecke."""
    result = {}
    try:
        index_url = f"{SMARD_BASE}/{filter_id}/{region}/index_{RESOLUTION}.json"
        resp = await client.get(index_url)
        if resp.status_code == 404:
            # Normalfall: nicht jede Erzeugungsart existiert in jeder
            # Regelzone (z.B. keine Braunkohle bei Amprion).
            logger.debug("Filter %s in Region %s nicht vorhanden", filter_id, region)
            return result
        resp.raise_for_status()
        timestamps = resp.json().get("timestamps", [])
        if not timestamps:
            return result

        for ts in reversed(timestamps[-2:]):
            data_url = f"{SMARD_BASE}/{filter_id}/{region}/{filter_id}_{region}_{RESOLUTION}_{ts}.json"
            resp = await client.get(data_url)
            if resp.status_code != 200:
                continue
            for entry in resp.json().get("series", []):
                if isinstance(entry, list) and len(entry) >= 2 and entry[1] is not None:
                    result[entry[0]] = float(entry[1])
            if result:
                break
    except Exception as e:
        logger.error("Error fetching SMARD data for filter %s/%s: %s", filter_id, region, e)
    return result
