"""Aufkommen in sozialen Netzen messen.

Der Grundsatz: EIN Beitrag ist ein Geruecht. Erst wenn mehrere unabhaengige
Konten binnen kurzer Zeit dasselbe zu einem Ort schreiben, ist es ein Signal.

Warum absolute Schwellen und kein Verhaeltnis zum Mittelwert: Das normale
Aufkommen an Ereignisbeitraegen zu Troisdorf liegt bei null bis zwei am Tag.
Ein Verhaeltnis zu fast null ist rechnerisch beliebig gross und damit
unbrauchbar — drei Beitraege in einer halben Stunde sind aussagekraeftiger als
jede Steigerungsrate.

Entscheidend ist die Zahl UNABHAENGIGER KONTEN, nicht die Zahl der Beitraege.
Ein einzelnes Konto, das fuenfmal dasselbe schreibt, bleibt eine Quelle.
"""

from datetime import datetime, timedelta
from typing import Optional

# Zeitfenster, in dem Beitraege als zusammengehoerig gelten
FENSTER = timedelta(minutes=30)

# Mindestanzahl Beitraege im Fenster
MIN_BEITRAEGE = 3

# Mindestanzahl verschiedener Konten. Das ist die eigentliche Huerde:
# Ohne sie wuerde ein einzelner eifriger Nutzer einen Alarm ausloesen.
MIN_KONTEN = 2

# Ab dieser Zahl unabhaengiger Konten gilt das Aufkommen als stark. Bei einer
# echten Grosslage schreiben Dutzende gleichzeitig.
STARKES_AUFKOMMEN_KONTEN = 5

# Nur diese Zonen loesen ein Signal aus. Ein Grossbrand in Hamburg erzeugt
# ebenfalls Aufkommen, geht Troisdorf aber nichts an.
RELEVANTE_ZONEN = ("troisdorf", "nachbarschaft")


def finde_aufkommen(posts, jetzt: Optional[datetime] = None,
                    fenster: timedelta = FENSTER) -> Optional[dict]:
    """Ungewoehnliches Aufkommen zu einem Ort finden.

    ``posts`` sind Objekte mit ``place``, ``scope``, ``author``, ``posted_at``
    und ``content``. Reine Funktion ohne Datenbankzugriff.

    Liefert den staerksten Treffer oder ``None``.
    """
    jetzt = jetzt or datetime.utcnow()
    grenze = jetzt - fenster

    nach_ort = {}
    for post in posts:
        if getattr(post, "scope", None) not in RELEVANTE_ZONEN:
            continue
        zeit = getattr(post, "posted_at", None) or getattr(post, "created_at", None)
        if zeit is None or zeit < grenze or zeit > jetzt + timedelta(minutes=5):
            continue
        ort = getattr(post, "place", None) or "Unbekannt"
        nach_ort.setdefault(ort, []).append(post)

    bester = None
    for ort, gruppe in nach_ort.items():
        konten = {getattr(p, "author", None) or "?" for p in gruppe}
        if len(gruppe) < MIN_BEITRAEGE or len(konten) < MIN_KONTEN:
            continue

        stichworte = []
        for p in gruppe:
            for w in (getattr(p, "keywords", None) or []):
                if w not in stichworte:
                    stichworte.append(w)

        treffer = {
            "ort": ort,
            "zone": getattr(gruppe[0], "scope", None),
            "beitraege": len(gruppe),
            "konten": len(konten),
            "stark": len(konten) >= STARKES_AUFKOMMEN_KONTEN,
            "stichworte": stichworte[:8],
            "beispiel": (getattr(gruppe[0], "content", "") or "")[:200],
            "fenster_minuten": int(fenster.total_seconds() // 60),
        }
        # Mehr unabhaengige Konten schlagen mehr Beitraege
        if bester is None or (treffer["konten"], treffer["beitraege"]) > \
                (bester["konten"], bester["beitraege"]):
            bester = treffer

    return bester


def beschreibe(aufkommen: dict, wachsam: bool = False) -> str:
    """Klartext fuer Begruendung und Lagebericht."""
    if not aufkommen:
        return ""
    teile = [
        f"{aufkommen['beitraege']} Beitraege von "
        f"{aufkommen['konten']} verschiedenen Konten zu {aufkommen['ort']} "
        f"binnen {aufkommen['fenster_minuten']} Minuten."
    ]
    if aufkommen.get("stichworte"):
        teile.append("Genannt: " + ", ".join(aufkommen["stichworte"][:5]) + ".")
    if aufkommen.get("stark"):
        teile.append(
            "Das Aufkommen ist deutlich — bei einer echten Lage schreiben "
            "Dutzende gleichzeitig."
        )
    if wachsam:
        teile.append(
            "Waehrend der laufenden Grosslage wiegt das schwerer als sonst."
        )
    teile.append(
        "UNBESTAETIGT: Soziale Netze sind der schnellste, aber auch der "
        "unzuverlaessigste Kanal. Amtliche Quellen pruefen."
    )
    return " ".join(teile)
