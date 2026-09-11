"""Bekannte wiederkehrende Grosslagen.

Manche Veranstaltungen sind so gross und so regelmaessig, dass es falsch
waere, sich auf eine Veranstaltungs-API zu verlassen. Sie finden jedes Jahr
statt, der Termin folgt einer festen Regel, und die Belastung ist aus den
Vorjahren bekannt. Dieses Wissen gehoert fest hinterlegt.

DER WICHTIGE TEIL IST DIE GRUNDLAST
-----------------------------------
Eine Grossveranstaltung erzeugt im Normalbetrieb eine hohe, aber voellig
erwartbare Zahl an Hilfeleistungen. Bei Puetzchens Markt waren es 2025 rund
180 Behandlungen und 48 Transporte — bei etwa 950.000 Besuchern und ohne
jeden besonderen Vorfall. Die Feuerwehr rueckte in beiden ausgewerteten
Jahren zu keinem einzigen Einsatz aus.

Ohne dieses Wissen liest ein Fruehwarnsystem eine Schlagzeile wie
"Rettungsdienst im Dauereinsatz auf Puetzchens Markt" als Eskalation — dabei
beschreibt sie den Normalzustand. Die Grundlast ist deshalb der Massstab:
Erst deutlich darueber wird eine Meldung zum Signal.
"""

from datetime import date, timedelta
from typing import Optional


def _zweiter_sonntag(jahr: int, monat: int) -> date:
    """Zweiter Sonntag eines Monats."""
    erster = date(jahr, monat, 1)
    erster_sonntag = erster + timedelta(days=(6 - erster.weekday()) % 7)
    return erster_sonntag + timedelta(days=7)


def _puetzchens_markt(jahr: int) -> tuple:
    """Freitag vor dem zweiten Sonntag im September bis zum Dienstag danach.

    Geprueft gegen die amtlichen Termine 2024 (06.-10.09.), 2025 (12.-16.09.)
    und 2026 (11.-15.09.).
    """
    sonntag = _zweiter_sonntag(jahr, 9)
    return sonntag - timedelta(days=2), sonntag + timedelta(days=2)


# Wie stark die Zahlen einer Meldung die Grundlast uebersteigen muessen,
# damit sie als auffaellig gilt. Unterhalb davon beschreibt die Meldung den
# erwartbaren Betrieb.
AUFFAELLIG_AB_FAKTOR = 2.0


GROSSLAGEN = [
    {
        "key": "puetzchens_markt",
        "name": "Puetzchens Markt",
        "ort": "Bonn-Beuel, Stadtteil Puetzchen",
        # Bonn liegt ausserhalb des Kreises, dieser Platz aber unmittelbar an
        # der Grenze zu Sankt Augustin — und es faehrt eine Sonderbuslinie
        # direkt aus Troisdorf. Deshalb Nachbarschaft, nicht "ausserhalb".
        "zone": "nachbarschaft",
        "termin": _puetzchens_markt,
        "besucher": 1_000_000,
        "flaeche_qm": 80_000,
        "geschaefte": 500,
        # Grundlast aus den amtlichen Bilanzen der Vorjahre
        "grundlast": {
            "behandlungen": 280,      # 2024: 279 Sanitaetshilfeleistungen
            "rettungseinsaetze": 100,  # 2024: 98
            "transporte": 50,          # 2025: 48
            "notarzt": 13,             # 2024: 13, 2025: 8
            "feuerwehr": 0,            # 2024 und 2025: kein Einsatz
        },
        "bemerkungen": (
            "Groesstes Volksfest der Region, fuenf Tage, bis 3 Uhr nachts. "
            "Sanitaetsdienst, Rettungsdienst und Feuerwehr sind in der "
            "Marktschule stationiert, dazu eine Rettungswache auf dem "
            "Gelaende und mobile Trupps. Abschlussfeuerwerk am Dienstag "
            "gegen 22 Uhr — der Zeitpunkt mit der hoechsten Personendichte."
        ),
    },
]


def aktive_grosslagen(tag: Optional[date] = None) -> list:
    """Welche bekannten Grosslagen laufen an diesem Tag?"""
    tag = tag or date.today()
    treffer = []
    for lage in GROSSLAGEN:
        beginn, ende = lage["termin"](tag.year)
        if beginn <= tag <= ende:
            treffer.append({**lage, "beginn": beginn, "ende": ende,
                            "tag_nummer": (tag - beginn).days + 1,
                            "tage_gesamt": (ende - beginn).days + 1})
    return treffer


def bevorstehende_grosslagen(tag: Optional[date] = None,
                             vorlauf_tage: int = 7) -> list:
    """Grosslagen, die binnen ``vorlauf_tage`` beginnen.

    Der Bedarfsplan plant Sonderbedarf mit mindestens 24 Stunden Vorlauf; fuer
    eine fuenftaegige Grosslage ist eine Woche die brauchbarere Vorwarnzeit.
    """
    tag = tag or date.today()
    treffer = []
    for lage in GROSSLAGEN:
        for jahr in (tag.year, tag.year + 1):
            beginn, ende = lage["termin"](jahr)
            abstand = (beginn - tag).days
            if 0 < abstand <= vorlauf_tage:
                treffer.append({**lage, "beginn": beginn, "ende": ende,
                                "in_tagen": abstand})
                break
    return treffer


def ist_auffaellig(lage: dict, gemeldet: dict) -> bool:
    """Weichen gemeldete Zahlen deutlich von der Grundlast ab?

    ``gemeldet`` enthaelt dieselben Schluessel wie ``grundlast``. Fehlt ein
    Wert, wird er nicht geprueft — ein einzelner auffaelliger Wert genuegt.

    Der Feuerwehr-Wert ist der empfindlichste: Die Grundlast ist null. Jeder
    Feuerwehreinsatz auf dem Gelaende ist damit per Definition auffaellig.
    """
    grundlast = lage.get("grundlast") or {}
    for schluessel, wert in (gemeldet or {}).items():
        if wert is None:
            continue
        erwartet = grundlast.get(schluessel)
        if erwartet is None:
            continue
        if erwartet == 0:
            if wert > 0:
                return True
            continue
        if wert >= erwartet * AUFFAELLIG_AB_FAKTOR:
            return True
    return False


def grundlast_text(lage: dict) -> str:
    """Erwartungswert in Worten — fuer Begruendungen und den Lagebericht."""
    g = lage.get("grundlast") or {}
    teile = []
    if g.get("behandlungen"):
        teile.append(f"rund {g['behandlungen']} Behandlungen")
    if g.get("transporte"):
        teile.append(f"etwa {g['transporte']} Transporte")
    if g.get("notarzt"):
        teile.append(f"rund {g['notarzt']} Notarzteinsaetze")
    if not teile:
        return ""
    return (
        f"Erwartbar ueber die gesamte Veranstaltung: {', '.join(teile)}. "
        f"Das ist der Normalbetrieb, kein Hinweis auf eine Lage."
    )
