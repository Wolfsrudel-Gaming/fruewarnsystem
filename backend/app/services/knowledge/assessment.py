"""Von der Messlage zur Einsatzerwartung.

Das System kann bisher sagen: "Wetter 82, Strom 40." Was es nicht sagen kann:
ob daraus fuer die Bereitschaft in Troisdorf etwas folgt. Genau das ist die
Frage, auf die es ankommt.

Dieses Modul uebersetzt die Risikoscores in eine Einsatzerwartung, und zwar
entlang dessen, was im Rettungsdienstbedarfsplan tatsaechlich steht:

* Nicht jede Kategorie fuehrt gleich schnell zu einem DRK-Einsatz. Eine
  Hochwasserlage bindet den Betreuungsdienst unmittelbar, eine Erdbebenmeldung
  aus der Eifel praktisch nie. Das bildet ``EINSATZBEZUG`` ab.
* Behoerdliche Warnungen sind der Sonderfall: NINA warnt bundesweit. Eine
  Warnung fuer einen anderen Kreis ist fuer Troisdorf erst ab
  UEMANV-Groessenordnung relevant. Das war der Fall "Brand in Dueren" — die
  Lage war real, die Folgerung fuer Troisdorf trotzdem nicht "sicherer
  Einsatz".
* Der Bedarfsplan kennt zwei Vorlaufzeiten: Sonderbedarf mit 24 Stunden bei
  angekuendigten Wetterlagen, Spitzenbedarf mit 30 bis 60 Minuten bei
  ploetzlichen Lagen. Danach richtet sich, was ueberhaupt sinnvoll vorhersagbar
  ist.

Die Bewertung ist bewusst eine reine Funktion ohne Datenbankzugriff, damit sie
pruefbar bleibt.
"""

from typing import Optional

# Wie direkt eine Kategorie auf einen Einsatz der Bereitschaft durchschlaegt.
# Abgeleitet aus den Aufgaben, die der Bedarfsplan den Hilfsorganisationen
# zuweist: Betreuungsdienst, Sanitaetsdienst, Einsatzeinheiten.
EINSATZBEZUG = {
    "manv": 1.0,           # der Einsatzfall schlechthin
    "water": 1.0,          # Evakuierung und Betreuung, Kernaufgabe
    "radiation": 1.0,      # CBRN, sicherheitskritisch — nie abwerten
    "weather": 0.9,        # Sonderbedarf ausdruecklich im Bedarfsplan
    "power": 0.9,          # Betreuungsplatz, Pflegeeinrichtungen
    "fire": 0.8,           # Verpflegung Einsatzkraefte, Evakuierung
    "health": 0.7,         # Systemauslastung senkt die Eskalationsschwelle
    "traffic": 0.7,        # A59, A560, ICE-Strecke, Flughafen Koeln/Bonn
    "official_warning": 0.6,  # ortsabhaengig, siehe _ortsfaktor
    "events": 0.6,         # planbar, meist Sanitaetsdienst
    "air_quality": 0.5,
    "seismic": 0.4,
    "shipping": 0.3,
    "news": 0.3,           # Indiz, nie Grund
}
DEFAULT_BEZUG = 0.5

# Schwellen der Einsatzerwartung, angewandt auf den einsatzgewichteten Score.
STUFEN = [
    (80.0, "einsatz_wahrscheinlich",
     "Einsatz wahrscheinlich",
     "Die Lage entspricht dem, was im Bedarfsplan zusaetzliche Kraefte "
     "ausloest. Mit Alarmierung ist zu rechnen."),
    (65.0, "bereitstellung_wahrscheinlich",
     "Bereitstellung wahrscheinlich",
     "Kraefte werden voraussichtlich in Bereitstellung versetzt, bevor ein "
     "konkreter Einsatzauftrag kommt."),
    (50.0, "bereitstellung_moeglich",
     "Bereitstellung moeglich",
     "Die Lage kann kippen. Erreichbarkeit sicherstellen, Material pruefen."),
    (30.0, "beobachtung",
     "Beobachtung",
     "Auffaellige Lage ohne unmittelbare Folgen fuer die Bereitschaft."),
    (0.0, "ruhe",
     "Ruhe",
     "Keine Hinweise auf bevorstehende Kraeftebindung."),
]

# Ab diesem Wert gilt eine Kategorie als mitverschaerfend
NEBENLAGE_SCHWELLE = 45.0

# Behoerdliche Warnungen ausserhalb des eigenen Kreises zaehlen nur gedaempft.
# Grundlage: UEMANV wird erst angefordert, wenn der betroffene Kreis seine
# eigenen Mittel erschoepft hat.
ORTSFAKTOR_AUSSERHALB = 0.45
ORTSFAKTOR_KREIS = 0.85
ORTSFAKTOR_ORT = 1.0

# Welche DRK-Komponenten bei welcher Kategorie typischerweise gebraucht werden
KOMPONENTEN = {
    "water": ["Betreuungsdienst", "Technik und Sicherheit", "Einsatzeinheit"],
    "power": ["Betreuungsdienst", "Technik und Sicherheit"],
    "weather": ["Betreuungsdienst", "Technik und Sicherheit"],
    "fire": ["Betreuungsdienst (Verpflegung Einsatzkraefte)", "Sanitaetsdienst"],
    "manv": ["Sanitaetsdienst", "Einsatzeinheit", "FB HiOrg", "ELW 1 RD"],
    "traffic": ["Sanitaetsdienst", "Einsatzeinheit"],
    "health": ["Sanitaetsdienst"],
    "events": ["Sanitaetsdienst"],
    "radiation": ["CBRN-Schutz", "Betreuungsdienst"],
    "official_warning": ["Betreuungsdienst", "Sanitaetsdienst"],
}

