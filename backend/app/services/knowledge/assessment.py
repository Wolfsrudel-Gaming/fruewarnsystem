"""Von der Messlage zur Einsatzerwartung des DRK Troisdorf.

Das System kann sagen: "Wetter 82, Strom 40." Was daraus fuer die Bereitschaft
folgt, steht hier — und das haengt weniger an der Schwere der Lage als am
Einsatzprofil des Standorts.

DAS PROFIL BESTIMMT DIE GEWICHTE
--------------------------------
Troisdorf ist vorrangig VERPFLEGUNGSSTANDORT, dazu Betreuungsstandort, und
ausdruecklich kein Rettungsdienststandort. Daraus folgt eine Bewertung, die
sich deutlich von der eines Rettungsdienststandorts unterscheidet:

* Massgeblich ist nicht, ob Verletzte zu erwarten sind, sondern ob ueber
  laengere Zeit Menschen versorgt werden muessen — Einsatzkraefte oder
  Betroffene. Eine Lage mit zehn Verletzten und zwei Stunden Dauer ist fuer
  Troisdorf weniger relevant als ein Grossbrand ueber drei Schichten.
* NACHRICHTEN sind der staerkste Fruehindikator. Das ist kein Zufall: Was
  Verpflegung braucht, dauert lange und bindet viele Kraefte — und genau
  darueber wird berichtet. Ein fruehes Modell hatte Nachrichten als "Indiz,
  nie Grund" abgewertet; das war nach der Erfahrung der Einheit falsch.
* EVAKUIERUNGEN in Troisdorf oder Siegburg bedeuten praktisch sicher Einsatz.
  Hier ist keine Abwaegung noetig, deshalb gibt es dafuer einen eigenen Pfad.
* Die Kategorie "Waldbrand" misst den GEFAHRENINDEX des DWD, nicht ein
  laufendes Feuer. Sie ist Vorbote, nicht Ereignis — echte Brandereignisse
  erreichen das System ueber Nachrichten und behoerdliche Warnungen.

Behoerdliche Warnungen bleiben ortsabhaengig gedaempft: NINA warnt bundesweit,
und ausserhalb des Kreises wird erst ab UEMANV-Groessenordnung angefordert.

Die Bewertung ist eine reine Funktion ohne Datenbankzugriff, damit sie
pruefbar bleibt.
"""

from typing import Optional

# Wie direkt eine Kategorie auf einen Einsatz der Bereitschaft Troisdorf
# durchschlaegt. Abgeleitet aus dem Einsatzprofil des Standorts, nicht aus
# der allgemeinen Schwere der Gefahr.
EINSATZBEZUG = {
    # Betreuung und Verpflegung ueber laengere Zeit — Kernaufgaben
    "water": 1.0,          # Hochwasser: Evakuierung, Betreuung, Verpflegung
    "radiation": 1.0,      # CBRN, sicherheitskritisch — nie abwerten
    "news": 1.0,           # staerkster Fruehindikator laut Einsatzerfahrung —
                           # der Ortsfaktor daempft die ueberregionale Streuung
    "power": 0.9,          # Betreuungsplatz, Pflegeeinrichtungen
    "weather": 0.9,        # Sonderbedarf ausdruecklich im Bedarfsplan
    "fire": 0.85,          # Gefahrenindex als Vorbote von Verpflegungslagen
    "manv": 0.75,          # Troisdorf wirkt mit, stellt aber keinen RD
    "events": 0.7,         # Sanitaetsdienst, auch in Nachbargemeinden
    "official_warning": 0.6,  # ortsabhaengig, siehe _ortsfaktor
    "traffic": 0.55,       # zuerst Rettungsdienst; Verpflegung erst bei Dauer
    "health": 0.5,         # kein Rettungsdienststandort
    "air_quality": 0.4,
    "seismic": 0.4,
    "shipping": 0.3,
}
DEFAULT_BEZUG = 0.5

