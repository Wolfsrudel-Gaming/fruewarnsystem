"""Konkrete Stromausfälle über die Störungsauskunft der Netzbetreiber.

Warum diese Quelle: Die SMARD-Daten zeigen die bundesweite Erzeugungsbilanz
und sagen nichts darüber aus, ob in Troisdorf der Strom weg ist. Die
Störungsauskunft dagegen sammelt die Ausfallmeldungen der Verteilnetz-
betreiber selbst — die Stadtwerke Troisdorf verweisen für ihr Netzgebiet
ausdrücklich auf dieses Portal.

Zwei Endpunkte mit unterschiedlicher Verlässlichkeit:

  * ``outages``          — vom Netzbetreiber bestätigte Störungen. Belastbar,
                           kommen aber erst, wenn der Betreiber sie erfasst hat.
  * ``usernotification`` — Bürgermeldungen. Früher da, einzeln jedoch wertlos
                           (eine Meldung kann eine Hausssicherung sein). Erst
                           mehrere Meldungen dicht beieinander sind ein Signal.

Hinweis zur Schnittstelle: Es ist die öffentliche API, die auch die Website
selbst im Browser nutzt (Basic-Auth ``frontend:frontend`` ist eine offene
Frontend-Kennung, kein Geheimnis). Sie ist nicht offiziell dokumentiert.
Deshalb: konservatives Abfrageintervall, sprechender User-Agent und ein
Betrieb, der einen Ausfall der Quelle unbeschadet übersteht. Für den
Dauerbetrieb empfiehlt sich, den Betreiber um eine offizielle Freigabe zu
bitten.
"""
import base64
import logging
import math
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select

from app.config import settings
from app.models.database import async_session
from app.models.schemas import PowerOutage

logger = logging.getLogger(__name__)

API_BASE = "https://api-public.stoerungsauskunft.de/api/v1/public"
SECTOR_ELECTRICITY = 1

_AUTH = "Basic " + base64.b64encode(b"frontend:frontend").decode()
HEADERS = {
    "Authorization": _AUTH,
    "Accept": "application/json",
    "User-Agent": "DRK-Troisdorf-Fruehwarnsystem/1.0 (Katastrophenschutz)",
}

REQUEST_TIMEOUT = 30

# --- Zwei Relevanzzonen ------------------------------------------------------
# Kernbereich ist der Rhein-Sieg-Kreis samt Troisdorf: dort ist jeder Ausfall
# einsatzrelevant. Ausserhalb interessiert nur noch ein Grossereignis — ein
# einzelner Trafoschaden zwei Kreise weiter ist reines Rauschen.

TROISDORF_PLZ = {"53840", "53842", "53844"}

# Die 19 Kommunen des Rhein-Sieg-Kreises. Bewusst als Liste statt als Radius:
# der Kreis reicht im Osten (Windeck) deutlich weiter als im Westen.
RHEIN_SIEG_PLZ = {
    "53347",  # Alfter
    "53604",  # Bad Honnef
    "53332",  # Bornheim
    "53783",  # Eitorf
    "53773",  # Hennef (Sieg)
    "53639",  # Koenigswinter
    "53797",  # Lohmar
    "53340",  # Meckenheim
    "53804",  # Much
    "53819",  # Neunkirchen-Seelscheid
    "53859",  # Niederkassel
    "53359",  # Rheinbach
    "53809",  # Ruppichteroth
    "53757",  # Sankt Augustin
    "53721",  # Siegburg
    "53913",  # Swisttal
    "53343",  # Wachtberg
    "51570",  # Windeck
    *TROISDORF_PLZ,
}
CORE_PLZ = RHEIN_SIEG_PLZ

# Nur wenn eine Meldung gar keine PLZ mitbringt, entscheidet die Entfernung.
CORE_FALLBACK_RADIUS_KM = 12.0

# Umkreis, in dem ueberhaupt nach Grossereignissen geschaut wird
WIDE_RADIUS_KM = 150.0

# Buergermeldungen werden geclustert: mehrere Meldungen innerhalb dieses
# Radius gelten als ein Ereignis.
CLUSTER_RADIUS_KM = 3.0

# Im Kernbereich reichen wenige Meldungen fuer einen Hinweis
MIN_CLUSTER_REPORTS = 3

