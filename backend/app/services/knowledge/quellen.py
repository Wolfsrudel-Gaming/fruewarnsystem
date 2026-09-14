"""Quellengesundheit — merkt, wenn das System blind wird.

DER FEHLER, UM DEN ES GEHT
Am 14.09.2026 stellte sich heraus: Acht von sechzehn Nachrichtenquellen
lieferten seit unbekannter Zeit nichts mehr. Zwei Zeitungsverlage hatten ihre
Feeds abgeschaltet (HTTP 410), drei kommunale Adressen waren umgezogen (404),
eine lieferte HTTP 200 mit einer leeren Seite.

Keiner dieser Ausfaelle war zu sehen. Der Sammler uebersprang jede Quelle,
die nicht mit 200 antwortete, und schrieb bestenfalls eine Zeile ins
Protokoll. Nach aussen sah das aus wie: keine Meldungen. Also Ruhe.

GENAU DAS IST DIE GEFAHR
Eine ausgefallene Quelle und eine ruhige Quelle sehen im Ergebnis gleich aus
— beide liefern nichts. Fuer ein Warnsystem ist der Unterschied alles: Das
eine heisst "es ist nichts passiert", das andere heisst "wir wuerden es nicht
merken". Betroffen waren ausgerechnet die kommunalen Quellen, also die, die
eine geplante Evakuierung oder Betreuungslage zuerst melden.

Ein stiller Ausfall ist deshalb schlimmer als ein lauter. Dieses Modul macht
ihn laut.

Reine Funktionen, damit die Bewertung ohne Datenbank pruefbar bleibt.
"""

from datetime import datetime, timedelta

# --- Ergebnis eines einzelnen Abrufs ---

STATUS_OK = "ok"
# HTTP 200, aber keine Eintraege. Der gefaehrlichste Fall: Der Abruf gilt
# technisch als gelungen, und das Ergebnis sieht aus wie Ruhe.
STATUS_STUMM = "stumm"
# Antwort mit Fehlercode (404, 410, 500 ...)
STATUS_FEHLER = "fehler"
# Gar keine Antwort: Zeitueberschreitung, Namensaufloesung, TLS
STATUS_UNERREICHBAR = "unerreichbar"
STATUS_UNBEKANNT = "unbekannt"

# --- Bewertung ueber die Zeit ---

STUFE_OK = "ok"
# Ein einzelner Fehlversuch kann alles Moegliche sein — ein Netzwackler, eine
# Wartung. Deshalb nicht sofort Alarm.
STUFE_WACKELT = "wackelt"
# Ab hier ist es kein Zufall mehr.
STUFE_AUSGEFALLEN = "ausgefallen"

AUSGEFALLEN_AB_FEHLVERSUCHEN = 3

# Eine Quelle, die laenger als das nichts Brauchbares geliefert hat, gilt als
# ausgefallen — auch wenn die Fehlversuche noch nicht gezaehlt wurden (etwa
# nach einem Neustart).
AUSGEFALLEN_AB_STUNDEN = 12

# Wie schwer ein Ausfall wiegt, haengt daran, was die Quelle abdeckt. Eine
# tote Lokalquelle kostet Vorlaufzeit im Kerngebiet; ein toter bundesweiter
# Ticker ist aergerlich, aber ersetzbar.
GEWICHT = {"kern": 1.0, "kreis": 0.7, "bundesweit": 0.3}
GEWICHT_STANDARD = 0.5


def bewerte_abruf(status_code=None, eintraege=0, fehler=None) -> str:
    """Was ist bei diesem einen Abruf herausgekommen?"""
    if fehler:
        return STATUS_UNERREICHBAR
    if status_code is None:
        return STATUS_UNBEKANNT
    if status_code != 200:
        return STATUS_FEHLER
    # 200 ohne Eintraege ist kein Erfolg. Ein Nachrichtenfeed ist nie leer;
    # wenn er leer ankommt, ist er umgezogen, abgeschaltet oder kaputt.
    if eintraege <= 0:
        return STATUS_STUMM
    return STATUS_OK


def ist_erfolg(status: str) -> bool:
    return status == STATUS_OK


