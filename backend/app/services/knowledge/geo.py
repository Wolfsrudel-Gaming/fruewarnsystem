"""Ortsbezug von Meldungen erkennen.

Nachrichten sind der staerkste Einsatzindikator des DRK Troisdorf — aber nur,
solange klar ist, WO etwas passiert. Ein Grossbrand in Troisdorf und einer in
Dueren erzeugen denselben Messwert und bedeuten voellig Verschiedenes.

Bisher hing die Ortserkennung davon ab, ob das Sprachmodell den Ortsnamen
zufaellig in seiner Begruendung erwaehnte. Bei einem Gewicht von 1.0 ist das
zu wackelig. Dieses Modul erkennt den Ort direkt aus dem Meldungstext und ist
damit die eine Stelle, an der die Ortslisten gepflegt werden.

Bewusst ohne Datenbank und ohne Sprachmodell: Die Zuordnung muss auch dann
funktionieren, wenn das LLM nicht laeuft.
"""

import re
from typing import Optional

# Kerngebiet: Troisdorf und Siegburg. Siegburg zaehlt laut Einsatzerfahrung
# praktisch wie das eigene Stadtgebiet.
KERNGEBIET = ("troisdorf", "siegburg")

# Troisdorfer Stadtteile — eine Meldung ueber Sieglar oder Spich meint
# Troisdorf, auch wenn der Stadtname nicht faellt.
TROISDORFER_STADTTEILE = (
    "sieglar", "spich", "friedrich-wilhelms-huette", "friedrich wilhelms huette",
    "oberlar", "eschmar", "bergheim an der sieg", "muellekoven", "müllekoven",
    "kriegsdorf", "altenrath", "rotter see", "west troisdorf",
)

# Direkte Nachbarschaft: relevant, aber eine Stufe darunter.
# Schreibvarianten mitgefuehrt, weil Meldungen sie uneinheitlich schreiben.
NACHBARSCHAFT = (
    "niederkassel", "sankt augustin", "st. augustin", "st.augustin",
    "lohmar", "hennef",
    # Puetzchen gehoert zu Bonn, grenzt aber unmittelbar an Sankt Augustin.
    # Waehrend Puetzchens Markt stehen dort bis zu sechsstellige
    # Besucherzahlen, und es faehrt eine Sonderbuslinie aus Troisdorf.
    # Deshalb der Stadtteil ausdruecklich — nicht ganz Bonn.
    "pützchen", "puetzchen", "pützchens markt", "puetzchens markt",
)

# Uebriger Rhein-Sieg-Kreis
KREIS = (
    "rhein-sieg", "rhein sieg", "bornheim", "meckenheim", "rheinbach",
    "swisttal", "wachtberg", "alfter", "bad honnef", "koenigswinter",
    "königswinter", "much", "neunkirchen-seelscheid", "ruppichteroth",
    "eitorf", "windeck", "much", "siegburg-kaldauen",
)

# Gebiete, die Troisdorf als Teil einer groesseren Flaeche EINSCHLIESSEN.
# Das ist etwas anderes als "woanders": Eine Warnung fuer ganz Deutschland
# oder ganz NRW gilt auch hier. Genau diese Unterscheidung fehlte und liess
# am Bundesweiten Warntag die Einsatzerwartung bei "koennte was sein" stehen,
# obwohl eine Extremwarnung fuer das gesamte Bundesgebiet lief.
FLAECHIG = (
    "deutschland", "bundesrepublik", "bundesgebiet", "bundesweit",
    "nordrhein-westfalen", "nordrhein westfalen", "nrw",
    "regierungsbezirk köln", "regierungsbezirk koeln",
)

SCOPE_ORT = "troisdorf"
SCOPE_NACHBARSCHAFT = "nachbarschaft"
SCOPE_KREIS = "rhein_sieg"
SCOPE_FLAECHIG = "flaechendeckend"
SCOPE_AUSSERHALB = "ausserhalb"
SCOPE_UNBEKANNT = "unbekannt"