# Ausserhalb wird grossflaechig gebuendelt — ein Flaechenausfall verteilt sich
# ueber ganze Staedte.
WIDE_CLUSTER_RADIUS_KM = 25.0

# Untergrenze, ab der ein Ereignis ausserhalb ueberhaupt erfasst wird
LARGE_SCALE_MIN_REPORTS = 100

# Ab hier gilt es als deutliches Grossereignis
LARGE_SCALE_CLEAR_REPORTS = 500

# Datumsformat der API: MM/DD/YYYY HH:MM:SS
_DATE_FMT = "%m/%d/%Y %H:%M:%S"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


def parse_coordinates(raw) -> tuple:
    """Koordinaten aus dem API-Feld lesen.

    Die beiden Endpunkte nutzen unterschiedliche Trennzeichen — bestätigte
    Störungen ``"9.27,48.59"``, Bürgermeldungen ``"6.86;51.41"`` — jeweils in
    der Reihenfolge Länge,Breite.
    """
    if not raw or not isinstance(raw, str):
        return (None, None)
    sep = ";" if ";" in raw else ","
    parts = raw.split(sep)
    if len(parts) < 2:
        return (None, None)
    try:
        lon, lat = float(parts[0]), float(parts[1])
    except (TypeError, ValueError):
        return (None, None)
    # Grobe Plausibilitaet fuer Mitteleuropa
    if not (45 <= lat <= 56 and 4 <= lon <= 17):
        return (None, None)
    return (lat, lon)


def parse_api_date(raw):
    if not raw or not isinstance(raw, str):
        return None
    try:
        return datetime.strptime(raw, _DATE_FMT)
    except ValueError:
        return None


def cluster_reports(reports: list) -> list:
    """Bürgermeldungen räumlich bündeln.

    Eine einzelne Meldung sagt wenig — mehrere dicht beieinander sind ein
    belastbarer Hinweis auf einen echten Ausfall.
    """
    clusters = []
    for rep in sorted(reports, key=lambda r: r["distance_km"]):
        placed = False
        for cl in clusters:
            if _haversine_km(cl["lat"], cl["lon"], rep["lat"], rep["lon"]) <= CLUSTER_RADIUS_KM:
                cl["members"].append(rep)
                # Zentrum bleibt die naechstgelegene Meldung, damit die
                # Entfernung zur Wache nicht durch Ausreisser verwaessert wird
                cl["distance_km"] = min(cl["distance_km"], rep["distance_km"])
                placed = True
                break
        if not placed:
            clusters.append({
                "lat": rep["lat"], "lon": rep["lon"],
                "distance_km": rep["distance_km"],
                "members": [rep],
            })
    return clusters


