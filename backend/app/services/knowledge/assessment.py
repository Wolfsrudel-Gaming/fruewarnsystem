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

from app.services.knowledge.geo import (
    KERNGEBIET, NACHBARSCHAFT, SCOPE_AUSSERHALB, SCOPE_FLAECHIG, SCOPE_KREIS,
    SCOPE_NACHBARSCHAFT, SCOPE_ORT, detect_scope,
)

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
    # Frueher 0.6. Das war der Versuch, "Warnung fuer woanders" schon im
    # Gewicht abzufangen — und traf damit auch jede Warnung, die uns wirklich
    # betrifft. Die Ortsfrage klaert jetzt allein der Ortsfaktor; eine
    # amtliche Warnung UEBER UNS ist das autoritativste Signal ueberhaupt.
    "official_warning": 1.0,
    "traffic": 0.55,       # zuerst Rettungsdienst; Verpflegung erst bei Dauer
    "health": 0.5,         # kein Rettungsdienststandort
    "air_quality": 0.4,
    "seismic": 0.4,
    "shipping": 0.3,
}
DEFAULT_BEZUG = 0.5

# Einsatzbezug waehrend erhoehter Wachsamkeit — also solange eine Grosslage in
# erreichbarer Naehe laeuft (siehe grosslagen.py).
#
# Der Grund ist nicht, dass alles gefaehrlicher waere. Es ist, dass sich die
# ART der Lage aendert:
#
# Ein Massenanfall auf einem Volksfest mit einer Million Besuchern ist fuer
# Troisdorf KEINE rettungsdienstliche Lage — dafuer ist der Standort nicht da.
# Er ist eine BETREUUNGS-Grosslage: Tausende Unverletzte, Getrennte,
# Evakuierte, die versorgt werden muessen. Genau dafuer gibt es den
# Betreuungsplatz 500 und die Kueche. Die uebliche Daempfung von "manv"
# ("wir sind kein Rettungsdienststandort") trifft hier also nicht zu.
#
# Dasselbe gilt fuer Verkehr (Massenabfluss, blockierte Rettungswege) und
# Veranstaltungen selbst.
EINSATZBEZUG_WACHSAM = {
    "manv": 1.0,       # Betreuungslage, nicht Rettungsdienstlage
    "events": 0.9,     # die Veranstaltung ist jetzt der Schauplatz
    "traffic": 0.75,   # Massenabfluss, Sperrungen, Rettungswege
    "health": 0.65,    # Regelrettungsdienst ist gebunden
}


def einsatzbezug_fuer(cat: str, wachsam: bool = False) -> float:
    """Einsatzbezug einer Kategorie, ggf. im Kontext einer Grosslage."""
    if wachsam and cat in EINSATZBEZUG_WACHSAM:
        return EINSATZBEZUG_WACHSAM[cat]
    return EINSATZBEZUG.get(cat, DEFAULT_BEZUG)

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
ORTSFAKTOR_NACHBARSCHAFT = 0.92
ORTSFAKTOR_ORT = 1.0

# KERNGEBIET und NACHBARSCHAFT stammen aus services/knowledge/geo.py —
# dort werden die Ortslisten gepflegt, damit Nachrichtenbewertung und
# Einsatzerwartung nie auseinanderlaufen.

# Woran eine Evakuierung im Text zu erkennen ist. Bewusst knapp gehalten:
# jeder zusaetzliche Begriff erhoeht die Zahl der Fehltreffer.
EVAKUIERUNGS_BEGRIFFE = (
    "evakuier", "evakuation", "raeumung", "räumung", "geraeumt", "geräumt",
    "entschaerf", "entschärf", "bombenfund",
)

# Eine erkannte Evakuierung im Kerngebiet hebt die Bewertung auf mindestens
# diesen Wert — laut Einsatzerfahrung ist der Einsatz dann nahezu sicher.
EVAKUIERUNG_MINDESTWERT = 82.0

# In der direkten Nachbarschaft ist eine Evakuierung ein deutlicher Hinweis,
# aber keine Gewissheit. ANNAHME, nicht aus der Einheit bestaetigt: eine Stufe
# unter dem Kerngebiet. Bei gegenteiliger Erfahrung anzupassen.
EVAKUIERUNG_MINDESTWERT_NACHBARSCHAFT = 66.0

# Untergrenzen der abgeleiteten Signale (siehe services/knowledge/signals.py).
# Kampfmittel liegt auf Hoehe der Evakuierung — es ist derselbe Vorgang, nur
# frueher erkannt. Verpflegungsbedarf und Kombilage heben auf Bereitstellung,
# nicht auf Einsatz: Sie sagen, dass es eng werden kann, nicht dass es eng ist.
SIGNAL_MINDESTWERT = {
    # Eine amtliche Extremwarnung fuer das ganze Bundesgebiet ist die
    # deutlichste Lage, die es gibt. Ausserhalb von Probealarmen bedeutet sie
    # eine reale, grossflaechige Gefahr — da haelt sich das Fruehwarnsystem
    # nicht mehr zurueck.
    "flaechenlage": 96.0,
    "kampfmittel": 82.0,
    "verpflegungsbedarf": 68.0,
    "kombilage": 62.0,
}

