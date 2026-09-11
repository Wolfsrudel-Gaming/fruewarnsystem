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


# ======================================================================
# Wachsamkeit
# ======================================================================
#
# Eine laufende Grossveranstaltung ist fuer sich genommen harmlos. Sie ist
# aber ein VERSTAERKER: Bei einer Million Menschen auf 80.000 Quadratmetern
# wird aus einem kleinen Ereignis binnen Minuten etwas, das den gesamten
# Grossraum bindet. Ein Massenanfall dort loest ueberoertliche Hilfe aus, und
# dann laufen auch die Troisdorfer Einheiten.
#
# Daraus folgt nicht, lauter zu alarmieren — die Veranstaltung selbst ist
# Normalbetrieb. Es folgt, GENAUER HINZUSEHEN: haeufiger abfragen, damit eine
# Abweichung frueher auffaellt, und die Kategorien schaerfer werten, die bei
# einer solchen Lage tatsaechlich zaehlen.

WACHSAMKEIT_NORMAL = "normal"
WACHSAMKEIT_ERHOEHT = "erhoeht"

# Zonen, in denen eine Grosslage die Wachsamkeit anhebt. Ein Volksfest in
# Ostwestfalen aendert hier nichts.
WACHSAME_ZONEN = ("troisdorf", "nachbarschaft", "rhein_sieg")

# Wie oft waehrend erhoehter Wachsamkeit abgefragt wird, in Sekunden.
# Bewusst nur die Quellen, die bei einer ploetzlichen Lage als Erste etwas
# zeigen — nicht jede Schnittstelle. Strompreise und Pegelstaende aendern sich
# durch eine Kirmes nicht.
ABTASTUNG_ERHOEHT = {
    # Soziale Netze zuerst: Wer auf dem Platz steht und etwas sieht, schreibt
    # darueber, lange bevor eine Leitstelle eine Meldung herausgibt. Genau
    # diese Vorlaufzeit ist bei einer Grosslage entscheidend.
    "social": 90,
    # Amtliche Warnungen: Ein echter Massenanfall erzeugt hier zuerst eine
    # Meldung. Die wichtigste Quelle ueberhaupt.
    "warnings": 60,
    # Presse: nach Auskunft der Einheit der zuverlaessigste Fruehindikator
    "news": 180,
    # Feuerwehr Bonn — Puetzchen liegt im Bonner Stadtgebiet
    "feuerwehr_bonn": 60,
    # Wetter: der kritische Punkt bei hoher Personendichte im Freien
    "weather_warnings": 180,
    # Verkehr: Massenabfluss, Sperrungen, blockierte Rettungswege
    "traffic": 300,
}


def wachsamkeitsstufe(tag: Optional[date] = None) -> dict:
    """Aktuelle Wachsamkeit des Systems.

    Erhoeht, solange eine Grosslage in erreichbarer Naehe laeuft. Nicht schon
    im Vorlauf: Vorher gibt es nichts zu beobachten, was es nicht sonst auch
    gaebe.
    """
    aktive = [l for l in aktive_grosslagen(tag)
              if l.get("zone") in WACHSAME_ZONEN]
    if not aktive:
        return {
            "stufe": WACHSAMKEIT_NORMAL,
            "grund": None,
            "lagen": [],
            "abtastung": {},
        }

    namen = ", ".join(l["name"] for l in aktive)
    besucher = max((l.get("besucher") or 0) for l in aktive)
    # Tausenderpunkte nach deutscher Schreibweise — getrennt gebildet, damit
    # die Ersetzung nicht die Satzkommas mitnimmt.
    besucher_text = f"{besucher:,}".replace(",", ".")
    return {
        "stufe": WACHSAMKEIT_ERHOEHT,
        "grund": (
            f"{namen} laeuft. Bei dieser Groessenordnung "
            f"({besucher_text} Besucher) kann aus einem kleinen Ereignis "
            f"binnen Minuten eine Lage werden, die den gesamten Grossraum "
            f"bindet. Das System fragt deshalb haeufiger ab und wertet die "
            f"Kategorien schaerfer, die dabei zaehlen."
        ),
        "lagen": [{"name": l["name"], "ort": l["ort"], "zone": l["zone"],
                   "tag_nummer": l["tag_nummer"],
                   "tage_gesamt": l["tage_gesamt"]} for l in aktive],
        "abtastung": dict(ABTASTUNG_ERHOEHT),
    }


def ist_wachsam(tag: Optional[date] = None) -> bool:
    return wachsamkeitsstufe(tag)["stufe"] == WACHSAMKEIT_ERHOEHT