async def _fetch(client: httpx.AsyncClient, path: str) -> list:
    try:
        resp = await client.get(f"{API_BASE}/{path}", headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error("Stoerungsauskunft %s nicht erreichbar: %s", path, e)
        return []


def is_core_area(postal_code, distance_km) -> bool:
    """Liegt die Meldung im Rhein-Sieg-Kreis (inkl. Troisdorf)?

    Die Postleitzahl ist massgeblich. Nur wenn sie fehlt, entscheidet die
    Entfernung — sonst wuerden Nachbarstaedte wie Koeln-Porz oder Bonn ueber
    den Radius hereinrutschen, obwohl sie nicht zum Kreis gehoeren.
    """
    if postal_code:
        return str(postal_code).strip() in CORE_PLZ
    return distance_km is not None and distance_km <= CORE_FALLBACK_RADIUS_KM


def _locate(rows: list, coord_field: str = "coordinates") -> list:
    """Reichert Meldungen um Entfernung und Zonenzugehoerigkeit an."""
    out = []
    for row in rows:
        lat, lon = parse_coordinates(row.get(coord_field))
        if lat is None:
            continue
        d = _haversine_km(settings.center_lat, settings.center_lon, lat, lon)
        if d > WIDE_RADIUS_KM:
            continue
        out.append({
            "row": row,
            "lat": lat,
            "lon": lon,
            "distance_km": round(d, 1),
            "is_core": is_core_area(row.get("postalCode"), d),
        })
    return out


def cluster_wide(entries: list) -> list:
    """Buendelt Meldungen ausserhalb des Kernbereichs grossflaechig.

    Ein Flaechenausfall verteilt sich ueber viele Orte; erst die Summe zeigt,
    ob es sich um ein Grossereignis handelt.
    """
    clusters = []
    for e in sorted(entries, key=lambda x: x["distance_km"]):
        placed = False
        for cl in clusters:
            if _haversine_km(cl["lat"], cl["lon"], e["lat"], e["lon"]) <= WIDE_CLUSTER_RADIUS_KM:
                cl["members"].append(e)
                cl["distance_km"] = min(cl["distance_km"], e["distance_km"])
                placed = True
                break
        if not placed:
            clusters.append({
                "lat": e["lat"], "lon": e["lon"],
                "distance_km": e["distance_km"],
                "members": [e],
            })
    return clusters


async def collect_power_outages():
    logger.info("Collecting power outages from Stoerungsauskunft...")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        confirmed_raw = await _fetch(client, f"outages?SectorType={SECTOR_ELECTRICITY}")
        reported_raw = await _fetch(
            client, f"usernotification?CountryCode=DE&SectorType={SECTOR_ELECTRICITY}"
        )

    if not confirmed_raw and not reported_raw:
        logger.warning("Keine Daten von der Stoerungsauskunft erhalten")
        return []

    entries = []
    located_confirmed = _locate(confirmed_raw)
    located_reported = [e for e in _locate(reported_raw) if not e["row"].get("disabled")]

    # === Kernbereich: Rhein-Sieg-Kreis — jeder Ausfall zaehlt ===============

    # Ein Ausfall wird teils als mehrere Datensaetze (Strassenzuege) geliefert.
    # Zusammenfassen ueber Betreiber + PLZ + Startzeit.
    seen = {}
    for item in located_confirmed:
        if not item["is_core"]:
            continue
        row = item["row"]
        if row.get("isFixed"):
            continue
        key = (row.get("operatorId"), row.get("postalCode"), row.get("dateStart"))
        if key in seen:
            seen[key]["report_count"] += 1
            seen[key]["distance_km"] = min(seen[key]["distance_km"], item["distance_km"])
            continue

        info_parts = [p for p in (row.get("liveInfo"), row.get("comments")) if p]
        seen[key] = {
            "external_id": str(row.get("id") or row.get("idPublic") or ""),
            "kind": "confirmed",
            "operator_name": row.get("operatorName"),
            "postal_code": row.get("postalCode"),
            "city": row.get("city"),
            "district": row.get("district"),
            "street": row.get("street"),
            "lat": item["lat"],
            "lon": item["lon"],
            "distance_km": item["distance_km"],
            "radius_m": row.get("radius"),
            "report_count": 1,
            "started_at": parse_api_date(row.get("dateStart")),
            "expected_end": parse_api_date(row.get("dateEnd")),
            "last_update": parse_api_date(row.get("lastUpdate")),
            "is_fixed": bool(row.get("isFixed")),
            "is_active": True,
            "info": " | ".join(info_parts) if info_parts else None,
            "source": "stoerungsauskunft",
            "raw_data": {**row, "_zone": "rhein_sieg"},
        }
    entries.extend(seen.values())

    core_reports = [e for e in located_reported if e["is_core"]]
    for cl in cluster_reports(core_reports):
        if len(cl["members"]) < MIN_CLUSTER_REPORTS:
            continue
        members = cl["members"]
        first = members[0]["row"]
        starts = [parse_api_date(m["row"].get("dateStart")) for m in members]
        starts = [s for s in starts if s]
        cities = {m["row"].get("city") for m in members if m["row"].get("city")}

        entries.append({
            "external_id": "cluster-" + "-".join(
                sorted(str(m["row"].get("id")) for m in members)[:5]
            ),
            "kind": "reported",
            "operator_name": first.get("operatorName"),
            "postal_code": first.get("postalCode"),
            "city": ", ".join(sorted(cities)[:3]) if cities else first.get("city"),
            "district": None,
            "street": None,
            "lat": cl["lat"],
            "lon": cl["lon"],
            "distance_km": cl["distance_km"],
            "radius_m": None,
            "report_count": len(members),
            "started_at": min(starts) if starts else None,
            "expected_end": None,
            "last_update": max(starts) if starts else None,
            "is_fixed": False,
            "is_active": True,
            "info": f"{len(members)} Bürgermeldungen im Umkreis von {CLUSTER_RADIUS_KM:.0f} km",
            "source": "stoerungsauskunft_buerger",
            "raw_data": {"member_ids": [m["row"].get("id") for m in members],
                         "_zone": "rhein_sieg"},
        })

    # === Ausserhalb: nur Grossereignisse ===================================
    # Ein einzelner Ausfall zwei Kreise weiter ist fuer Troisdorf belanglos.
    # Erfasst wird erst, was flaechig genug ist, um ueberregional zu wirken —
    # etwa als Amtshilfe-Lage.
    outside = [e for e in located_confirmed + located_reported if not e["is_core"]]
    outside = [e for e in outside if not e["row"].get("isFixed")]

    for cl in cluster_wide(outside):
        members = cl["members"]
        # Buergermeldungen zaehlen einzeln; ein bestaetigter Betreiber-Datensatz
        # steht fuer einen ganzen Strassenzug und wiegt daher schwerer.
        report_weight = sum(
            1 if m["row"].get("id") and "sectorType" in m["row"] else 5
            for m in members
        )
        if report_weight < LARGE_SCALE_MIN_REPORTS:
            continue

        cities = {m["row"].get("city") for m in members if m["row"].get("city")}
        operators = {m["row"].get("operatorName") for m in members if m["row"].get("operatorName")}
        starts = [parse_api_date(m["row"].get("dateStart")) for m in members]
        starts = [s for s in starts if s]
        clear = report_weight >= LARGE_SCALE_CLEAR_REPORTS

        entries.append({
            "external_id": "grossereignis-" + "-".join(
                sorted(str(m["row"].get("id")) for m in members)[:5]
            ),
            "kind": "large_scale",
            "operator_name": ", ".join(sorted(operators)[:2]) if operators else None,
            "postal_code": members[0]["row"].get("postalCode"),
            "city": ", ".join(sorted(cities)[:3]) if cities else None,
            "district": None,
            "street": None,
            "lat": cl["lat"],
            "lon": cl["lon"],
            "distance_km": cl["distance_km"],
            "radius_m": None,
            "report_count": report_weight,
            "started_at": min(starts) if starts else None,
            "expected_end": None,
            "last_update": max(starts) if starts else None,
            "is_fixed": False,
            "is_active": True,
            "info": (
                f"Großflächiger Ausfall außerhalb des Kreises: {report_weight} Meldungen "
                f"in {len(cities) or 1} Orten"
                + (" — überregionale Lage" if clear else " — Schwelle knapp erreicht")
            ),
            "source": "stoerungsauskunft_grossereignis",
            "raw_data": {
                "_zone": "ausserhalb",
                "report_weight": report_weight,
                "member_count": len(members),
                "cities": sorted(cities)[:20],
                "clear_large_scale": clear,
            },
        })

    async with async_session() as session:
        # Alles, was nicht mehr in der Quelle steht, gilt als behoben.
        current_ids = {e["external_id"] for e in entries}
        existing = (await session.execute(
            select(PowerOutage).where(PowerOutage.is_active == True)
        )).scalars().all()
        for old in existing:
            if old.external_id not in current_ids:
                old.is_active = False
                old.is_fixed = True

        known = {(o.external_id, o.kind): o for o in existing}
        for data in entries:
            hit = known.get((data["external_id"], data["kind"]))
            if hit:
                hit.report_count = data["report_count"]
                hit.expected_end = data["expected_end"]
                hit.last_update = data["last_update"]
                hit.info = data["info"]
                hit.is_active = True
                hit.is_fixed = False
            else:
                session.add(PowerOutage(**data))
        await session.commit()

    confirmed = sum(1 for e in entries if e["kind"] == "confirmed")
    clusters = sum(1 for e in entries if e["kind"] == "reported")
    large = sum(1 for e in entries if e["kind"] == "large_scale")
    nearest = min((e["distance_km"] for e in entries), default=None)
    logger.info(
        "Stromausfaelle Rhein-Sieg: %s bestaetigt, %s Melde-Cluster; "
        "ausserhalb: %s Grossereignisse (ab %s Meldungen)%s",
        confirmed, clusters, large, LARGE_SCALE_MIN_REPORTS,
        f"; naechster {nearest} km" if nearest is not None else "",
    )
    return entries
