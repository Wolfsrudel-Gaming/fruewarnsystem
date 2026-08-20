"""Abgeleitete Signale aus der Lage.

Die Kategorie-Scores sagen, wie hoch ein Risiko steht. Sie sagen nicht, ob
eine der Konstellationen vorliegt, die beim DRK Troisdorf erfahrungsgemaess
zum Einsatz fuehren. Genau die stehen hier — jede als eigene Funktion, jede
ohne Datenbankzugriff, damit sie pruefbar bleibt.

Drei Signale:

* KAMPFMITTEL — Bombenfund oder Entschaerfung im Kerngebiet. Zieht Betreuung
  und Verpflegung der Evakuierten nach sich, praktisch ohne Ausnahme.
* KOMBILAGE — eine Veranstaltung faellt mit einer Wetterlage zusammen. Dann
  steht bereits Personal vor Ort, und aus dem geplanten Sanitaetsdienst wird
  eine Schadenslage.
* VERPFLEGUNGSBEDARF — die Meldungen deuten auf eine lange Lage mit vielen
  gebundenen Kraeften. Das ist der haeufigste Einsatzanlass ueberhaupt.

Alle drei arbeiten auf Meldungstexten. Das ist bewusst so: Der zuverlaessigste
Vorbote eines Einsatzes ist nach Auskunft der Einheit die Presse, und was dort
steht, steht im Klartext — nicht in einer Kennzahl.
"""

import re
from typing import Optional

from app.services.knowledge.geo import (
    SCOPE_NACHBARSCHAFT, SCOPE_ORT, detect_scope,
)

# --- Kampfmittel -------------------------------------------------------------

KAMPFMITTEL_BEGRIFFE = (
    "bombenfund", "fliegerbombe", "kampfmittel", "blindgaenger", "blindgänger",
    "entschaerf", "entschärf", "sprengmeister", "kampfmittelbeseitigung",
    "weltkriegsbombe",
)

# --- Verpflegungsbedarf ------------------------------------------------------
# Schwellen aus der Einsatzerfahrung der Einheit.
#
# ANNAHME: Es reicht, wenn EINE der beiden Bedingungen zutrifft. Genannt wurden
# beide Werte einzeln, ohne Verknuepfung. "Eines reicht" warnt frueher — bei
# einem Verpflegungsstandort ist eine unnoetige Vorwarnung deutlich weniger
# schaedlich als eine verpasste Lage. Bei gegenteiliger Erfahrung anzupassen.
DAUER_SCHWELLE_STUNDEN = 2
KRAEFTE_SCHWELLE = 50

# Formulierungen, die auf eine lange Lage hindeuten. Bewusst knapp: Jeder
# weitere Begriff erhoeht die Zahl der Fehltreffer, und Fehltreffer kosten
# hier Glaubwuerdigkeit.
DAUER_BEGRIFFE = (
    "dauereinsatz", "grossbrand", "großbrand", "grosseinsatz", "großeinsatz",
    "seit stunden", "stundenlang", "die ganze nacht", "ueber nacht",
    "über nacht", "loescharbeiten dauern", "löscharbeiten dauern",
    "wird noch andauern", "mehrere stunden", "im vollbrand",
)

# Zahl vor einer Kraefte-Bezeichnung, z. B. "rund 120 Einsatzkraefte".
# Umlaut und Umschrift muessen beide treffen: Feeds schreiben mal "Kräfte",
# mal "Kraefte" — je nach Zeichensatz der Quelle.
_AE = r"(?:ä|ae|a)"
_KRAEFTE_MUSTER = re.compile(
    rf"(\d{{1,4}})\s*(?:einsatzkr{_AE}ften?|feuerwehrleute|"
    rf"kr{_AE}ften?|helfer(?:innen)?)",
    re.IGNORECASE,
)

# Stundenangabe, z. B. "seit 5 Stunden"
_STUNDEN_MUSTER = re.compile(r"(\d{1,2})\s*stunden", re.IGNORECASE)


def _texte_aus(scores: dict, kategorien=None) -> list:
    """Sammelt die Meldungstexte aus den Kategoriedaten.

    Die Einzelmeldungen stecken in ``contributions[].reason`` — dort steht
    seit der Nachrichtenueberarbeitung der Titel an erster Stelle.
    """
    texte = []
    for cat, data in scores.items():
        if cat == "overall" or not isinstance(data, dict):
            continue
        if kategorien and cat not in kategorien:
            continue
        if data.get("detail"):
            texte.append((cat, str(data["detail"])))
        for beitrag in (data.get("contributions") or [])[:15]:
            if isinstance(beitrag, dict) and beitrag.get("reason"):
                texte.append((cat, str(beitrag["reason"])))
    return texte