# Schwellen der Einsatzerwartung, angewandt auf den einsatzgewichteten Score.
STUFEN = [
    (80.0, "einsatz_wahrscheinlich",
     "Einsatz wahrscheinlich",
     "Die Lage entspricht dem, was Verpflegung oder Betreuung bindet. "
     "Mit Alarmierung ist zu rechnen."),
    (65.0, "bereitstellung_wahrscheinlich",
     "Bereitstellung wahrscheinlich",
     "Kraefte werden voraussichtlich in Bereitstellung versetzt, bevor ein "
     "konkreter Einsatzauftrag kommt."),
    (50.0, "bereitstellung_moeglich",
     "Bereitstellung moeglich",
     "Die Lage kann kippen. Erreichbarkeit sicherstellen, Kueche und "
     "Fahrzeuge pruefen."),
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

# Kerngebiet der Einheit. Siegburg zaehlt wie das eigene Stadtgebiet — die
# Naehe und die eingespielte Zusammenarbeit machen den Unterschied.
KERNGEBIET = ("troisdorf", "siegburg")

# Woran eine Evakuierung im Text zu erkennen ist. Bewusst knapp gehalten:
# jeder zusaetzliche Begriff erhoeht die Zahl der Fehltreffer.
EVAKUIERUNGS_BEGRIFFE = (
    "evakuier", "evakuation", "raeumung", "räumung", "geraeumt", "geräumt",
    "entschaerf", "entschärf", "bombenfund",
)

# Eine erkannte Evakuierung im Kerngebiet hebt die Bewertung auf mindestens
# diesen Wert — laut Einsatzerfahrung ist der Einsatz dann nahezu sicher.
EVAKUIERUNG_MINDESTWERT = 82.0

# Welche Komponenten des Standorts bei welcher Kategorie typischerweise
# gebraucht werden. Verpflegung steht vorn, weil sie den Standort ausmacht.
KOMPONENTEN = {
    "fire": ["Verpflegung (Kuechenanhaenger/Feldkueche)", "Betreuungsdienst"],
    "water": ["Betreuungsdienst", "Verpflegung", "Betreuungsgespann",
              "Techniktrupp"],
    "power": ["Betreuungsdienst", "Verpflegung", "Techniktrupp"],
    "weather": ["Verpflegung", "Betreuungsdienst"],
    "manv": ["Betreuungsdienst", "Verpflegung", "Einsatzeinheit"],
    "news": ["Verpflegung", "Betreuungsdienst"],
    "traffic": ["Verpflegung (bei laengerer Einsatzdauer)"],
    "events": ["Sanitaetsdienst"],
    "radiation": ["CBRN-Schutz", "Betreuungsdienst", "Verpflegung"],
    "official_warning": ["Betreuungsdienst", "Verpflegung"],
    "health": ["Sanitaetsdienst"],
}

# Bei einer Evakuierung immer diese Komponenten
KOMPONENTEN_EVAKUIERUNG = ["Betreuungsdienst", "Verpflegung",
                           "Betreuungsgespann"]

# Vorlaufzeiten aus dem Bedarfsplan
VORLAUF = {
    "sonderbedarf_stunden": 24,
    "spitzenbedarf_minuten_regel": 30,
    "spitzenbedarf_minuten_spaet": 60,
    "fb_hiorg_minuten": 45,
}


def _lagetext(data: dict) -> str:
    """Freitext einer Kategorie, in dem nach Hinweisen gesucht wird."""
    teile = [
        data.get("detail", ""),
        data.get("primary_condition", ""),
        data.get("area", ""),
        data.get("area_scope", ""),
    ]
    for beitrag in (data.get("contributions") or [])[:10]:
        if isinstance(beitrag, dict):
            teile.append(str(beitrag.get("reason", "")))
            teile.append(str(beitrag.get("source", "")))
    return " ".join(str(t) for t in teile if t).lower()


def evakuierungshinweis(scores: dict) -> Optional[dict]:
    """Deutet etwas auf eine Evakuierung im Kerngebiet hin?

    Laut Einsatzerfahrung ist der Einsatz bei einer Evakuierung in Troisdorf
    oder Siegburg praktisch sicher — unabhaengig davon, wie hoch die Scores
    gerade stehen. Deshalb ein eigener Pfad statt einer Gewichtung.

    Verlangt werden BEIDE Hinweise im selben Text: ein Evakuierungsbegriff und
    ein Ort aus dem Kerngebiet. Ein Bombenfund in Koeln loest damit nichts aus.
    """
    for cat, data in scores.items():
        if cat == "overall" or not isinstance(data, dict):
            continue
        text = _lagetext(data)
        if not text:
            continue
        if not any(w in text for w in EVAKUIERUNGS_BEGRIFFE):
            continue
        ort = next((o for o in KERNGEBIET if o in text), None)
        if ort:
            return {"category": cat, "ort": ort.capitalize()}
    return None


def _ortsfaktor(cat: str, data: dict) -> float:
    """Wie ortsnah ist das, was diese Kategorie meldet?

    Behoerdliche Warnungen und Nachrichten brauchen die Unterscheidung, weil
    beide ueberregional berichten. Der Stromkollektor bringt seine Zonenlogik
    selbst mit und liefert sie als ``primary_condition``.
    """
    if cat in ("official_warning", "news"):
        bereich = (data.get("area_scope") or data.get("scope") or "").lower()
        if bereich in ("troisdorf", "lokal", "ort"):
            return ORTSFAKTOR_ORT
        if bereich in ("rhein_sieg", "kreis", "region"):
            return ORTSFAKTOR_KREIS
        if bereich in ("ausserhalb", "extern", "bundesweit"):
            return ORTSFAKTOR_AUSSERHALB
        # Ohne ausdrueckliche Angabe im Text nach Ortsnamen suchen. Nachrichten
        # ueber Troisdorf oder Siegburg wiegen deutlich schwerer als solche
        # ueber irgendwo.
        if any(o in _lagetext(data) for o in KERNGEBIET):
            return ORTSFAKTOR_ORT
        # Sonst konservativ auf Kreisebene: nicht ignorieren, aber auch nicht
        # wie eine Lage vor der Haustuer behandeln.
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
    Komponenten des Standorts und eine nachvollziehbare Begruendung. Bewusst
    getrennt vom Gesamtrisiko: Das Gesamtrisiko beschreibt die Lage, die
    Einsatzerwartung ihre Folgen fuer die eigene Bereitschaft. Beides kann
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
            "driver_score": 0.0, "contributing": [], "components": [],
            "reasons": [], "evacuation": None, "lead_time": VORLAUF,
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
            f"Der Einsatzbezug dieser Kategorie ist {bezug:.0%} — Troisdorf ist "
            f"Verpflegungs- und Betreuungsstandort, kein Rettungsdienststandort."
        )
    if orts < 1.0:
        reasons.append(
            f"Die Lage ist nicht ortsnah ({orts:.0%} Ortsbezug). Ausserhalb des "
            f"Kreises wird erst ab UEMANV-Groessenordnung angefordert."
        )
    if nebenlagen:
        namen = ", ".join(labels.get(c, c) for c in nebenlagen[:3])
        reasons.append(f"Gleichzeitig erhoeht: {namen}.")

    # Evakuierung im Kerngebiet uebersteuert die Rechnung. Sie ist kein
    # Zuschlag, sondern eine Untergrenze — laut Einsatzerfahrung ist der
    # Einsatz dann so gut wie sicher.
    evakuierung = evakuierungshinweis(scores)
    if evakuierung and wert < EVAKUIERUNG_MINDESTWERT:
        wert = EVAKUIERUNG_MINDESTWERT
    if evakuierung:
        reasons.insert(0, (
            f"Hinweis auf eine Evakuierung in {evakuierung['ort']}. Bei "
            f"Evakuierungen im Kerngebiet geht Troisdorf erfahrungsgemaess "
            f"in den Einsatz — Betreuung und Verpflegung der Evakuierten."
        ))

    key, label, beschreibung = _stufe_fuer(wert)

    komponenten = []
    quellen = [driver] + nebenlagen
    if evakuierung:
        komponenten.extend(KOMPONENTEN_EVAKUIERUNG)
    for cat in quellen:
        for komp in KOMPONENTEN.get(cat, []):
            if komp not in komponenten:
                komponenten.append(komp)

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
        "evacuation": evakuierung,
        "lead_time": VORLAUF,
    }