# Wie oft das Land das in Troisdorf stationierte Betreuungsgespann tatsaechlich
# gezogen hat: zuletzt beim Ahrhochwasser 2021, davor ein- bis zweimal in sehr
# grossen Abstaenden. Grob einmal pro Jahrzehnt. Diese Grundrate ist der Grund,
# warum ueberoertliche Lagen stark gedaempft werden — sie sind real, aber als
# Alltagserwartung falsch.
LANDESALARMIERUNG_HINWEIS = (
    "Eine Landesalarmierung des Betreuungsgespanns kam zuletzt beim "
    "Ahrhochwasser 2021 vor, davor nur ein- bis zweimal in sehr grossen "
    "Abstaenden — als Alltagserwartung also praktisch auszuschliessen."
)

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
    ein Ort aus dem Kerngebiet oder der direkten Nachbarschaft. Ein Bombenfund
    in Koeln loest damit nichts aus.

    Das Kerngebiet hat Vorrang: Wird in einem Text sowohl Siegburg als auch
    Lohmar genannt, zaehlt Siegburg.
    """
    treffer_nachbarschaft = None
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
            return {"category": cat, "ort": _ortsname(ort), "zone": "kerngebiet"}
        nachbar = next((o for o in NACHBARSCHAFT if o in text), None)
        if nachbar and treffer_nachbarschaft is None:
            treffer_nachbarschaft = {
                "category": cat, "ort": _ortsname(nachbar), "zone": "nachbarschaft",
            }
    return treffer_nachbarschaft


def _ortsname(key: str) -> str:
    """Schreibweise fuer die Anzeige — "sankt augustin" wird zu "Sankt Augustin"."""
    return " ".join(teil.capitalize() for teil in key.split())


def _ortsfaktor(cat: str, data: dict) -> float:
    """Wie ortsnah ist das, was diese Kategorie meldet?

    Behoerdliche Warnungen und Nachrichten brauchen die Unterscheidung, weil
    beide ueberregional berichten. Der Stromkollektor bringt seine Zonenlogik
    selbst mit und liefert sie als ``primary_condition``.
    """
    if cat in ("official_warning", "news"):
        bereich = (data.get("area_scope") or data.get("scope") or "").lower()
        if bereich in (SCOPE_ORT, SCOPE_FLAECHIG, "lokal", "ort"):
            # Flaechendeckend heisst "auch hier" — nicht "woanders".
            return ORTSFAKTOR_ORT
        if bereich in (SCOPE_NACHBARSCHAFT, "nachbar"):
            return ORTSFAKTOR_NACHBARSCHAFT
        if bereich in (SCOPE_KREIS, "kreis", "region"):
            return ORTSFAKTOR_KREIS
        if bereich in (SCOPE_AUSSERHALB, "extern", "bundesweit"):
            return ORTSFAKTOR_AUSSERHALB
        # Ohne ausdrueckliche Angabe den Text selbst auswerten.
        erkannt = detect_scope(_lagetext(data))["scope"]
        if erkannt in (SCOPE_ORT, SCOPE_FLAECHIG):
            return ORTSFAKTOR_ORT
        if erkannt == SCOPE_NACHBARSCHAFT:
            return ORTSFAKTOR_NACHBARSCHAFT
        if erkannt == SCOPE_AUSSERHALB:
            return ORTSFAKTOR_AUSSERHALB
        # Bleibt der Ort unklar, konservativ auf Kreisebene: nicht ignorieren,
        # aber auch nicht wie eine Lage vor der Haustuer behandeln.
        return ORTSFAKTOR_KREIS
    if cat == "power":
        bedingung = (data.get("primary_condition") or "").lower()
        if bedingung == "extremlage_ausserhalb":
            return ORTSFAKTOR_AUSSERHALB
        if bedingung == "grosslage_kreis":
            return ORTSFAKTOR_KREIS
    return ORTSFAKTOR_ORT


def einsatzgewichteter_score(cat: str, data: dict,
                             wachsam: bool = False) -> float:
    """Score einer Kategorie, uebersetzt in Einsatzrelevanz fuer Troisdorf."""
    score = float(data.get("score", 0) or 0)
    return score * einsatzbezug_fuer(cat, wachsam) * _ortsfaktor(cat, data)


def _stufe_fuer(wert: float) -> tuple:
    for schwelle, key, label, beschreibung in STUFEN:
        if wert >= schwelle:
            return key, label, beschreibung
    return STUFEN[-1][1], STUFEN[-1][2], STUFEN[-1][3]


def assess_deployment(scores: dict, kategorie_labels: Optional[dict] = None,
                      tag=None) -> dict:
    """Einsatzerwartung aus den aktuellen Risikoscores ableiten.

    Liefert die Stufe, den treibenden Anlass, die voraussichtlich gebrauchten
    Komponenten des Standorts und eine nachvollziehbare Begruendung. Bewusst
    getrennt vom Gesamtrisiko: Das Gesamtrisiko beschreibt die Lage, die
    Einsatzerwartung ihre Folgen fuer die eigene Bereitschaft. Beides kann
    auseinanderfallen — genau das war der Fall Dueren.
    """
    from app.services.knowledge.grosslagen import wachsamkeitsstufe

    labels = kategorie_labels or {}
    wachsamkeit = wachsamkeitsstufe(tag)
    wachsam = wachsamkeit["stufe"] != "normal"

    gewichtet = {}
    for cat, data in scores.items():
        if cat == "overall" or not isinstance(data, dict):
            continue
        gewichtet[cat] = einsatzgewichteter_score(cat, data, wachsam)

    if not gewichtet:
        key, label, beschreibung = _stufe_fuer(0)
        return {
            "level": key, "label": label, "description": beschreibung,
            "value": 0.0, "driver": None, "driver_label": None,
            "driver_score": 0.0, "contributing": [], "components": [],
            "reasons": [], "evacuation": None, "signals": [],
            "vigilance": wachsamkeit, "lead_time": VORLAUF,
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
    bezug = einsatzbezug_fuer(driver, wachsam)
    orts = _ortsfaktor(driver, scores.get(driver) or {})

    reasons.append(
        f"{driver_label} steht bei {roh:.0f}/100 und ist damit der treibende Anlass."
    )
    if wachsam and driver in EINSATZBEZUG_WACHSAM:
        normal = EINSATZBEZUG.get(driver, DEFAULT_BEZUG)
        if bezug > normal:
            reasons.append(
                f"Waehrend der laufenden Grosslage zaehlt {driver_label} "
                f"staerker ({normal:.0%} auf {bezug:.0%}): Ein Massenanfall "
                f"auf einer Grossveranstaltung ist fuer Troisdorf vor allem "
                f"eine Betreuungslage — Tausende Unverletzte und Getrennte, "
                f"die versorgt werden muessen."
            )
    elif bezug < 1.0:
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
    # Bei ueberoertlichen Lagen die Grundrate nennen. Ohne diesen Hinweis liest
    # sich ein hoher Wert als Alltagserwartung, obwohl die Landesalarmierung
    # historisch etwa einmal pro Jahrzehnt vorkommt.
    if _ortsfaktor(driver, scores.get(driver) or {}) <= ORTSFAKTOR_AUSSERHALB:
        reasons.append(LANDESALARMIERUNG_HINWEIS)

    # Abgeleitete Signale: Konstellationen, die erfahrungsgemaess zum Einsatz
    # fuehren, ohne dass ein einzelner Score dafuer hoch genug waere.
    from app.services.knowledge.signals import alle_signale
    signale = alle_signale(scores, tag=tag)
    for signal in signale:
        untergrenze = SIGNAL_MINDESTWERT.get(signal["kind"])
        if untergrenze:
            wert = max(wert, untergrenze)

    # Rueckwaerts einfuegen, damit die Reihenfolge erhalten bleibt: Jedes
    # insert(0) draengt das Vorige nach hinten, ein Vorwaertslauf wuerde die
    # Liste also umdrehen und das wichtigste Signal ans Ende stellen.
    for signal in reversed(signale):
        reasons.insert(0, signal["hinweis"])

    # Nach den Signalen eingefuegt, damit der Evakuierungshinweis ganz oben
    # steht — er ist der unmittelbarste Anlass, den es gibt.
    evakuierung = evakuierungshinweis(scores)
    if evakuierung:
        im_kerngebiet = evakuierung.get("zone") == "kerngebiet"
        mindestwert = (EVAKUIERUNG_MINDESTWERT if im_kerngebiet
                       else EVAKUIERUNG_MINDESTWERT_NACHBARSCHAFT)
        wert = max(wert, mindestwert)
        if im_kerngebiet:
            reasons.insert(0, (
                f"Hinweis auf eine Evakuierung in {evakuierung['ort']}. Bei "
                f"Evakuierungen im Kerngebiet geht Troisdorf erfahrungsgemaess "
                f"in den Einsatz — Betreuung und Verpflegung der Evakuierten."
            ))
        else:
            reasons.insert(0, (
                f"Hinweis auf eine Evakuierung in {evakuierung['ort']} — "
                f"direkte Nachbarschaft, eine Stufe unter dem Kerngebiet."
            ))

    key, label, beschreibung = _stufe_fuer(wert)

    komponenten = []
    quellen = [driver] + nebenlagen
    if evakuierung or any(s["kind"] == "kampfmittel" for s in signale):
        komponenten.extend(KOMPONENTEN_EVAKUIERUNG)
    if any(s["kind"] == "verpflegungsbedarf" for s in signale):
        for komp in ("Verpflegung (Kuechenanhaenger/Feldkueche)",):
            if komp not in komponenten:
                komponenten.insert(0, komp)
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
        "signals": signale,
        "vigilance": wachsamkeit,
        "lead_time": VORLAUF,
    }
