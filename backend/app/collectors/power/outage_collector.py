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

# --- Drei Relevanzzonen ------------------------------------------------------
# Je weiter weg, desto groesser muss ein Ereignis sein, um ueberhaupt
# einsatzrelevant zu werden:
#
#   Troisdorf        -> jeder Ausfall zaehlt
#   Rhein-Sieg-Kreis -> nur Grosslagen
#   ausserhalb       -> nur Extremlagen
#
# Ein einzelner Trafoschaden in Siegburg ist fuer Troisdorf kein Anlass; ein
# flaechiger Ausfall im Kreis dagegen sehr wohl.

ZONE_TROISDORF = "troisdorf"
ZONE_RHEIN_SIEG = "rhein_sieg"
ZONE_OUTSIDE = "ausserhalb"

TROISDORF_PLZ = {"53840", "53842", "53844"}

# Die uebrigen 18 Kommunen des Rhein-Sieg-Kreises. Bewusst als Liste statt als
# Radius: der Kreis reicht im Osten (Windeck) deutlich weiter als im Westen.
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
}

# Nur wenn eine Meldung gar keine PLZ mitbringt, entscheidet die Entfernung.
TROISDORF_FALLBACK_RADIUS_KM = 7.0
KREIS_FALLBACK_RADIUS_KM = 25.0

# Umkreis, in dem ueberhaupt gesucht wird
WIDE_RADIUS_KM = 150.0

# Buergermeldungen in Troisdorf werden eng gebuendelt; einzelne Meldung kann
# eine Haussicherung sein, mehrere dicht beieinander sind ein Signal.
CLUSTER_RADIUS_KM = 3.0
MIN_CLUSTER_REPORTS = 3

# Grosslage im Kreis: mittlere Buendelung, spuerbare Groesse
KREIS_CLUSTER_RADIUS_KM = 10.0
GROSSLAGE_MIN_REPORTS = 100
GROSSLAGE_CLEAR_REPORTS = 300

# Extremlage ausserhalb: grossflaechige Buendelung, deutlich hoehere Huerde —
# hier interessiert nur noch, was ueberregional Kraefte binden koennte.
WIDE_CLUSTER_RADIUS_KM = 25.0
EXTREMLAGE_MIN_REPORTS = 500
EXTREMLAGE_CLEAR_REPORTS = 1500

# Ein bestaetigter Betreiber-Datensatz steht fuer einen ganzen Strassenzug und
# wiegt daher schwerer als eine einzelne Buergermeldung.
CONFIRMED_RECORD_WEIGHT = 5

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


def zone_of(postal_code, distance_km) -> str:
    """Ordnet eine Meldung einer der drei Relevanzzonen zu.

    Die Postleitzahl ist massgeblich. Nur wenn sie fehlt, entscheidet die
    Entfernung — sonst wuerden Nachbarstaedte wie Koeln-Porz oder Bonn ueber
    einen Radius hereinrutschen, obwohl sie nicht zum Kreis gehoeren.
    """
    if postal_code:
        plz = str(postal_code).strip()
        if plz in TROISDORF_PLZ:
            return ZONE_TROISDORF
        if plz in RHEIN_SIEG_PLZ:
            return ZONE_RHEIN_SIEG
        return ZONE_OUTSIDE

    if distance_km is None:
        return ZONE_OUTSIDE
    if distance_km <= TROISDORF_FALLBACK_RADIUS_KM:
        return ZONE_TROISDORF
    if distance_km <= KREIS_FALLBACK_RADIUS_KM:
        return ZONE_RHEIN_SIEG
    return ZONE_OUTSIDE


def _locate(rows: list, coord_field: str = "coordinates") -> list:
    """Reichert Meldungen um Entfernung und Zone an."""
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
            "zone": zone_of(row.get("postalCode"), d),
        })
    return out


def cluster_by_radius(entries: list, radius_km: float) -> list:
    """Buendelt Meldungen raeumlich zu Ereignissen.

    Je groesser das betrachtete Gebiet, desto weiter der Radius: ein
    Flaechenausfall verteilt sich ueber ganze Staedte.
    """
    clusters = []
    for e in sorted(entries, key=lambda x: x["distance_km"]):
        placed = False
        for cl in clusters:
            if _haversine_km(cl["lat"], cl["lon"], e["lat"], e["lon"]) <= radius_km:
                cl["members"].append(e)
                # Zentrum bleibt die naechstgelegene Meldung, damit die
                # Entfernung nicht durch Ausreisser verwaessert wird
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


def is_confirmed_record(row: dict) -> bool:
    """Betreiber-Meldung oder Buergermeldung?

    Buergermeldungen tragen ``sectorType``, bestaetigte Stoerungen ``SectorType``
    — das unterscheidet die beiden Endpunkte zuverlaessig.
    """
    return "sectorType" not in row


