import logging
from datetime import datetime
from typing import Optional

import httpx

from app.config import settings
from app.models.database import async_session
from app.models.schemas import WaterLevel

logger = logging.getLogger(__name__)

PEGELONLINE_BASE = "https://www.pegelonline.wsv.de/webservices/rest-api/v2"

# PEGELONLINE ist das Netz der Wasser- und Schifffahrtsverwaltung und deckt
# ausschliesslich BUNDESWASSERSTRASSEN ab. Am 25.11.2026 geprueft: Von den
# 102 dort gefuehrten Gewaessern sind Sieg und Agger KEINES. Die beiden
# Eintraege "SIEGBURG" und "TROISDORF" standen mit uuid=None in dieser Liste
# und suchten nach einem Pegel, den es dort nicht gibt — der Abruf gab still
# None zurueck, und die beiden Fluesse, die durch Troisdorf laufen, hatten
# damit gar keinen Pegel.
#
# Sieg und Agger liegen bei OpenHygon (LANUV NRW) und werden vom
# hochwasser_collector abgerufen: Menden, Siegburg Kaldenhausen, Lohmar und
# Eitorf, jeweils mit den amtlichen Meldestufen.
STATIONS = {
    "KOELN": {"uuid": "a6ee8177-107b-47dd-bcfd-30960ccc6e9c", "river": "Rhein"},
    "BONN": {"uuid": "593647aa-9fea-43ec-a7d6-6476a76ae868", "river": "Rhein"},
}

RIVER_THRESHOLDS = {
    "rhein": {
        "low_extreme": 80,   # Schifffahrt eingestellt
        "low_warning": 150,  # Niedrigwasser-Warnung
        "low_normal": 200,   # Unterer Normalbereich
        "high_normal": 600,  # Oberer Normalbereich
        "high_warning": 700, # Hochwasser-Warnung
        "high_extreme": 850, # Extremhochwasser
    },
    "sieg": {
        "low_extreme": 15,
        "low_warning": 30,
        "low_normal": 50,
        "high_normal": 300,
        "high_warning": 400,
        "high_extreme": 500,
    },
    "agger": {
        "low_extreme": 10,
        "low_warning": 20,
        "low_normal": 35,
        "high_normal": 200,
        "high_warning": 280,
        "high_extreme": 350,
    },
    "pleisbach": {
        "low_extreme": 5,
        "low_warning": 10,
        "low_normal": 20,
        "high_normal": 100,
        "high_warning": 150,
        "high_extreme": 200,
    },
    "swistbach": {
        "low_extreme": 5,
        "low_warning": 10,
        "low_normal": 20,
        "high_normal": 80,
        "high_warning": 120,
        "high_extreme": 160,
    },
}

LANUV_BASE = "https://luadb.it.nrw.de/LUA/hygon/pegel.php"


async def fetch_pegelonline_station(client: httpx.AsyncClient, station_id: str, station_info: dict) -> Optional[dict]:
    try:
        if station_info.get("uuid"):
            # Die vollstaendige Station statt nur des Messwerts: nur so kommen
            # die amtlichen Kennwerte (GlW, M_I, MHW ...) mit, nach denen die
            # Einstufung sich richtet.
            return await _station_mit_kennwerten(
                client, station_id, station_info)
        else:
            url = f"{PEGELONLINE_BASE}/stations.json?waters={station_info['river']}&includeCurrentMeasurement=true"

        resp = await client.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, list):
            for s in data:
                if station_info.get("search", "").lower() in s.get("longname", "").lower():
                    cm = s.get("currentMeasurement", {})
                    return {
                        "station_id": station_id,
                        "station_name": s.get("longname", station_id),
                        "river": station_info["river"],
                        "level_cm": cm.get("value"),
                        "trend": _parse_trend(cm.get("trend")),
                        "timestamp": _parse_timestamp(cm.get("timestamp")),
                        "source": "pegelonline",
                        "raw_data": s,
                    }
            return None

        return {
            "station_id": station_id,
            "station_name": station_id,
            "river": station_info["river"],
            "level_cm": data.get("value"),
            "trend": _parse_trend(data.get("trend")),
            "timestamp": _parse_timestamp(data.get("timestamp")),
            "source": "pegelonline",
            "raw_data": data,
        }
    except Exception as e:
        logger.error(f"Error fetching pegel for {station_id}: {e}")
        return None


