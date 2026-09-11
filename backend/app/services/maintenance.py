"""Aufraeumarbeiten an gewachsenen Datenbestaenden.

Zwei Fehler haben ueber Wochen Duplikate erzeugt:

* Der DWD-Collector legte jede Warnung bei jedem Lauf (alle 5 Minuten) neu an.
  Vier gueltige Warnungen wurden so binnen sechs Stunden zu 288 Zeilen.
* Die Alarm-Dedup pruefte nur ein Zeitfenster von einer Stunde und loeste
  dieselbe Lage danach immer wieder neu aus. Der Rueckmeldungs-Stapel fuellte
  sich mit Dutzenden Eintraegen, die alle dasselbe Ereignis meinten.

Beide Ursachen sind behoben. Die Routinen hier raeumen auf, was vorher
entstanden ist — einmalig beim Start und bei Bedarf ueber die Admin-API.
Sie sind bewusst idempotent: ein zweiter Lauf findet nichts mehr zu tun.
"""

import logging
import re
from datetime import datetime, timedelta

from sqlalchemy import select, text

from app.models.database import async_session, engine
from app.models.schemas import Alert, AlertFeedback, WeatherData

logger = logging.getLogger(__name__)

# Alarme derselben Schwelle innerhalb dieses Abstands gelten als dieselbe Lage.
# Entspricht dem Wiederbenachrichtigungs-Abstand der Alarm-Engine.
EPISODE_GAP = timedelta(hours=6)


def group_weather_duplicates(rows) -> dict:
    """Warnungen nach ihrem Identitaetsschluessel buendeln.

    Reine Funktion ohne Datenbankzugriff, damit die Gruppierung pruefbar ist.
    Die Reihenfolge innerhalb einer Gruppe bleibt erhalten — der erste Eintrag
    ist damit der aelteste, wenn die Eingabe chronologisch sortiert ist.
    """
    groups: dict[str, list] = {}
    for row in rows:
        groups.setdefault(_weather_key(row), []).append(row)
    return groups


def plan_alert_episodes(alerts, answered_ids=None, gap: timedelta = EPISODE_GAP) -> list:
    """Alarme derselben Schwelle in Episoden zerlegen.

    Erwartet die Alarme chronologisch sortiert. Liefert je Episode ein Paar
    ``(Vertreter, [Wiederholungen])``. Ein Alarm beginnt eine neue Episode,
    wenn seit dem vorigen mehr als ``gap`` vergangen ist.

    Bereits beantwortete Alarme (``answered_ids``) bleiben Vertreter ihrer
    selbst — ein abgegebenes Urteil wird nicht nachtraeglich einkassiert.
    """
    answered = answered_ids or set()
    from app.services.alert.alert_engine import _threshold_key_of

    by_threshold: dict[tuple, list] = {}
    for alert in alerts:
        by_threshold.setdefault(_threshold_key_of(alert), []).append(alert)

    episodes = []
    for group in by_threshold.values():
        current = None
        last_seen = None
        for alert in group:
            ts = alert.triggered_at or alert.created_at
            # Ohne Zeitstempel laesst sich keine Episode bilden — solche Alarme
            # bleiben fuer sich stehen, statt fremde Wiederholungen zu schlucken.
            if ts is None or current is None or last_seen is None or ts - last_seen > gap:
                current = (alert, [])
                episodes.append(current)
            elif alert.id not in answered:
                current[1].append(alert)
            last_seen = ts
    return episodes


def _weather_key(row) -> str:
    """Schluessel einer DWD-Warnung.

    Neue Zeilen tragen ihn in ``parameters._key``. Fuer Altbestaende, die vor
    dem Upsert entstanden sind, wird er aus denselben Bestandteilen
    rekonstruiert — Warnzelle, Ereignis und Gueltigkeit.
    """
    params = row.parameters if isinstance(row.parameters, dict) else {}
    key = params.get("_key")
    if key:
        return str(key)
    return "|".join(str(p) for p in (
        params.get("warncell_id", row.region or ""),
        params.get("event", row.title or ""),
        row.valid_from.isoformat() if row.valid_from else "",
        row.valid_to.isoformat() if row.valid_to else "",
    ))