def report_weight(members: list) -> int:
    """Gewicht eines Ereignisses in 'Meldungen'.

    Buergermeldungen zaehlen einfach, ein bestaetigter Betreiber-Datensatz
    steht fuer einen ganzen Strassenzug und zaehlt entsprechend hoeher.
    """
    return sum(
        CONFIRMED_RECORD_WEIGHT if is_confirmed_record(m["row"]) else 1
        for m in members
    )


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
    located = _locate(confirmed_raw) + _locate(reported_raw)
    located = [e for e in located
               if not e["row"].get("isFixed") and not e["row"].get("disabled")]

    by_zone = {ZONE_TROISDORF: [], ZONE_RHEIN_SIEG: [], ZONE_OUTSIDE: []}
    for e in located:
        by_zone[e["zone"]].append(e)

    # === Troisdorf: jeder Ausfall zaehlt ===================================

    # Ein Ausfall wird teils als mehrere Datensaetze (Strassenzuege) geliefert.
    # Zusammenfassen ueber Betreiber + PLZ + Startzeit.
    seen = {}
    for item in by_zone[ZONE_TROISDORF]:
        row = item["row"]
        if not is_confirmed_record(row):
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
            "is_fixed": False,
            "is_active": True,
            "info": " | ".join(info_parts) if info_parts else None,
            "source": "stoerungsauskunft",
            "raw_data": {**row, "_zone": ZONE_TROISDORF},
        }
    entries.extend(seen.values())

    troisdorf_reports = [e for e in by_zone[ZONE_TROISDORF]
                         if not is_confirmed_record(e["row"])]
    for cl in cluster_by_radius(troisdorf_reports, CLUSTER_RADIUS_KM):
        if len(cl["members"]) < MIN_CLUSTER_REPORTS:
            continue
        entries.append(_aggregate_entry(
            cl, kind="reported", zone=ZONE_TROISDORF,
            weight=len(cl["members"]),
            info=f"{len(cl['members'])} Bürgermeldungen aus Troisdorf, "
                 f"vom Netzbetreiber noch nicht bestätigt",
            source="stoerungsauskunft_buerger",
        ))

    # === Rhein-Sieg-Kreis: nur Grosslagen ==================================
    for cl in cluster_by_radius(by_zone[ZONE_RHEIN_SIEG], KREIS_CLUSTER_RADIUS_KM):
        weight = report_weight(cl["members"])
        if weight < GROSSLAGE_MIN_REPORTS:
            continue
        clear = weight >= GROSSLAGE_CLEAR_REPORTS
        cities = _cities_of(cl)
        entries.append(_aggregate_entry(
            cl, kind="grosslage", zone=ZONE_RHEIN_SIEG, weight=weight,
            info=(f"Großlage im Rhein-Sieg-Kreis: {weight} Meldungen in "
                  f"{len(cities) or 1} Orten"
                  + (" — flächiger Ausfall" if clear else " — Schwelle erreicht")),
            source="stoerungsauskunft_grosslage",
            extra={"clear": clear},
        ))

    # === Ausserhalb: nur Extremlagen =======================================
    for cl in cluster_by_radius(by_zone[ZONE_OUTSIDE], WIDE_CLUSTER_RADIUS_KM):
        weight = report_weight(cl["members"])
        if weight < EXTREMLAGE_MIN_REPORTS:
            continue
        clear = weight >= EXTREMLAGE_CLEAR_REPORTS
        cities = _cities_of(cl)
        entries.append(_aggregate_entry(
            cl, kind="extremlage", zone=ZONE_OUTSIDE, weight=weight,
            info=(f"Extremlage außerhalb des Kreises: {weight} Meldungen in "
                  f"{len(cities) or 1} Orten"
                  + (" — großräumiger Ausfall" if clear else " — Schwelle erreicht")),
            source="stoerungsauskunft_extremlage",
            extra={"clear": clear},
        ))

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

    counts = {k: sum(1 for e in entries if e["kind"] == k)
              for k in ("confirmed", "reported", "grosslage", "extremlage")}
    logger.info(
        "Stromausfaelle — Troisdorf: %s bestaetigt, %s Melde-Cluster | "
        "Kreis: %s Grosslagen (ab %s) | ausserhalb: %s Extremlagen (ab %s)",
        counts["confirmed"], counts["reported"],
        counts["grosslage"], GROSSLAGE_MIN_REPORTS,
        counts["extremlage"], EXTREMLAGE_MIN_REPORTS,
    )
    return entries


def _cities_of(cluster: dict) -> set:
    return {m["row"].get("city") for m in cluster["members"] if m["row"].get("city")}


def _aggregate_entry(cluster: dict, kind: str, zone: str, weight: int,
                     info: str, source: str, extra: dict = None) -> dict:
    """Baut aus einem Meldungs-Cluster einen Datensatz."""
    members = cluster["members"]
    first = members[0]["row"]
    cities = _cities_of(cluster)
    operators = {m["row"].get("operatorName") for m in members if m["row"].get("operatorName")}
    starts = [parse_api_date(m["row"].get("dateStart")) for m in members]
    starts = [s for s in starts if s]

    return {
        "external_id": f"{kind}-" + "-".join(
            sorted(str(m["row"].get("id")) for m in members)[:5]
        ),
        "kind": kind,
        "operator_name": ", ".join(sorted(operators)[:2]) if operators else None,
        "postal_code": first.get("postalCode"),
        "city": ", ".join(sorted(cities)[:3]) if cities else first.get("city"),
        "district": None,
        "street": None,
        "lat": cluster["lat"],
        "lon": cluster["lon"],
        "distance_km": cluster["distance_km"],
        "radius_m": None,
        "report_count": weight,
        "started_at": min(starts) if starts else None,
        "expected_end": None,
        "last_update": max(starts) if starts else None,
        "is_fixed": False,
        "is_active": True,
        "info": info,
        "source": source,
        "raw_data": {
            "_zone": zone,
            "report_weight": weight,
            "member_count": len(members),
            "cities": sorted(cities)[:20],
            **(extra or {}),
        },
    }