async def _station_mit_kennwerten(client: httpx.AsyncClient, station_id: str,
                                  station_info: dict) -> Optional[dict]:
    """Messwert UND amtliche Kennwerte einer PEGELONLINE-Station."""
    url = f"{PEGELONLINE_BASE}/stations/{station_info['uuid']}.json"
    resp = await client.get(
        url,
        params={"includeTimeseries": "true",
                "includeCurrentMeasurement": "true",
                "includeCharacteristicValues": "true"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    reihe = next((t for t in data.get("timeseries", [])
                  if t.get("shortname") == "W"), None)
    if not reihe:
        return None
    messung = reihe.get("currentMeasurement") or {}
    kennwerte = {k.get("shortname"): k.get("value")
                 for k in reihe.get("characteristicValues", [])
                 if k.get("shortname")}

    return {
        "station_id": station_id,
        "station_name": data.get("longname", station_id),
        "river": station_info["river"],
        "level_cm": messung.get("value"),
        "trend": _parse_trend(messung.get("trend")),
        "timestamp": _parse_timestamp(messung.get("timestamp")),
        "source": "pegelonline",
        "kennwerte": kennwerte,
        "raw_data": {"station": data.get("longname"),
                     "kennwerte": kennwerte, "current": messung},
    }


def _parse_trend(trend_val) -> str:
    if trend_val is None:
        return "unknown"
    if isinstance(trend_val, (int, float)):
        if trend_val > 0:
            return "rising"
        elif trend_val < 0:
            return "falling"
        return "stable"
    return str(trend_val).lower()


def _parse_timestamp(ts_str) -> datetime:
    if not ts_str:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return datetime.utcnow()


# --- Amtliche Bezugswerte statt geschaetzter Schwellen ---
#
# RIVER_THRESHOLDS oben ist eine Schaetzung JE FLUSS. Das ist zweifach falsch:
# Erstens hat jeder Pegel seinen eigenen Pegelnullpunkt — Bonn und Koeln
# liegen beide am Rhein, aber Bonn hat MHW 680 cm und Koeln 725 cm. Eine
# gemeinsame Schwelle von 700 cm ist fuer den einen zu hoch, fuer den anderen
# zu niedrig. Zweitens bewerteten Pegel, Schifffahrt und Hochwasser dieselbe
# Zahl nach drei verschiedenen Maßstaeben und widersprachen sich dadurch.
#
# Die amtlichen Werte liegen vor und werden ohnehin schon abgerufen:
#   Rhein (PEGELONLINE characteristicValues)
#     NNW  niedrigster bekannter Wasserstand
#     MNW  mittlerer Niedrigwasserstand
#     GlW  Gleichwertiger Wasserstand — darunter wird die Schifffahrt knapp
#     M_I  Hochwassermarke I — Geschwindigkeitsbeschraenkung
#     MHW  mittlerer Hochwasserstand
#     M_II / HSW  Hochwassermarke II — Schifffahrt wird eingestellt
#   Sieg und Agger (OpenHygon/LANUV, siehe hochwasser_collector)
#     LANUV_MNW, LANUV_MHW und die Meldestufen Info_1, Info_2, Info_3
#
# Namensgleiche Werte werden hier auf ein gemeinsames Schema gebracht. Nur
# wenn nichts Amtliches vorliegt, greift die Schaetzung aus RIVER_THRESHOLDS.

# Welche amtlichen Werte auf welche Schwelle passen, in der Reihenfolge, in
# der sie bevorzugt werden.
_AMTLICH = {
    "low_extreme":  ("NNW", "LANUV_NNW"),
    "low_warning":  ("MNW", "LANUV_MNW"),
    "low_normal":   ("GlW", "TuGLW", "LANUV_MW"),
    "high_normal":  ("Info_1", "LANUV_Info_1", "M_I"),
    "high_warning": ("Info_2", "LANUV_Info_2", "MHW", "LANUV_MHW"),
    "high_extreme": ("Info_3", "LANUV_Info_3", "M_II", "HSW", "HHW"),
}

SCHWELLEN_REIHENFOLGE = ("low_extreme", "low_warning", "low_normal",
                         "high_normal", "high_warning", "high_extreme")


def schwellen_aus_kennwerten(kennwerte: Optional[dict]) -> Optional[dict]:
    """Amtliche Schwellen aus den Kennwerten einer Station ableiten.

    Gibt None zurueck, wenn nicht alle Schwellen belegt sind oder sie nicht
    streng aufsteigen. Lieber die bekannte Schaetzung als eine amtlich
    aussehende, aber unsinnige Reihe — eine Schwelle, die unter der
    darunterliegenden steht, wuerde Stufen ueberspringen.

    Reine Funktion, damit sie ohne Netz pruefbar ist.
    """
    if not kennwerte:
        return None

    abgeleitet = {}
    for schwelle, namen in _AMTLICH.items():
        for name in namen:
            wert = kennwerte.get(name)
            if wert is None:
                continue
            try:
                abgeleitet[schwelle] = float(wert)
            except (TypeError, ValueError):
                continue
            break

    # Nicht jeder Pegel veroeffentlicht Hochwassermarken. Bonn etwa liefert
    # MHW und HHW, aber kein M_I/M_II. Dann die obere Haelfte aus den eigenen
    # Werten der Station spannen: ueber dem mittleren Hochwasserstand ist es
    # nicht mehr normal, der hoechste bekannte Stand ist die Obergrenze.
    # Das ist eine Ableitung, keine amtliche Marke — und wird als solche
    # ausgewiesen.
    if "high_normal" not in abgeleitet:
        mhw = _zahl(kennwerte.get("MHW") or kennwerte.get("LANUV_MHW"))
        hhw = _zahl(kennwerte.get("HHW") or kennwerte.get("LANUV_HHW"))
        if mhw is not None and hhw is not None and hhw > mhw:
            spanne = hhw - mhw
            abgeleitet["high_normal"] = mhw
            abgeleitet["high_warning"] = mhw + spanne * 0.33
            abgeleitet["high_extreme"] = mhw + spanne * 0.66
            abgeleitet["_abgeleitet_oben"] = True

    if any(k not in abgeleitet for k in _AMTLICH):
        return None

    werte = [abgeleitet[s] for s in SCHWELLEN_REIHENFOLGE]
    if any(a >= b for a, b in zip(werte, werte[1:])):
        return None
    return abgeleitet


def _zahl(wert):
    try:
        return float(wert)
    except (TypeError, ValueError):
        return None


def classify_water_level(level_cm: Optional[float], river: str,
                         kennwerte: Optional[dict] = None) -> dict:
    if level_cm is None:
        return {"warning_level": "unknown", "condition": "no_data",
                "deviation": 0, "basis": "keine Daten"}

    thresholds = schwellen_aus_kennwerten(kennwerte)
    if thresholds and thresholds.get("_abgeleitet_oben"):
        basis = ("amtliche Pegelkennwerte; Hochwasserstufen aus MHW/HHW "
                 "dieser Station abgeleitet")
    else:
        basis = "amtliche Pegelkennwerte"

    if not thresholds:
        basis = "geschaetzte Flussschwellen (keine amtlichen Kennwerte)"
        river_key = river.lower()
        for key in RIVER_THRESHOLDS:
            if key in river_key:
                thresholds = RIVER_THRESHOLDS[key]
                break

    if not thresholds:
        thresholds = RIVER_THRESHOLDS.get("sieg")

    if level_cm <= thresholds["low_extreme"]:
        return {"warning_level": "extreme_low", "condition": "drought", "deviation": (thresholds["low_extreme"] - level_cm) / thresholds["low_normal"], "basis": basis}
    elif level_cm <= thresholds["low_warning"]:
        return {"warning_level": "low", "condition": "niedrigwasser", "deviation": (thresholds["low_warning"] - level_cm) / thresholds["low_normal"], "basis": basis}
    elif level_cm <= thresholds["low_normal"]:
        return {"warning_level": "below_normal", "condition": "unterdurchschnittlich", "deviation": 0, "basis": basis}
    elif level_cm <= thresholds["high_normal"]:
        return {"warning_level": "normal", "condition": "normal", "deviation": 0, "basis": basis}
    elif level_cm <= thresholds["high_warning"]:
        return {"warning_level": "high", "condition": "hochwasser", "deviation": (level_cm - thresholds["high_normal"]) / thresholds["high_normal"], "basis": basis}
    elif level_cm <= thresholds["high_extreme"]:
        return {"warning_level": "very_high", "condition": "starkes_hochwasser", "deviation": (level_cm - thresholds["high_normal"]) / thresholds["high_normal"], "basis": basis}
    else:
        return {"warning_level": "extreme_high", "condition": "extremhochwasser", "deviation": (level_cm - thresholds["high_normal"]) / thresholds["high_normal"], "basis": basis}


async def collect_water_levels():
    logger.info("Collecting water levels...")
    results = []

    async with httpx.AsyncClient() as client:
        for station_id, station_info in STATIONS.items():
            data = await fetch_pegelonline_station(client, station_id, station_info)
            if data:
                classification = classify_water_level(
                    data.get("level_cm"), data.get("river", ""),
                    kennwerte=data.get("kennwerte"))
                data["classification"] = classification
                if classification["condition"] in ("drought", "niedrigwasser"):
                    logger.warning(
                        f"NIEDRIGWASSER: {data['station_name']} ({data['river']}) "
                        f"bei {data['level_cm']} cm - {classification['condition']}"
                    )
                results.append(data)

        try:
            all_stations_url = f"{PEGELONLINE_BASE}/stations.json?includeCurrentMeasurement=true"
            resp = await client.get(all_stations_url, timeout=30)
            resp.raise_for_status()
            all_stations = resp.json()

            rhein_sieg_rivers = ["sieg", "agger", "pleisbach", "swistbach"]
            for station in all_stations:
                water = station.get("water", {}).get("longname", "").lower()
                if water in rhein_sieg_rivers:
                    existing = [r for r in results if r["station_id"] == station.get("shortname")]
                    if not existing:
                        cm = station.get("currentMeasurement", {})
                        if cm:
                            level_val = cm.get("value")
                            river_name = water.title()
                            classification = classify_water_level(level_val, river_name)
                            entry = {
                                "station_id": station.get("shortname", "UNKNOWN"),
                                "station_name": station.get("longname", ""),
                                "river": river_name,
                                "level_cm": level_val,
                                "trend": _parse_trend(cm.get("trend")),
                                "timestamp": _parse_timestamp(cm.get("timestamp")),
                                "source": "pegelonline",
                                "raw_data": station,
                                "classification": classification,
                            }
                            if classification["condition"] in ("drought", "niedrigwasser"):
                                logger.warning(
                                    f"NIEDRIGWASSER: {entry['station_name']} ({river_name}) "
                                    f"bei {level_val} cm - {classification['condition']}"
                                )
                            results.append(entry)
        except Exception as e:
            logger.warning(f"Error fetching additional stations: {e}")

    async with async_session() as session:
        for data in results:
            entry = WaterLevel(**data)
            session.add(entry)
        await session.commit()

    logger.info(f"Collected {len(results)} water level readings")
    return results