# Vorlaufzeiten aus dem Bedarfsplan
VORLAUF = {
    "sonderbedarf_stunden": 24,
    "spitzenbedarf_minuten_regel": 30,
    "spitzenbedarf_minuten_spaet": 60,
    "fb_hiorg_minuten": 45,
}


def _ortsfaktor(cat: str, data: dict) -> float:
    """Wie ortsnah ist das, was diese Kategorie meldet?

    Nur behoerdliche Warnungen brauchen die Unterscheidung — alle anderen
    Kollektoren erfassen ohnehin nur die Region. Der Stromkollektor bringt
    seine Zonenlogik selbst mit und liefert sie als ``primary_condition``.
    """
    if cat == "official_warning":
        bereich = (data.get("area_scope") or data.get("scope") or "").lower()
        if bereich in ("troisdorf", "lokal", "ort"):
            return ORTSFAKTOR_ORT
        if bereich in ("rhein_sieg", "kreis", "region"):
            return ORTSFAKTOR_KREIS
        if bereich in ("ausserhalb", "extern", "bundesweit"):
            return ORTSFAKTOR_AUSSERHALB
        # Ohne Angabe konservativ auf Kreisebene einordnen: nicht ignorieren,
        # aber auch nicht wie eine Lage vor der Haustuer behandeln.
        return ORTSFAKTOR_KREIS
    if cat == "power":
        bedingung = (data.get("primary_condition") or "").lower()
        if bedingung == "extremlage_ausserhalb":
            return ORTSFAKTOR_AUSSERHALB
        if bedingung == "grosslage_kreis":
            return ORTSFAKTOR_KREIS
    return ORTSFAKTOR_ORT


def einsatzgewichteter_score(cat: str, data: dict) -> float:
    """Score einer Kategorie, uebersetzt in Einsatzrelevanz fuer Troisdorf."""
    score = float(data.get("score", 0) or 0)
    bezug = EINSATZBEZUG.get(cat, DEFAULT_BEZUG)
    return score * bezug * _ortsfaktor(cat, data)


def _stufe_fuer(wert: float) -> tuple:
    for schwelle, key, label, beschreibung in STUFEN:
        if wert >= schwelle:
            return key, label, beschreibung
    return STUFEN[-1][1], STUFEN[-1][2], STUFEN[-1][3]


def assess_deployment(scores: dict, kategorie_labels: Optional[dict] = None) -> dict:
    """Einsatzerwartung aus den aktuellen Risikoscores ableiten.

    Liefert die Stufe, den treibenden Anlass, die voraussichtlich gebrauchten
    DRK-Komponenten und eine nachvollziehbare Begruendung. Bewusst getrennt
    vom Gesamtrisiko: Das Gesamtrisiko beschreibt die Lage, die Einsatzerwartung
    beschreibt die Folgen fuer die eigene Bereitschaft. Beides kann
    auseinanderfallen — genau das war der Fall Dueren.
    """
    labels = kategorie_labels or {}
    gewichtet = {}
    for cat, data in scores.items():
        if cat == "overall" or not isinstance(data, dict):
            continue
        gewichtet[cat] = einsatzgewichteter_score(cat, data)

    if not gewichtet:
        key, label, beschreibung = _stufe_fuer(0)
        return {
            "level": key, "label": label, "description": beschreibung,
            "value": 0.0, "driver": None, "driver_label": None,
            "contributing": [], "components": [], "reasons": [],
            "lead_time": VORLAUF,
        }

    driver = max(gewichtet, key=lambda c: gewichtet[c])
    wert = gewichtet[driver]

    # Mehrere gleichzeitig erhoehte Kategorien verschaerfen die Lage. Der
    # Zuschlag bleibt klein — er soll eine Stufe anheben koennen, nicht zwei.
    nebenlagen = [
        c for c, v in gewichtet.items()
        if c != driver and v >= NEBENLAGE_SCHWELLE
    ]
    wert = min(100.0, wert + 4.0 * len(nebenlagen))

    key, label, beschreibung = _stufe_fuer(wert)

    komponenten = []
    for cat in [driver] + nebenlagen:
        for komp in KOMPONENTEN.get(cat, []):
            if komp not in komponenten:
                komponenten.append(komp)

    reasons = []
    roh = float((scores.get(driver) or {}).get("score", 0) or 0)
    driver_label = labels.get(driver, driver)
    bezug = EINSATZBEZUG.get(driver, DEFAULT_BEZUG)
    orts = _ortsfaktor(driver, scores.get(driver) or {})

    reasons.append(
        f"{driver_label} steht bei {roh:.0f}/100 und ist damit der treibende Anlass."
    )
    if bezug < 1.0:
        reasons.append(
            f"Der Einsatzbezug dieser Kategorie ist {bezug:.0%} — sie fuehrt "
            f"seltener unmittelbar zu einer Alarmierung der Bereitschaft."
        )
    if orts < 1.0:
        reasons.append(
            f"Die Lage ist nicht ortsnah ({orts:.0%} Ortsbezug). Ausserhalb des "
            f"Kreises wird erst ab UEMANV-Groessenordnung angefordert."
        )
    if nebenlagen:
        namen = ", ".join(labels.get(c, c) for c in nebenlagen[:3])
        reasons.append(f"Gleichzeitig erhoeht: {namen}.")

    return {
        "level": key,
        "label": label,
        "description": beschreibung,
        "value": round(wert, 1),
        "driver": driver,
        "driver_label": driver_label,
        "driver_score": roh,
        "contributing": nebenlagen,
        "components": komponenten,
        "reasons": reasons,
        "lead_time": VORLAUF,
    }