def bewerte_quelle(status, fehlversuche_in_folge=0, letzter_erfolg=None,
                   jetzt=None, bereich=None) -> dict:
    """Wie steht es um diese Quelle — ueber die Zeit betrachtet?"""
    jetzt = jetzt or datetime.utcnow()
    stunden = None
    if letzter_erfolg is not None:
        stunden = max(0.0, (jetzt - letzter_erfolg).total_seconds() / 3600.0)

    if ist_erfolg(status):
        stufe = STUFE_OK
    elif fehlversuche_in_folge >= AUSGEFALLEN_AB_FEHLVERSUCHEN:
        stufe = STUFE_AUSGEFALLEN
    elif stunden is not None and stunden >= AUSGEFALLEN_AB_STUNDEN:
        stufe = STUFE_AUSGEFALLEN
    elif letzter_erfolg is None and status != STATUS_UNBEKANNT:
        # Noch nie geliefert. Eine Quelle, die von Anfang an nichts bringt,
        # ist falsch eingetragen — das ist kein voruebergehender Aussetzer.
        stufe = STUFE_AUSGEFALLEN
    else:
        stufe = STUFE_WACKELT

    return {
        "stufe": stufe,
        "status": status,
        "fehlversuche": fehlversuche_in_folge,
        "stunden_ohne_erfolg": round(stunden, 1) if stunden is not None else None,
        "gewicht": GEWICHT.get(bereich, GEWICHT_STANDARD),
        "hinweis": _hinweis(status, stufe, stunden),
    }


def _hinweis(status, stufe, stunden) -> str:
    if stufe == STUFE_OK:
        return "Liefert."
    dauer = ""
    if stunden is not None:
        dauer = (f" Seit {int(stunden)} Stunden nichts mehr."
                 if stunden >= 1 else "")
    if status == STATUS_STUMM:
        return ("Antwortet, liefert aber keine Eintraege — vermutlich "
                "umgezogen oder abgeschaltet. ACHTUNG: Das sieht im Ergebnis "
                "aus wie Ruhe, ist aber Blindheit." + dauer)
    if status == STATUS_FEHLER:
        return "Antwortet mit Fehlercode." + dauer
    if status == STATUS_UNERREICHBAR:
        return "Nicht erreichbar." + dauer
    return "Noch nie abgefragt."


def gesamtbild(quellen, jetzt=None) -> dict:
    """Wie blind ist das System insgesamt?

    `quellen` sind bereits bewertete Eintraege (siehe bewerte_quelle), je
    ergaenzt um `name` und `bereich`.
    """
    gesamt = len(quellen)
    ausgefallen = [q for q in quellen if q["stufe"] == STUFE_AUSGEFALLEN]
    wackeln = [q for q in quellen if q["stufe"] == STUFE_WACKELT]

    # Der Anteil zaehlt nicht nach Koepfen, sondern nach Bedeutung.
    gewicht_gesamt = sum(q.get("gewicht", GEWICHT_STANDARD) for q in quellen)
    gewicht_blind = sum(q.get("gewicht", GEWICHT_STANDARD) for q in ausgefallen)
    anteil = (gewicht_blind / gewicht_gesamt) if gewicht_gesamt else 0.0

    if not ausgefallen:
        stufe, text = STUFE_OK, "Alle Quellen liefern."
    elif anteil >= 0.5:
        stufe = "kritisch"
        text = ("Mehr als die Haelfte der Beobachtung ist ausgefallen. "
                "Ruhe im System bedeutet gerade NICHT, dass nichts passiert.")
    elif any(q.get("bereich") == "kern" for q in ausgefallen):
        stufe = "kritisch"
        text = ("Eine Quelle aus dem Kerngebiet ist ausgefallen. Genau dort "
                "entsteht die Vorlaufzeit, die das System liefern soll.")
    else:
        stufe = "beeintraechtigt"
        text = "Einzelne Quellen sind ausgefallen, das Kerngebiet ist gedeckt."

    return {
        "stufe": stufe,
        "text": text,
        "gesamt": gesamt,
        "ausgefallen": len(ausgefallen),
        "wackeln": len(wackeln),
        "blindanteil": round(anteil, 3),
        "namen_ausgefallen": [q.get("name") for q in ausgefallen],
    }