# Orte, die haeufig in regionalen Meldungen auftauchen, aber ausserhalb der
# Zustaendigkeit liegen. Nur zur ausdruecklichen Abgrenzung — ohne sie waere
# eine Koelner Meldung schlicht "unbekannt" statt "ausserhalb".
AUSSERHALB = (
    "köln", "koeln", "bonn", "düren", "dueren", "euskirchen", "leverkusen",
    "rhein-berg", "oberberg", "ahrweiler", "neuwied", "düsseldorf",
    "duesseldorf", "aachen", "wuppertal", "essen", "dortmund",
)


# Deutsche Ableitungsformen, die einem Ortsnamen folgen duerfen.
# "Troisdorfer Feuerwehr" und "Duerener Lagerhalle" sind in Schlagzeilen
# haeufiger als der blanke Ortsname — ohne diese Endungen bliebe die
# haeufigste Schreibweise unerkannt.
_ENDUNGEN = r"(?:s|er|ers|ern|erin|erinnen)?"


def _enthaelt(text: str, begriffe) -> Optional[str]:
    """Sucht Ortsnamen als ganze Woerter, mit deutschen Ableitungsformen.

    Vorne bleibt die Wortgrenze streng: Sonst wuerde "Abonnement" als "Bonn"
    gelesen. Hinten sind nur die bekannten Endungen erlaubt, keine beliebigen
    Buchstaben — sonst traefe jeder laengere Wortbestandteil.
    """
    for begriff in begriffe:
        muster = rf"(?<![a-zäöüß]){re.escape(begriff)}{_ENDUNGEN}(?![a-zäöüß])"
        if re.search(muster, text):
            return begriff
    return None


def detect_scope(*texte: str) -> dict:
    """Ordnet einen Meldungstext einer Relevanzzone zu.

    Liefert ``scope`` und den gefundenen ``ort``. Die Reihenfolge der Pruefung
    ist die Reihenfolge der Naehe: Wird Troisdorf UND Koeln genannt, gewinnt
    Troisdorf — die naehere Zustaendigkeit ist die massgebliche.
    """
    text = " ".join(t for t in texte if t).lower()
    if not text.strip():
        return {"scope": SCOPE_UNBEKANNT, "ort": None}

    # Flaechenlagen zuerst: Sie schlagen jede engere Zuordnung, weil sie
    # ohnehin alles darunter einschliessen.
    treffer = _enthaelt(text, FLAECHIG)
    if treffer:
        return {"scope": SCOPE_FLAECHIG, "ort": _schoen(treffer)}

    treffer = _enthaelt(text, KERNGEBIET)
    if treffer:
        return {"scope": SCOPE_ORT, "ort": treffer.capitalize()}

    treffer = _enthaelt(text, TROISDORFER_STADTTEILE)
    if treffer:
        # Ein Stadtteil ist Troisdorf, auch wenn der Stadtname fehlt
        return {"scope": SCOPE_ORT, "ort": f"Troisdorf-{treffer.capitalize()}"}

    treffer = _enthaelt(text, NACHBARSCHAFT)
    if treffer:
        return {"scope": SCOPE_NACHBARSCHAFT, "ort": _schoen(treffer)}

    treffer = _enthaelt(text, KREIS)
    if treffer:
        return {"scope": SCOPE_KREIS, "ort": _schoen(treffer)}

    treffer = _enthaelt(text, AUSSERHALB)
    if treffer:
        return {"scope": SCOPE_AUSSERHALB, "ort": _schoen(treffer)}

    return {"scope": SCOPE_UNBEKANNT, "ort": None}


def _schoen(key: str) -> str:
    """Anzeigename — "sankt augustin" wird zu "Sankt Augustin"."""
    return " ".join(teil.capitalize() for teil in key.split())


def is_local(*texte: str) -> bool:
    """Betrifft die Meldung das Kerngebiet oder die direkte Nachbarschaft?"""
    return detect_scope(*texte)["scope"] in (SCOPE_ORT, SCOPE_NACHBARSCHAFT)


def covers_troisdorf(*texte: str) -> bool:
    """Schliesst das genannte Gebiet Troisdorf ein?

    Wahr fuer das Kerngebiet selbst und fuer jede Flaechenlage, die Troisdorf
    umfasst — Deutschland, NRW, Regierungsbezirk Koeln. Falsch fuer Gebiete,
    die woanders liegen.
    """
    return detect_scope(*texte)["scope"] in (SCOPE_ORT, SCOPE_FLAECHIG)