async def collapse_weather_duplicates(dry_run: bool = False) -> dict:
    """Mehrfach angelegte DWD-Warnungen auf je eine Zeile zusammenfassen.

    Behalten wird die aelteste Zeile (sie traegt den echten Erstkontakt), ihr
    Inhalt wird aber vom juengsten Duplikat uebernommen — das ist der aktuellste
    Stand. Der Schluessel wird dabei nachgetragen, damit der Collector die Zeile
    beim naechsten Lauf wiederfindet.
    """
    removed = 0
    kept = 0
    async with async_session() as session:
        rows = (await session.execute(
            select(WeatherData)
            .where(WeatherData.data_type == "warning")
            .order_by(WeatherData.created_at.asc(), WeatherData.id.asc())
        )).scalars().all()

        groups = group_weather_duplicates(rows)

        for key, group in groups.items():
            kept += 1
            if len(group) == 1:
                # Schluessel auch bei Einzelstuecken nachtragen
                if not dry_run:
                    params = dict(group[0].parameters or {})
                    if not params.get("_key"):
                        params["_key"] = key
                        group[0].parameters = params
                continue

            keeper, extras = group[0], group[1:]
            newest = extras[-1]
            removed += len(extras)
            if dry_run:
                continue

            keeper.severity = newest.severity
            keeper.title = newest.title
            keeper.description = newest.description
            keeper.valid_from = newest.valid_from
            keeper.valid_to = newest.valid_to
            keeper.raw_data = newest.raw_data
            params = dict(newest.parameters or {})
            params["_key"] = key
            keeper.parameters = params
            for extra in extras:
                await session.delete(extra)

        if not dry_run:
            await session.commit()

    logger.info(
        "Wetterwarnungen aufgeraeumt: %d Duplikate entfernt, %d Warnungen verbleiben%s",
        removed, kept, " (Probelauf)" if dry_run else "",
    )
    return {"removed": removed, "kept": kept, "dry_run": dry_run}


async def collapse_alert_duplicates(dry_run: bool = False) -> dict:
    """Wiederholt ausgeloeste Alarme derselben Lage zu einer Episode buendeln.

    Alarme werden je Kategorie und Schwelle chronologisch durchgegangen. Folgt
    einer innerhalb von ``EPISODE_GAP`` auf den vorigen, gehoert er zur selben
    Episode: Der erste bleibt als Vertreter stehen, die uebrigen werden als
    aufgeloest und ``_superseded`` markiert. Damit verschwinden sie aus der
    Rueckmeldungsliste, bleiben aber als Verlauf erhalten — geloescht wird
    nichts.

    Alarme mit bereits abgegebener Rueckmeldung bleiben unangetastet.
    """
    superseded = 0
    episodes = 0
    async with async_session() as session:
        alerts = (await session.execute(
            select(Alert).order_by(Alert.triggered_at.asc(), Alert.id.asc())
        )).scalars().all()

        answered = set((await session.execute(
            select(AlertFeedback.alert_id)
        )).scalars().all())

        now = datetime.utcnow()
        plan = plan_alert_episodes(alerts, answered_ids=answered)
        episodes = len(plan)

        for representative, repeats in plan:
            superseded += len(repeats)
            if dry_run:
                continue
            for alert in repeats:
                cfg = dict(alert.threshold_config or {})
                cfg["_superseded"] = True
                cfg["_superseded_by"] = representative.id
                alert.threshold_config = cfg
                alert.is_active = False
                if alert.resolved_at is None:
                    alert.resolved_at = now
                # Der Vertreter behaelt die hoechste Auspraegung der Episode
                if alert.score > representative.score:
                    representative.score = alert.score
                    representative.escalation_level = max(
                        representative.escalation_level or 0,
                        alert.escalation_level or 0,
                    )

        if not dry_run:
            await session.commit()

    logger.info(
        "Alarme aufgeraeumt: %d Wiederholungen gebuendelt, %d eigenstaendige Lagen%s",
        superseded, episodes, " (Probelauf)" if dry_run else "",
    )
    return {"superseded": superseded, "episodes": episodes, "dry_run": dry_run}