def kampfmittel_signal(scores: dict) -> Optional[dict]:
    """Bombenfund oder Entschaerfung im Kerngebiet?

    Verlangt beides im selben Text: einen Kampfmittel-Begriff und einen Ort
    aus Kerngebiet oder Nachbarschaft. Ein Bombenfund in Koeln loest nichts
    aus — dort ist Koeln zustaendig.
    """
    for cat, text in _texte_aus(scores):
        klein = text.lower()
        if not any(w in klein for w in KAMPFMITTEL_BEGRIFFE):
            continue
        ort = detect_scope(text)
        if ort["scope"] in (SCOPE_ORT, SCOPE_NACHBARSCHAFT):
            return {
                "kind": "kampfmittel",
                "category": cat,
                "ort": ort["ort"],
                "zone": ort["scope"],
                "text": text[:200],
                "hinweis": (
                    f"Kampfmittel in {ort['ort']}. Eine Entschaerfung zieht "
                    f"Raeumung, Betreuung und Verpflegung der Evakuierten nach "
                    f"sich — bei Lagen im Kerngebiet praktisch ohne Ausnahme."
                ),
            }
    return None


def kombilage_signal(scores: dict, schwelle: float = 40.0) -> Optional[dict]:
    """Veranstaltung und Wetterlage gleichzeitig?

    Beides einzeln ist beherrschbar. Zusammen trifft eine hohe Personendichte
    auf Sturm, Hitze oder Gewitter — und aus dem geplanten Sanitaetsdienst
    wird eine Schadenslage mit Betreuungs- und Verpflegungsbedarf.
    """
    events = float((scores.get("events") or {}).get("score", 0) or 0)
    weather = float((scores.get("weather") or {}).get("score", 0) or 0)
    if events < schwelle or weather < schwelle:
        return None
    return {
        "kind": "kombilage",
        "events_score": events,
        "weather_score": weather,
        "hinweis": (
            f"Veranstaltungslage ({events:.0f}) faellt mit einer Wetterlage "
            f"({weather:.0f}) zusammen. Dann steht bereits Personal vor Ort, "
            f"und aus dem Sanitaetsdienst kann eine Schadenslage werden."
        ),
    }


def verpflegungsbedarf_signal(scores: dict) -> Optional[dict]:
    """Deutet die Lage auf laengeren Verpflegungsbedarf?

    Zwei Wege, von denen einer reichen muss (siehe Schwellen oben):
    eine erkennbar lange Einsatzdauer oder eine grosse Zahl gebundener Kraefte.

    Gewertet werden nur ortsnahe Meldungen. Ein Grossbrand in Hamburg dauert
    genauso lange, geht Troisdorf aber nichts an.
    """
    gruende = []
    ort_treffer = None
    max_kraefte = 0
    max_stunden = 0

    for _cat, text in _texte_aus(scores, kategorien={"news", "fire", "official_warning"}):
        ort = detect_scope(text)
        if ort["scope"] not in (SCOPE_ORT, SCOPE_NACHBARSCHAFT):
            continue
        klein = text.lower()

        treffer = next((w for w in DAUER_BEGRIFFE if w in klein), None)
        if treffer:
            ort_treffer = ort_treffer or ort
            if treffer not in [g.get("wort") for g in gruende]:
                gruende.append({"art": "dauer", "wort": treffer})

        for zahl in _KRAEFTE_MUSTER.findall(text):
            wert = int(zahl)
            if wert >= KRAEFTE_SCHWELLE and wert > max_kraefte:
                max_kraefte = wert
                ort_treffer = ort_treffer or ort

        for zahl in _STUNDEN_MUSTER.findall(text):
            wert = int(zahl)
            if wert >= DAUER_SCHWELLE_STUNDEN and wert > max_stunden:
                max_stunden = wert
                ort_treffer = ort_treffer or ort

    if not gruende and not max_kraefte and not max_stunden:
        return None

    teile = []
    if max_kraefte:
        teile.append(f"{max_kraefte} Einsatzkraefte gemeldet")
    if max_stunden:
        teile.append(f"seit {max_stunden} Stunden")
    if gruende:
        teile.append("Formulierung deutet auf lange Lage "
                     f"({gruende[0]['wort']})")

    return {
        "kind": "verpflegungsbedarf",
        "ort": ort_treffer["ort"] if ort_treffer else None,
        "zone": ort_treffer["scope"] if ort_treffer else None,
        "kraefte": max_kraefte or None,
        "stunden": max_stunden or None,
        "hinweis": (
            "Hinweis auf laengeren Verpflegungsbedarf: " + ", ".join(teile) +
            f". Ab etwa {DAUER_SCHWELLE_STUNDEN} Stunden Dauer oder "
            f"{KRAEFTE_SCHWELLE} Kraeften wird die Kueche erfahrungsgemaess "
            f"angefordert."
        ),
    }


def alle_signale(scores: dict) -> list:
    """Alle zutreffenden Signale, wichtigstes zuerst."""
    ergebnis = []
    for funktion in (kampfmittel_signal, verpflegungsbedarf_signal,
                     kombilage_signal):
        treffer = funktion(scores)
        if treffer:
            ergebnis.append(treffer)
    return ergebnis