# Enum-Werte, die nach der ersten Auslieferung dazugekommen sind.
#
# create_all legt fehlende TABELLEN an, erweitert aber keinen bestehenden
# Postgres-Enum-Typ. Ohne diese Ergaenzung schlaegt jeder Schreibvorgang mit
# dem neuen Wert fehl — und zwar erst zur Laufzeit, nicht beim Start.
ENUM_NACHTRAEGE = {
    "knowledgescope": ("nachbarschaft",),
}

# Enum-Typen und -Werte bestehen nur aus Kleinbuchstaben, Ziffern und
# Unterstrichen. Die Pruefung verhindert, dass je etwas anderes in eine
# Anweisung geraet, die keine Parameter zulaesst.
_BEZEICHNER = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def _ist_sicherer_bezeichner(wert: str) -> bool:
    return bool(_BEZEICHNER.match(wert or ""))


async def ergaenze_enum_werte() -> dict:
    """Fehlende Enum-Werte nachtragen.

    Zwei Eigenheiten von Postgres bestimmen die Umsetzung:

    * ``ALTER TYPE ... ADD VALUE`` nimmt KEINE gebundenen Parameter. Der Wert
      muss als Literal im Anweisungstext stehen. Die Werte stammen
      ausschliesslich aus ``ENUM_NACHTRAEGE`` hier im Code; zur Sicherheit
      wird die Schreibweise trotzdem geprueft, bevor sie eingesetzt wird.
    * Ein neu hinzugefuegter Wert darf in derselben Transaktion nicht benutzt
      werden. Deshalb laeuft jede Anweisung auf einer eigenen Verbindung im
      Autocommit-Modus.

    ``IF NOT EXISTS`` macht den Lauf idempotent.
    """
    ergaenzt = []
    for typ, werte in ENUM_NACHTRAEGE.items():
        for wert in werte:
            if not _ist_sicherer_bezeichner(typ) or not _ist_sicherer_bezeichner(wert):
                logger.error("Enum-Nachtrag uebersprungen: %s.%s", typ, wert)
                continue
            try:
                async with engine.connect() as conn:
                    await conn.execution_options(isolation_level="AUTOCOMMIT")
                    await conn.execute(text(
                        f"ALTER TYPE {typ} ADD VALUE IF NOT EXISTS '{wert}'"
                    ))
                ergaenzt.append(f"{typ}.{wert}")
            except Exception as e:
                # Existiert der Typ noch nicht, legt create_all ihn ohnehin
                # vollstaendig an — das ist kein Fehler.
                logger.debug("Enum %s.%s nicht ergaenzt: %s", typ, wert, e)

    if ergaenzt:
        logger.info("Enum-Werte geprueft: %s", ", ".join(ergaenzt))
    return {"geprueft": ergaenzt}


async def run_startup_maintenance() -> dict:
    """Beim Start einmal aufraeumen — Fehler hier duerfen den Start nicht stoppen."""
    result: dict = {}
    for name, func in (
        # Zuerst das Schema, dann die Daten — sonst scheitern Schreibvorgaenge
        # mit neuen Enum-Werten.
        ("enums", ergaenze_enum_werte),
        ("weather", collapse_weather_duplicates),
        ("alerts", collapse_alert_duplicates),
    ):
        try:
            result[name] = await func()
        except Exception as e:  # pragma: no cover - Startpfad
            logger.error("Aufraeumen (%s) fehlgeschlagen: %s", name, e, exc_info=True)
            result[name] = {"error": str(e)}
    return result
