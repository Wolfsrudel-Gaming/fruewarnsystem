"""Recherchierter Grundbestand der DRK-Wissensdatenbank.

Alle Eintraege hier stammen aus oeffentlich zugaenglichen Quellen und sind mit
Fundstelle belegt. Wichtigste Grundlage ist der Rettungsdienstbedarfsplan 2023
des Rhein-Sieg-Kreises — ein vom Kreistag beschlossenes und veroeffentlichtes
Dokument, das den Einsatzrahmen fuer Troisdorf sehr genau beschreibt.

WAS HIER BEWUSST FEHLT
----------------------
Die Alarm- und Ausrueckeordnung des Rhein-Sieg-Kreises ist nicht oeffentlich.
Eine Anfrage nach dem Informationsfreiheitsgesetz wurde 2023 abschlaegig
beschieden; herausgegeben wurde nur ein geschwaerztes Dokument mit dem Hinweis,
der Kreis fuehre keine einheitliche AAO, die Stichwortlisten lagen bei den
Kommunen. Die konkrete Zuordnung "Stichwort X alarmiert Einheit Y" ist damit
nicht aus oeffentlichen Quellen zu rekonstruieren.

Was hier steht, ist deshalb der belegbare Rahmen: Eskalationsstufen, Einheiten,
Staerken, Zeitvorgaben, Gefahrenschwerpunkte. Die eigentliche AAO und die
internen Einsatzplanungen des Kreisverbands muessen von Personen mit Zugang
selbst eingepflegt werden — dafuer gibt es die Eintraege ohne ``seed_key``
ueber die API. Solche Eintraege werden gleichberechtigt herangezogen, aber als
nicht-oeffentlich gekennzeichnet.

Quellen im Einzelnen sind bei jedem Eintrag vermerkt.
"""

RDBP = "Rettungsdienstbedarfsplan 2023 Rhein-Sieg-Kreis"
RDBP_URL = (
    "https://www.rhein-sieg-kreis.de/vv/ressourcen/medien/downloads/Dezernat_5/"
    "Amt_38_-_Amt_fuer_Bevoelkerungsschutz/RDBP2023_finale-Version.pdf"
)
RDBP_DATE = "2023-09-28"

LK_UEH = "Landeskonzept ueberoertliche Hilfe NRW – Sanitaets- und Betreuungsdienst (MIK NRW)"


def _e(seed_key, kind, scope, title, body, *, categories=None, tags=None,
       trigger=None, facts=None, source=RDBP, source_url=RDBP_URL,
       source_date=RDBP_DATE, is_official=True):
    return {
        "seed_key": seed_key,
        "kind": kind,
        "scope": scope,
        "title": title,
        "body": body.strip(),
        "categories": categories or [],
        "tags": tags or [],
        "trigger": trigger,
        "facts": facts,
        "source": source,
        "source_url": source_url,
        "source_date": source_date,
        "is_official": is_official,
    }


SEED_ENTRIES = [

    # ------------------------------------------------------------------
    # Doktrin — was rechtlich und konzeptionell gilt
    # ------------------------------------------------------------------

    _e(
        "doktrin.rettg.7.4", "doktrin", "nrw",
        "RettG NRW § 7 Abs. 4 — Vorkehrungen fuer Schadensereignisse",
        """
Fuer Schadensereignisse mit einer groesseren Anzahl Verletzter oder Kranker
sind Leitende Notaerzte (LNA) zu bestellen und deren Einsatz ist zu regeln.
Ergaenzend koennen Organisatorische Leiter Rettungsdienst (OrgL RD) bestellt
werden. Ferner sind ausreichende Vorbereitungen fuer den Einsatz zusaetzlicher
Rettungsmittel und des notwendigen Personals zu treffen.

Das ist die Rechtsgrundlage dafuer, dass bei einer groesseren Lage nicht nur
mehr Fahrzeuge, sondern eine eigene Fuehrungsorganisation anlaeuft — und damit
auch der Punkt, an dem die Hilfsorganisationen ins Spiel kommen.
        """,
        categories=["manv", "health"],
        tags=["RettG", "LNA", "OrgL", "Rechtsgrundlage"],
    ),

    _e(
        "doktrin.manv.definition", "doktrin", "bund",
        "MANV — Definition nach DIN 13050",
        """
Ein Massenanfall von Verletzten (MANV) bezeichnet einen Notfall mit einer
groesseren Anzahl von Verletzten oder Erkrankten sowie anderen Geschaedigten
oder Betroffenen, der mit der vorhandenen und einsetzbaren Vorhaltung des
Rettungsdienstes aus dem Rettungsdienstbereich nicht bewaeltigt werden kann.

Entscheidend ist nicht die absolute Zahl, sondern das Missverhaeltnis zur
verfuegbaren Vorhaltung. Bei ohnehin hoher Auslastung des Rettungsdienstes
kann deshalb schon eine kleinere Lage zum MANV werden — genau deshalb ist die
Beobachtung der Systemauslastung ein Fruehindikator.
        """,
        categories=["manv"],
        tags=["MANV", "DIN 13050", "Definition"],
    ),

    _e(
        "doktrin.manv.konzept.rsk", "doktrin", "rhein_sieg",
        "Einsatzkonzept MANV des Rhein-Sieg-Kreises — Merkmale",
        """
Das MANV-Konzept des Kreises deckt den Bereich zwischen rettungsdienstlicher
Individualversorgung und Grosseinsatzlagen bzw. Katastrophen im Sinne des BHKG
ab; die Uebergaenge zwischen den Stufen sind fliessend. Es ist geprägt durch:

- weitgehend automatisierte, mehrstufige, schadenslagenabhaengige Alarmierung
- schadenslagenabhaengige Alarmierung der rettungs- und sanitaetsdienstlichen
  Reserven aller mitwirkenden Leistungserbringer, der kommunalen
  Rettungsdienste sowie der Hilfsorganisationen
- Beruecksichtigung aller Komponenten: LNA, OrgL RD, Sonderrettungsmittel,
  Notaerzte, Luftrettung, RTW, KTW, NEF, Einsatzeinheiten NRW, Sanitaetsdienst,
  Betreuungsdienst, PSNV, Personenauskunftsstelle
- ein Fuehrungs- und Organisationskonzept mit kreisweit einheitlichem
  Kennzeichnungskonzept (Kennzeichnungswesten)
- Einsetzbarkeit auch ausserhalb des Kreises im Rahmen nachbarschaftlicher
  oder ueberoertlicher Hilfe
- festgelegte Bereitstellungsraeume in allen Kommunen des Kreises

Fuer die Einschaetzung wichtig: Die Alarmierung ist *automatisiert und
mehrstufig*. Sobald ein Stichwort eine Stufe erreicht, laufen die
Hilfsorganisationen mit — ohne gesonderte Entscheidung.
        """,
        categories=["manv", "health"],
        tags=["MANV", "Alarmierung", "Einsatzeinheit", "Bereitstellungsraum"],
    ),

    _e(
        "doktrin.uemanv", "doktrin", "nrw",
        "UEMANV — Ueberoertliche Hilfe beim Massenanfall",
        """
Das UEMANV-Konzept regelt die Anforderung externer bzw. Entsendung eigener
Kraefte zwischen benachbarten Rettungsdienstbereichen mit standardisierten
Komponenten (nach Landeskonzept ueberoertliche Hilfe NRW »Sanitaetsdienst und
Betreuungsdienst«, MIK NRW, Ausgabe 1. Juli 2013):

- Nachbarschaftliche (Sofort-)Hilfe aus dem Rettungsdienst
- UEMANV-S-Komponente (UEMANV-S)
- Patiententransport-Zug 10 NRW (PT-Z 10 NRW)
- Behandlungsplatz-Bereitschaft 50 NRW (BHP-B 50 NRW)

Das Konzept ist fuer Grossschadensereignisse mit bis zu 1.000 Betroffenen
ausgelegt. Die Leistungen werden von den eintreffenden Einheiten autark und
unter Beibehaltung der bestehenden oertlichen Organisation erbracht. Fuer die
Anfahrt sind Sammel- und Bereitstellungsraeume festgelegt.

Im Rhein-Sieg-Kreis uebernehmen ergaenzend ein Leitender Notarzt und ein
Organisatorischer Leiter die Fuehrung des PT-Z 10 NRW.

Praktische Folge: Eine Grosslage in Koeln, Bonn oder einem Nachbarkreis kann
Troisdorfer Kraefte binden, ohne dass in Troisdorf selbst etwas passiert.
        """,
        categories=["manv", "official_warning"],
        tags=["UEMANV", "PT-Z 10", "BHP 50", "ueberoertlich", "Nachbarkreis"],
    ),

    _e(
        "doktrin.hilfsfrist", "doktrin", "rhein_sieg",
        "Hilfsfrist und Erreichungsgrad im Rhein-Sieg-Kreis",
        """
Fuer Einsatzkernbereiche gilt eine Hilfsfrist von 8 Minuten, fuer alle
weiteren Bereiche 12 Minuten. Angestrebt wird ein Erreichungsgrad von
mindestens 90 Prozent.

Die Hilfsfrist ist das wichtigste Planungs- und Qualitaetsmerkmal des
Rettungsdienstes. Sinkende Erreichungsgrade sind ein Indikator dafuer, dass
das System an der Belastungsgrenze arbeitet — und damit dafuer, dass eine
zusaetzliche Lage schneller zum MANV eskaliert.
        """,
        categories=["health", "manv"],
        tags=["Hilfsfrist", "Erreichungsgrad", "Auslastung"],
        facts={"hilfsfrist_kern_min": 8, "hilfsfrist_flaeche_min": 12,
               "erreichungsgrad_ziel_prozent": 90},
    ),

    # ------------------------------------------------------------------
    # Eskalationsstufen — ab wann was
    # ------------------------------------------------------------------

    _e(
        "stufe.manv.rsk", "eskalationsstufe", "rhein_sieg",
        "MANV-Stufen des Rhein-Sieg-Kreises",
        """
Der Kreis staffelt den Massenanfall in Zehnerschritten:

- MANV10 —  6 bis 10 Verletzte/Erkrankte
- MANV20 — 11 bis 20 Verletzte/Erkrankte
- MANV30 — 21 bis 30 Verletzte/Erkrankte
- MANV40 — 31 bis 40 Verletzte/Erkrankte
- MANV50 — 41 bis 50 Verletzte/Erkrankte
- darueber hinaus weitere Stufen

Diese Staffelung ist feiner als die anderer Kreise in NRW, die haeufig
MANV 10/15/25/50/100 verwenden. Fuer Troisdorf gilt die Kreis-Staffelung.

Je hoeher die Stufe, desto sicherer laufen die Einsatzeinheiten und damit die
DRK-Bereitschaften mit — nicht nur der Regelrettungsdienst.
        """,
        categories=["manv"],
        tags=["MANV10", "MANV20", "MANV30", "MANV40", "MANV50", "Stufen"],
        facts={"stufen": [10, 20, 30, 40, 50]},
    ),

    _e(
        "stufe.sichtung", "eskalationsstufe", "bund",
        "Sichtungskategorien und Planungsannahmen",
        """
Bei einem MANV wird die Behandlungs- und Transportprioritaet durch einen
(Leitenden) Notarzt festgelegt. Uebliche Planungsannahme fuer die
Ressourcenbemessung:

- SK I  (rot, Sofortbehandlung):        etwa 20 Prozent der Betroffenen
- SK II (gelb, aufgeschobene Behandlung): etwa 30 Prozent
- SK III (gruen, leicht):                etwa 50 Prozent

Beispiel MANV50: 10 Patienten SK I, 15 SK II, 25 SK III.
Beispiel MANV20:  4 Patienten SK I,  6 SK II, 10 SK III.

Der Betreuungsdienst — die typische DRK-Aufgabe — traegt vor allem die
SK-III-Gruppe und die unverletzt Betroffenen. Deren Zahl ist bei Ereignissen
wie Evakuierungen oder Ausfaellen um ein Vielfaches groesser als die Zahl der
Verletzten.
        """,
        categories=["manv"],
        tags=["Sichtung", "SK I", "SK II", "SK III", "Triage"],
        source="Muster-MANV-Konzepte NRW / AGBF-Verteilungsschluessel",
        source_url="https://www.bra.nrw.de/system/files/media/document/file/praesentation_kat_konzepte.pdf",
        source_date="2014-02",
        facts={"sk1_anteil": 0.2, "sk2_anteil": 0.3, "sk3_anteil": 0.5},
    ),

    _e(
        "stufe.taktische_reserve", "eskalationsstufe", "rhein_sieg",
        "Taktische Reserve — Spitzenbedarf und Sonderbedarf",
        """
Neben dem Grundbedarf haelt der Kreis eine taktische Reserve vor. Sie
gliedert sich in zwei Arten, die sich in der Vorlaufzeit unterscheiden:

SPITZENBEDARF — nicht vorplanbare Belastungsspitzen, ausgeloest durch:
- zeitweise besonders hohe Einsatzfallzahlen
- Schadensereignisse mit groesserer Anzahl Betroffener (MANV-Lagen)
- Sofortanforderungen von Aufsichtsbehoerden
- BESONDERE WETTERLAGEN / HAEUFUNG VON WITTERUNGSBEDINGTEN EINSAETZEN
- Bereitstellungseinsaetze / Evakuierungsmassnahmen

Im Alarmierungsfall sollen diese Rettungsmittel nach 30 Minuten, spaetestens
45 bis 60 Minuten inklusive Umkleide- und Ruestzeit einsatzbereit sein.

SONDERBEDARF — vorplanbare Ereignisse, in der Regel mit mindestens
24 Stunden Vorlauf geplant:
- geplante (Gross-)Veranstaltungen
- laenger andauernde Schadensereignisse mit groesserer Anzahl Betroffener
- ZU ERWARTENDE BESONDERE WETTERLAGEN
- vorplanbare Ereignisse wie Silvester oder Brauchtumstage
- vorplanbare Bereitstellungseinsaetze / Evakuierungsmassnahmen
- Unterstuetzung bei polizeilichen Lagen

Das ist die direkteste Bruecke zwischen diesem Fruehwarnsystem und der
tatsaechlichen Alarmierung: Eine angekuendigte Unwetterlage ist im Bedarfsplan
ausdruecklich ein Grund, Kraefte vorzuhalten — mit genau dem Vorlauf von
24 Stunden, den auch dieses System betrachtet.
        """,
        categories=["weather", "water", "events", "power", "traffic"],
        tags=["Spitzenbedarf", "Sonderbedarf", "Vorhaltung", "Wetterlage",
              "Vorlaufzeit", "Bereitstellung"],
        trigger={"any_category_min_score": 60},
        facts={"spitzenbedarf_bereit_min": 30, "spitzenbedarf_spaet_min": 60,
               "sonderbedarf_vorlauf_h": 24},
    ),

    # ------------------------------------------------------------------
    # Organisation — wer laeuft
    # ------------------------------------------------------------------

    _e(
        "org.einsatzeinheit.nrw", "organisation", "nrw",
        "Einsatzeinheit NRW — Gliederung und Staerke",
        """
Die Einsatzeinheit (EE) NRW ist die vereinheitlichte, autark einsetzbare
Grundeinheit des Sanitaets- und Betreuungsdienstes. Gesamtstaerke 1/7/25/33.

Teileinheiten:
- Fuehrung      1/1/2/4  — Zugfuehrer, Gruppenfuehrer, zwei Fuehrungsgehilfen
                            (KdoW oder ELW 1)
- Sanitaet      0/1/9/10 — Sanitaetsstaffel (GW-San) und zwei
                            Notfallkrankenwagen. Seit Ende 2024 gehoert kein
                            Arzt mehr zur Sanitaetsgruppe.
- Betreuung     -/4/11/15 — zwei Betreuungsstaffeln (GW-Betreuung,
                            Betreuungskombi) und ein Verpflegungstrupp (Bt-LKW)
- Unterstuetzung -/1/3/4  — Truppfuehrer und drei Helfer (MTF)

Leistung: Erstversorgung und Betreuung von bis zu 250 unverletzten Betroffenen
an einer Anlaufstelle und im weiteren Verlauf in einer Betreuungseinrichtung,
autark fuer die ersten vier Stunden nach Herstellung der Einsatzbereitschaft.

Landesweit gab es 2024 insgesamt 241 Einsatzeinheiten NRW, davon 28 nicht
einsatzbereit. Das ueberarbeitete Landeskonzept wurde Ende 2024 erlassen.
        """,
        categories=["manv", "events"],
        tags=["Einsatzeinheit", "EE NRW", "Betreuungsdienst", "Sanitaetsdienst"],
        source="Landeskonzept ueberoertliche Hilfe NRW / Uebersicht Einsatzeinheit NRW",
        source_url="https://de.wikipedia.org/wiki/Einsatzeinheit_(Deutschland)",
        source_date="2024",
        facts={"staerke_gesamt": 33, "fuehrer": 1, "unterfuehrer": 7,
               "helfer": 25, "betreute_personen": 250, "autark_stunden": 4},
    ),

    _e(
        "org.ee.rhein_sieg", "organisation", "rhein_sieg",
        "Einsatzeinheiten im Rhein-Sieg-Kreis",
        """
Im Rhein-Sieg-Kreis bestehen fuenf Einsatzeinheiten. Das DRK stellt im Auftrag
des Landes drei davon, jede mit 33 Einsatzkraeften und den Teileinheiten
Sanitaetsgruppe, Betreuungsgruppe, Fuehrungskomponente und Technikkomponente.
Eine weitere Einheit (EE SU 05) stellen die Malteser aus Meckenheim,
Bad Honnef und Siegburg; die Johanniter und die DLRG wirken ebenfalls mit.

Die Hilfsorganisationen im Kreis verfuegen zusammen ueber 26 Standorte. Das
DRK Rhein-Sieg hat rund 1.000 ehrenamtliche Helferinnen und Helfer in den
Bereitschaften.

Viele Mitglieder der Einsatzeinheiten sind zugleich in den Ortsvereinen in den
Fachdiensten Sanitaetsdienst, Betreuungsdienst sowie Technik und Sicherheit
taetig; weitere Kraefte stellt der Rettungsdienst.

Sonderfahrzeuge des DRK Rhein-Sieg: Geraetewagen Sanitaetsdienst, mobile
Kuechenanhaenger und Feldkochherde, Versorgungsfahrzeuge, Komponenten Technik
und Sicherheit, mobile Unfallhilfsstellen, mehrere Logistik-Lkw sowie zwei
Wechselladerfahrzeuge mit Abrollbehaeltern fuer Sanitaets- und Technikmaterial
im MANV.
        """,
        categories=["manv", "events"],
        tags=["DRK Rhein-Sieg", "Einsatzeinheit", "Malteser", "Johanniter",
              "DLRG", "Abrollbehaelter"],
        source="DRK Kreisverband Rhein-Sieg / Malteser Meckenheim",
        source_url="https://www.drk-rhein-sieg.de/aufgaben/katastrophenschutz",
        source_date="2025",
        facts={"einsatzeinheiten_gesamt": 5, "einsatzeinheiten_drk": 3,
               "helfer_drk_rhein_sieg": 1000, "standorte_hiorg": 26},
    ),

    _e(
        "org.bhp50", "organisation", "nrw",
        "Behandlungsplatz-Bereitschaft 50 NRW (BHP-B 50)",
        """
Der BHP 50 wird aus einer Fuehrungsteileinheit, drei Sanitaetsteileinheiten,
einem Abrollbehaelter MANV NRW und weiteren Ressourcen gebildet — insgesamt
78 Einsatzkraefte.

Leistung: Aufnahme und Versorgung von 50 Patienten innerhalb von zwei Stunden,
autark bis zu vier Stunden fuer bis zu 100 Patienten.

Der BHP-B 50 NRW ist eine der vier UEMANV-Komponenten und wird bei
ueberoertlicher Hilfe angefordert.
        """,
        categories=["manv"],
        tags=["BHP 50", "Behandlungsplatz", "UEMANV"],
        source=LK_UEH,
        source_url="https://de.wikipedia.org/wiki/Einsatzeinheit_(Deutschland)",
        source_date="2013-07-01",
        facts={"einsatzkraefte": 78, "patienten_2h": 50, "patienten_autark": 100,
               "autark_stunden": 4},
    ),

    _e(
        "org.btp500", "organisation", "nrw",
        "Betreuungsplatz-Bereitschaft 500 NRW (BTP-B 500)",
        """
Zwei Einsatzeinheiten und eine Fuehrungsstaffel bilden einen Betreuungsplatz
fuer mindestens 500 Betroffene — 72 Einsatzkraefte, autark bis zu vier Stunden.

Das ist die Groessenordnung, die bei Evakuierungen, laengeren Stromausfaellen
oder Hochwasserlagen gebraucht wird. Fuer das DRK Troisdorf ist der
Betreuungsdienst die wahrscheinlichste Einsatzart ueberhaupt: Betroffene ohne
Verletzung sind bei fast jeder Grosslage die groesste Gruppe.
        """,
        categories=["manv", "power", "water", "weather"],
        tags=["BTP 500", "Betreuungsplatz", "Evakuierung", "Notunterkunft"],
        source=LK_UEH,
        source_url="https://de.wikipedia.org/wiki/Einsatzeinheit_(Deutschland)",
        source_date="2013-07-01",
        facts={"einsatzkraefte": 72, "betroffene": 500, "autark_stunden": 4},
    ),

    _e(
        "org.fb_hiorg", "organisation", "rhein_sieg",
        "Fachberater Hilfsorganisation (FB HiOrg)",
        """
Der FB HiOrg beraet die Einsatzleitung und spricht im Einsatz fuer alle
Hilfsorganisationen. Themen: Leistungsfaehigkeit des Betreuungsdienstes
inklusive PSNV, sanitaets- und betreuungsdienstliche Fragestellungen sowie die
Unterstuetzung bei Anforderung und Einsatz von Kraeften, Material und
Sonderfahrzeugen.

Der Dienst wird rund um die Uhr fuer den gesamten Rhein-Sieg-Kreis
sichergestellt und kann jederzeit durch die Kreisleitstelle alarmiert werden.
Angestrebte Eintreffzeit: 30 bis 45 Minuten nach Alarmierung.

Aus der Funktion leiten sich keine Fuehrungsaufgaben in der Einsatzleitung ab —
sie ist beratend. Ansprechpartner fuer medizinisch-organisatorische Fragen
bleiben LNA und OrgL RD.
        """,
        categories=["manv", "health"],
        tags=["FB HiOrg", "Fachberater", "Kreisleitstelle", "24/7"],
        facts={"eintreffzeit_min": 30, "eintreffzeit_max": 45},
    ),

    _e(
        "org.elw1rd", "organisation", "rhein_sieg",
        "Einsatzleitwagen Rettungsdienst (ELW 1 RD) — DRK Niederkassel",
        """
Der ELW 1 RD hat seinen Standort an der DRK-Rettungswache Niederkassel und
wird kreisweit bei JEDEM LNA-/OrgL-RD-Einsatz automatisch mitalarmiert.
Besetzung in der Regel zwei Fuehrungsgehilfen, davon ein Gruppenfuehrer
Rettungsdienst. Einsatzbereitschaft rund um die Uhr, angestrebte Eintreffzeit
30 bis 45 Minuten.

Bemerkenswert fuer die Lageeinschaetzung: Hier laeuft eine DRK-Komponente
automatisch mit, sobald eine Fuehrungsstruktur Rettungsdienst gebildet wird.
Ein LNA-Einsatz im Kreis bedeutet also immer auch DRK-Beteiligung.
        """,
        categories=["manv", "health"],
        tags=["ELW 1 RD", "DRK Niederkassel", "LNA", "OrgL", "Automatikalarm"],
        facts={"eintreffzeit_min": 30, "eintreffzeit_max": 45},
    ),

    _e(
        "org.lv_nordrhein", "organisation", "nrw",
        "DRK Landesverband Nordrhein — Fachdienste im Bevoelkerungsschutz",
        """
Der Landesverband Nordrhein gliedert den Bevoelkerungsschutz in sechs
Fachdienste:

- Betreuungsdienst — Verpflegung, Notunterkuenfte und Kleidung fuer bis zu
  500 Personen in kuerzester Zeit
- Sanitaetsdienst — Versorgung Verletzter und Erkrankter bei Veranstaltungen
  und im Einsatz
- Rettungshunde — Flaechen- und Truemmersuche
- Information und Kommunikation (IuK) — Aufbau und Betrieb der
  Einsatzkommunikation
- Technik und Sicherheit — Stromversorgung, Beleuchtung, Wasser, Zeltaufbau,
  Feldkochherde, Sicherungsaufgaben
- CBRN-Schutz — chemische, biologische, radiologische und nukleare Gefahren

Gefuehrt vom Landesbereitschaftsleiter mit drei Stellvertretern sowie sechs
Landesbeauftragten fuer die Fachdienste.
        """,
        categories=["manv", "radiation", "power", "events"],
        tags=["Landesverband Nordrhein", "Fachdienst", "CBRN", "IuK",
              "Betreuungsdienst", "Rettungshunde"],
        source="DRK Landesverband Nordrhein",
        source_url="https://www.drk-nordrhein.de/angebote/bevoelkerungsschutz-rettung/bereitschaften/",
        source_date="2025",
    ),

    _e(
        "org.rettungswache.troisdorf", "organisation", "troisdorf",
        "Rettungswache Troisdorf",
        """
Traeger: Stadt Troisdorf.
Standorte derzeit: Larstrasse 2 (Feuerwache) und Muelheimer Strasse 26
(Industriepark Troisdorf). Geplant ist die Zusammenfuehrung beider Standorte
und die Verlagerung westlich von Troisdorf-Mitte (B 8).

Versorgungsbereich kuenftig: Stadtgebiet Troisdorf ohne Altenrath, Bergheim,
Muellekoven und Eschmar, zusaetzlich Niederkassel-Stockem.

Zu versorgende Autobahnabschnitte:
- A 59 AS Troisdorf bis AS Lind, Fahrtrichtung Koeln
- A 59 AS Lind bis AD Bonn-Beuel, Fahrtrichtung Bonn
- A 560 AD Sankt Augustin bis AS Siegburg, Fahrtrichtung Hennef

Notarztstandort Troisdorf-Sieglar (Wilhelm-Busch-Strasse 9) versorgt das
Stadtgebiet westlich der A 59 sowie Bergheim, Muellekoven und Eschmar.
        """,
        categories=["health", "traffic"],
        tags=["Rettungswache", "Troisdorf", "A59", "A560", "Sieglar"],
    ),

    _e(
        "org.reserve.troisdorf", "organisation", "troisdorf",
        "Taktische Reserve — Stellung der Stadt Troisdorf",
        """
In der Uebersicht der taktischen Reserve haelt die Stadt Troisdorf als Traeger
der Rettungswache KEINE eigenen Spitzenbedarfs-Fahrzeuge vor. Fuer den
Sonderbedarf stellt Troisdorf lediglich Personal zur Besetzung von RTW und NEF
aus der technischen Reserve (im Bedarfsplan als "P*" gekennzeichnet).

Kreisweit stehen im Spitzenbedarf 9 RTW und 3 NEF, im Sonderbedarf 4 KTW sowie
Personalgestellungen bereit.

Bedeutung fuer die Lageeinschaetzung: Troisdorf hat wenig eigenen Puffer. Wird
es hier eng, kommt Verstaerkung von aussen oder ueber die ehrenamtlichen
Einheiten — also ueber die Bereitschaft.
        """,
        categories=["health", "manv"],
        tags=["taktische Reserve", "Spitzenbedarf", "Sonderbedarf", "Troisdorf"],
        facts={"spitzenbedarf_rtw_kreis": 9, "spitzenbedarf_nef_kreis": 3,
               "sonderbedarf_ktw_kreis": 4},
    ),

    # ------------------------------------------------------------------
    # Gefahrenobjekte — was im Gebiet liegt
    # ------------------------------------------------------------------

    _e(
        "gefahr.industrie", "gefahrenobjekt", "rhein_sieg",
        "Chemische und sprengstoffverarbeitende Industrie",
        """
Betriebe und Einrichtungen mit besonderen Risiken fuer die Bevoelkerung
(Brandereignisse, Explosionen, Schadstoffaustritte) liegen im Umkreis der
chemischen und sprengstoffverarbeitenden Industrie in NIEDERKASSEL,
TROISDORF, SIEGBURG und EITORF. Bedeutsam ist zusaetzlich die unmittelbare
Nachbarschaft zum Chemieguertel Koeln.

Troisdorf ist damit einer von vier Schwerpunkten im Kreis. Ein Stoerfall hier
trifft die eigene Stadt unmittelbar; ein Stoerfall im Koelner Chemieguertel
kann ueber Ausbreitung und Evakuierung ebenfalls Troisdorf betreffen.
        """,
        categories=["fire", "air_quality", "official_warning"],
        tags=["Industrie", "Stoerfall", "Explosion", "Schadstoff", "Troisdorf",
              "Chemieguertel Koeln"],
        trigger={"categories": ["fire", "air_quality"], "min_score": 50},
    ),

    _e(
        "gefahr.verkehr", "gefahrenobjekt", "rhein_sieg",
        "Fernverkehrsstrassen und Bahnstrecken",
        """
Autobahnen: A 3, A 59, A 61, A 555, A 560, A 565.
Bundesstrassen: B 8, B 42, B 56, B 256, B 266, B 478, B 484, B 507.
Landesstrasse L 333.

Eisenbahn-Hauptstrecken der DB AG: ICE-Schnellfahrstrecke Koeln–Frankfurt,
Koeln–Siegen, Koeln–Wiesbaden, Koeln–Mainz, Koeln–Gummersbach–Luedenscheid,
Bonn–Euskirchen–Bad Muenstereifel. Ausdruecklich genannt sind
Schadensereignisse mit Personenzuegen und Transporten gefaehrlicher Gueter.

Durch Troisdorf verlaufen A 59, A 560 und B 8 sowie die Schnellfahrstrecke.
Der Rangierbahnhof Troisdorf ist ein Knoten des Gefahrgutverkehrs.
        """,
        categories=["traffic", "manv"],
        tags=["Autobahn", "A59", "A560", "B8", "ICE", "Gefahrgut",
              "Rangierbahnhof", "Bahnunglueck"],
        trigger={"categories": ["traffic"], "min_score": 55},
    ),

    _e(
        "gefahr.flughafen", "gefahrenobjekt", "troisdorf",
        "Flughaefen und Flugplaetze",
        """
- Konrad-Adenauer-Airport Koeln/Bonn — liegt auf dem Gebiet von TROISDORF
  und Koeln
- Verkehrslandeplatz Bonn/Hangelar (Sankt Augustin)
- Flugplatz Eudenbach (Bad Honnef und Koenigswinter)

Der Flughafen Koeln/Bonn liegt anteilig auf Troisdorfer Stadtgebiet. Ein
Flugunfall dort ist das klassische Grossschadensszenario mit sofortiger
MANV-Alarmierung ueber mehrere Stufen und Betreuungsbedarf fuer unverletzte
Betroffene und Angehoerige in dreistelliger Zahl.
        """,
        categories=["manv", "traffic"],
        tags=["Flughafen", "Koeln/Bonn", "Troisdorf", "Flugunfall", "MANV"],
        trigger={"categories": ["traffic", "manv"], "min_score": 60},
    ),

    _e(
        "gefahr.gewaesser", "gefahrenobjekt", "rhein_sieg",
        "Gewaesser im Kreisgebiet",
        """
Rhein, Sieg, Agger, Broel und Swist.

Troisdorf liegt zwischen Rhein und Sieg. Die Sieg-Muendung bei Bergheim, die
Ortslagen Bergheim, Muellekoven und Eschmar sowie die Rheinaue sind die
hochwassergefaehrdeten Bereiche. Bei Rheinhochwasser sind Betreuung,
Evakuierung und Deichverteidigung die typischen Aufgaben.

Niedrigwasser ist ebenso relevant: Es zeigt Duerre an und erhoeht damit die
Waldbrandgefahr, besonders in der Wahner Heide.
        """,
        categories=["water", "shipping", "fire"],
        tags=["Rhein", "Sieg", "Agger", "Hochwasser", "Niedrigwasser",
              "Bergheim", "Muellekoven", "Eschmar"],
        trigger={"categories": ["water"], "min_score": 50},
    ),

    _e(
        "gefahr.pflege", "gefahrenobjekt", "rhein_sieg",
        "Pflegeeinrichtungen und Krankenhaeuser",
        """
Im Kreisgebiet rund 80 Altenheime und Pflegeeinrichtungen, fuenf
Akut-Krankenhaeuser, sechs Sonderkrankenhaeuser und eine Kinderklinik
(Asklepios Sankt Augustin). In Troisdorf die GFO Kliniken (St. Josef
Troisdorf und St. Johannes Troisdorf-Sieglar, geplante Zusammenfuehrung am
Standort Sieglar).

Pflegeeinrichtungen sind bei Hitzewellen, Stromausfaellen und Evakuierungen
der kritische Punkt: viele nicht selbst mobile Personen, hoher Betreuungs- und
Transportbedarf. Eine Heimraeumung bindet sofort Betreuungsdienst und KTW.
        """,
        categories=["health", "power", "weather"],
        tags=["Altenheim", "Pflegeheim", "Krankenhaus", "Evakuierung",
              "Hitze", "vulnerable Gruppen"],
        trigger={"categories": ["health", "power", "weather"], "min_score": 60},
        facts={"altenheime": 80, "akutkrankenhaeuser": 5,
               "sonderkrankenhaeuser": 6, "kinderkliniken": 1},
    ),

    _e(
        "gefahr.veranstaltungen", "gefahrenobjekt", "rhein_sieg",
        "Grossveranstaltungen mit besonderen Risiken",
        """
Im Bedarfsplan ausdruecklich genannt:
- "Rhein in Flammen"
- "Autofreies Siegtal"
- Grosskirmes-Veranstaltungen
- groessere Stadtfeste
- groessere Weihnachtsmaerkte
- groessere Musikveranstaltungen
- Karnevals-Grossveranstaltungen

Grossversammlungsstaetten: Gross-Einkaufszentren, Rhein-Sieg-Forum Siegburg,
Jabachhalle Lohmar, Jungholzhalle Meckenheim sowie Objekte mit erhoehter
politischer und gesellschaftlicher Symbolkraft.

Fuer das DRK sind das die planbaren Einsaetze — Sanitaetsdienst im Vorfeld
beauftragt. Kritisch wird es, wenn eine Veranstaltung mit einer Wetterlage
zusammenfaellt: Dann trifft eine hohe Personendichte auf Sturm, Hitze oder
Gewitter, und aus dem geplanten Sanitaetsdienst wird eine Schadenslage.
        """,
        categories=["events", "weather", "manv"],
        tags=["Grossveranstaltung", "Karneval", "Weihnachtsmarkt", "Kirmes",
              "Rhein in Flammen", "Sanitaetsdienst"],
        trigger={"categories": ["events"], "min_score": 40},
    ),

    _e(
        "gefahr.troisdorf.eckdaten", "gefahrenobjekt", "troisdorf",
        "Troisdorf — Eckdaten",
        """
Einwohner: 74.953. Flaeche: 62,00 km². Bevoelkerungsdichte: 1.209 je km²
(Stand Bevoelkerungsfortschreibung im Bedarfsplan).

Troisdorf ist damit die einwohnerstaerkste Stadt des Rhein-Sieg-Kreises und
grosse kreisangehoerige Stadt mit eigener Feuerwehr und eigener
Rettungswachentraegerschaft.

Stadtteile mit abweichender rettungsdienstlicher Zuordnung: Altenrath (eigener
Versorgungsbereich), Bergheim, Muellekoven und Eschmar (Zuordnung
Niederkassel/Sieglar).
        """,
        categories=["health"],
        tags=["Troisdorf", "Einwohner", "Stadtteile", "Altenrath"],
        facts={"einwohner": 74953, "flaeche_km2": 62.0, "dichte": 1209},
    ),

    # ------------------------------------------------------------------
    # Ausloeser — woran man einen bevorstehenden Einsatz erkennt
    # ------------------------------------------------------------------

    _e(
        "ausloeser.wetter", "ausloeser", "rhein_sieg",
        "Angekuendigte Unwetterlage",
        """
Der Rettungsdienstbedarfsplan nennt "zu erwartende besondere Wetterlagen"
ausdruecklich als Grund fuer Sonderbedarf mit 24 Stunden Vorlauf und
"besondere Wetterlagen / Haeufung von witterungsbedingten Einsaetzen" als
Grund fuer Spitzenbedarf.

Praktisch heisst das: Eine amtliche Unwetterwarnung ab Stufe 3 (Unwetter) fuer
den Kreis ist ein belastbarer Vorbote fuer Kraeftebindung — auch ohne dass
schon etwas passiert ist. Typische Folgeeinsaetze: umgestuerzte Baeume,
ueberflutete Keller, Dachschaeden, Verkehrsunfaelle, Ausfall der
Stromversorgung, Betreuung Evakuierter.

Fuer die Bereitschaft bedeutet das erfahrungsgemaess zuerst Bereitstellung,
nicht sofort Ausrueckung.
        """,
        categories=["weather"],
        tags=["Unwetter", "Sturm", "Starkregen", "Vorlauf", "Bereitstellung"],
        trigger={"categories": ["weather"], "min_score": 60},
    ),

    _e(
        "ausloeser.hochwasser", "ausloeser", "troisdorf",
        "Steigende Pegel an Rhein und Sieg",
        """
Bei steigenden Pegeln laufen die Massnahmen gestuft: Beobachtung,
Deichverteidigung, Sperrungen, Raeumung gefaehrdeter Lagen, Betreuung der
Evakuierten. Der Betreuungsdienst wird typischerweise mit deutlichem zeitlichem
Abstand nach der Feuerwehr gebraucht — was Vorwarnung besonders wertvoll macht.

Betroffene Bereiche in Troisdorf: Rheinaue sowie die Sieg-nahen Ortslagen
Bergheim, Muellekoven und Eschmar.

Ein Hochwasser 2021er Praegung im Sieg-Einzugsgebiet ist die Lage, fuer die die
Betreuungskapazitaeten (BTP 500) und die ueberoertliche Hilfe gedacht sind.
        """,
        categories=["water"],
        tags=["Hochwasser", "Pegel", "Rhein", "Sieg", "Evakuierung",
              "Bergheim", "Muellekoven", "Eschmar"],
        trigger={"categories": ["water"], "min_score": 55},
    ),

    _e(
        "ausloeser.stromausfall", "ausloeser", "troisdorf",
        "Flaechendeckender Stromausfall",
        """
Ein laenger andauernder Stromausfall erzeugt Betreuungsbedarf, noch bevor
Verletzte auftreten: Ausfall von Heizung und Aufzuegen, Pflegeeinrichtungen
ohne Netzersatz, Ausfall der Telekommunikation und damit des Notrufs,
Menschen in steckengebliebenen Aufzuegen, Kaeltefolgen im Winter.

Die typische DRK-Antwort ist der Betreuungsplatz und die Einrichtung von
Anlaufstellen — im Landeskonzept der BTP 500 mit 72 Kraeften fuer 500
Betroffene.

Faustregel aus der Bedarfsplanung: Erst ab einer Dauer von mehreren Stunden
und einer Ausdehnung ueber ganze Ortslagen wird aus der Stoerung eine Lage.
Einzelne Strassenzuege sind Sache des Netzbetreibers.
        """,
        categories=["power"],
        tags=["Stromausfall", "Blackout", "Betreuungsplatz", "Notunterkunft",
              "Pflegeeinrichtung"],
        trigger={"categories": ["power"], "min_score": 60},
    ),

    _e(
        "ausloeser.grosslage_nachbar", "ausloeser", "rhein_sieg",
        "Grosslage im Nachbarkreis",
        """
Ueber das UEMANV-Konzept und die nachbarschaftliche Hilfe koennen Troisdorfer
Kraefte zu einer Lage ausserhalb des Kreises gerufen werden — nach Koeln, Bonn
oder in einen angrenzenden Kreis. Angefordert werden dann standardisierte
Komponenten, nicht einzelne Fahrzeuge.

Fuer die Bewertung heisst das: Eine Lage ausserhalb des eigenen Gebiets ist
nicht automatisch irrelevant, aber die Schwelle liegt deutlich hoeher. Ein
Ereignis muss die Groessenordnung erreichen, in der der betroffene Kreis seine
eigenen Mittel erschoepft hat.

Umgekehrt gilt: Wird UEMANV ausgeloest, laufen die Einsatzeinheiten — und damit
die Bereitschaften — als Ganzes, nicht einzelne Helfer.
        """,
        categories=["official_warning", "manv"],
        tags=["UEMANV", "Nachbarkreis", "Koeln", "Bonn", "ueberoertlich"],
        trigger={"categories": ["official_warning"], "min_score": 70},
    ),

    _e(
        "ausloeser.systemauslastung", "ausloeser", "rhein_sieg",
        "Hohe Grundauslastung des Rettungsdienstes",
        """
Der Bedarfsplan haelt fest, dass die Kapazitaet der regelhaft besetzten
Rettungsmittel besonders dann an die Leistungsgrenze kommt, wenn sie auch ohne
Schadensereignis hoch ausgelastet sind.

Daraus folgt ein oft uebersehener Fruehindikator: Nicht nur die Groesse eines
Ereignisses entscheidet ueber die Eskalation, sondern der Zustand des Systems
davor. Eine Grippewelle, eine Hitzeperiode oder ein Feiertagswochenende mit
hohem Einsatzaufkommen senken die Schwelle, ab der zusaetzliche Kraefte
alarmiert werden.
        """,
        categories=["health", "weather"],
        tags=["Auslastung", "Grundbedarf", "Leistungsgrenze", "Grippewelle"],
        trigger={"categories": ["health"], "min_score": 55},
    ),
]


# ======================================================================
# Eigenes Wissen des DRK Troisdorf
# ======================================================================
#
# Diese Eintraege stammen nicht aus oeffentlichen Dokumenten, sondern aus der
# Kenntnis der eigenen Einheit. Fuer die Lagebewertung sind sie die
# verlaesslichste Quelle ueberhaupt — oeffentlich belegbar sind sie nicht.
# Deshalb ``is_official=False``: nicht weniger wert, nur anders herkommend.
#
# Sie korrigieren mehrere Annahmen, die aus den oeffentlichen Quellen allein
# falsch gezogen worden waeren. Vor allem: Troisdorf ist Verpflegungs- und
# Betreuungsstandort, kein Rettungsdienststandort.

EIGEN = "DRK Troisdorf — eigene Angabe"


def _local(seed_key, kind, scope, title, body, *, categories=None, tags=None,
           trigger=None, facts=None):
    return _e(seed_key, kind, scope, title, body, categories=categories,
              tags=tags, trigger=trigger, facts=facts, source=EIGEN,
              source_url=None, source_date=None, is_official=False)


LOCAL_ENTRIES = [

    _local(
        "eigen.profil.troisdorf", "organisation", "troisdorf",
        "DRK Troisdorf — Einsatzprofil",
        """
Troisdorf ist vorrangig VERPFLEGUNGSSTANDORT, dazu Betreuungsstandort.
Kein Rettungsdienststandort.

Zustaendig fuer Verpflegungslagen von oertlich bis ueberoertlich sowie fuer
Betreuungslagen. Bei einem Massenanfall von Verletzten wirkt Troisdorf mit,
stellt dabei aber keine rettungsdienstliche Komponente.

Helferinnen und Helfer mit Sanitaetsausbildung sind vorhanden. Sie werden
ueberwiegend im Sanitaetsdienst bei Veranstaltungen eingesetzt, auch
aushilfsweise in Nachbargemeinden.

Ein kleiner Techniktrupp ist vorhanden. Seine Aufgabe ist vor allem die
Versorgung der eigenen in den Einsatz gebrachten Mittel, nicht die
selbststaendige technische Hilfeleistung.

Fuer die Lagebewertung heisst das: Eine Lage wird fuer Troisdorf nicht dadurch
relevant, dass Verletzte zu erwarten sind, sondern dadurch, dass ueber laengere
Zeit Menschen versorgt werden muessen — Einsatzkraefte oder Betroffene.
        """,
        categories=["manv", "events", "fire", "water", "power"],
        tags=["Verpflegung", "Betreuung", "Einsatzprofil", "Techniktrupp",
              "Sanitaetsdienst"],
    ),

    _local(
        "eigen.fahrzeuge.troisdorf", "ressource", "troisdorf",
        "DRK Troisdorf — Fahrzeuge und Material",
        """
- 1 MTF (Mannschaftstransportfahrzeug)
- 2 MZF (Mehrzweckfahrzeuge)
- 1 Kuechenanhaenger — eine einsatzbereite mobile Kueche mit Kuehlschrank,
  Kochplatte, Konvektomat und Gefrierschrank. Grosser Anhaenger, mobil als
  vollwertige Kueche einsetzbar.
- 1 Feldkueche
- 1 Betreuungsgespann, in Troisdorf stationiert. Es kann vom Land NRW in den
  Einsatz gebracht werden — damit reicht die Verwendung ueber den Kreis hinaus.

Das Betreuungsgespann ist der Grund, warum Troisdorf auch bei Lagen weit
ausserhalb des Kreises gezogen werden kann: Es ist eine Landesressource an
einem Troisdorfer Standort.
        """,
        categories=["fire", "water", "power", "events", "manv"],
        tags=["MTF", "MZF", "Kuechenanhaenger", "Feldkueche",
              "Betreuungsgespann", "Konvektomat", "Landesressource"],
        facts={"mtf": 1, "mzf": 2, "kuechenanhaenger": 1, "feldkueche": 1,
               "betreuungsgespann": 1},
    ),

    _local(
        "eigen.ausloeser.brand", "ausloeser", "troisdorf",
        "Haeufigster Einsatzanlass: Verpflegung bei Brandereignissen",
        """
Die mit Abstand haeufigste Einsatzgrundlage in Troisdorf sind
BRANDEREIGNISSE, bei denen Verpflegung fuer die Einsatzkraefte gestellt wird.

Massgeblich ist dabei nicht die Groesse des Brandes an sich, sondern die
EINSATZDAUER: Ein Feuer, das nach einer Stunde erledigt ist, braucht keine
Verpflegung. Ein Grossbrand ueber mehrere Schichten braucht sie sicher.

Achtung bei der Datenlage: Die Kategorie "Waldbrand" dieses Systems misst den
Waldbrandgefahrenindex des DWD — also die GEFAHR, nicht ein laufendes Feuer.
Tatsaechliche Brandereignisse erreichen das System ueber die Nachrichten und
ueber behoerdliche Warnungen. Ein hoher Gefahrenindex ist ein Vorbote, kein
Ereignis.
        """,
        categories=["fire", "news"],
        tags=["Brand", "Verpflegung", "Einsatzkraefteverpflegung",
              "Grossbrand", "Einsatzdauer"],
        trigger={"categories": ["fire", "news"], "min_score": 50},
    ),

    _local(
        "eigen.ausloeser.nachrichten", "ausloeser", "troisdorf",
        "Nachrichten sind der staerkste Einsatzindikator",
        """
Erfahrungswert der Einheit: Der zuverlaessigste Vorbote eines Einsatzes ist
die Presse. Ereignisse, die gross genug sind, um das DRK Troisdorf in den
Einsatz zu bringen, rufen fast immer auch die Presse auf den Plan.

Der Zusammenhang ist kein Zufall, sondern folgt aus dem Einsatzprofil: Was
Verpflegung oder Betreuung braucht, dauert lange und bindet viele Kraefte —
und genau das ist auch das, worueber berichtet wird. Kurze Einsaetze ohne
Pressewirkung brauchen umgekehrt selten Verpflegung.

Deshalb wiegt die Kategorie Nachrichten fuer Troisdorf ungewoehnlich schwer.
Wichtig bleibt der Ortsbezug: Eine Meldung ueber ein Ereignis in einem anderen
Kreis sagt wenig, eine ueber Troisdorf oder Siegburg sehr viel.
        """,
        categories=["news"],
        tags=["Presse", "Nachrichten", "Fruehindikator", "Erfahrungswert"],
        trigger={"categories": ["news"], "min_score": 45},
    ),

    _local(
        "eigen.ausloeser.evakuierung", "ausloeser", "troisdorf",
        "Evakuierungen in Troisdorf und Siegburg — Einsatz nahezu sicher",
        """
Bei Evakuierungen in TROISDORF oder SIEGBURG kann man sehr sicher davon
ausgehen, dass das DRK Troisdorf in den Einsatz geht.

Typische Anlaesse: Bombenfund und Entschaerfung, Grossbrand mit Raeumung,
Gebaeudeschaden, Hochwasser, Gefahrstoffaustritt.

Die Aufgabe ist dann Betreuung der Evakuierten und deren Verpflegung — beides
Kernaufgaben des Standorts. Anders als bei vielen anderen Lagen ist hier keine
Abwaegung noetig: Evakuierung im Kerngebiet bedeutet Einsatz.

Siegburg zaehlt dabei wie das eigene Stadtgebiet, obwohl es eine andere
Kommune ist — die Naehe und die eingespielte Zusammenarbeit machen den
Unterschied.
        """,
        categories=["water", "fire", "official_warning", "news", "power"],
        tags=["Evakuierung", "Raeumung", "Bombenfund", "Entschaerfung",
              "Siegburg", "Troisdorf", "Kerngebiet"],
        trigger={"categories": ["official_warning", "news"], "min_score": 40},
    ),

    _local(
        "eigen.ausloeser.veranstaltungen", "ausloeser", "troisdorf",
        "Sanitaetsdienst bei Veranstaltungen, auch in Nachbargemeinden",
        """
Der Sanitaetsdienst bei Veranstaltungen ist der planbare Teil des
Einsatzgeschehens. Troisdorfer Kraefte helfen dabei auch in Nachbargemeinden
aus.

Fuer die Bewertung bedeutet das: Bei Veranstaltungslagen ist der Ortsbezug
weiter zu fassen als sonst — eine Grossveranstaltung in einer Nachbargemeinde
kann Troisdorfer Kraefte binden, ohne dass in Troisdorf selbst etwas
stattfindet.

Kritisch wird es, wenn eine Veranstaltung mit einer Wetterlage zusammenfaellt.
Dann steht bereits Personal vor Ort, und aus dem geplanten Sanitaetsdienst
wird eine Schadenslage mit zusaetzlichem Verpflegungs- und Betreuungsbedarf.
        """,
        categories=["events", "weather"],
        tags=["Sanitaetsdienst", "Veranstaltung", "Nachbargemeinde",
              "Aushilfe"],
        trigger={"categories": ["events"], "min_score": 40},
    ),
]


LOCAL_ENTRIES += [

    _local(
        "eigen.alarmierungsweg", "doktrin", "troisdorf",
        "Alarmierungsweg des DRK Troisdorf",
        """
Zwei Wege fuehren zur Alarmierung:

1. Die KREISLEITSTELLE alarmiert den Fuehrungsdienst, dieser alarmiert intern.
2. Bei einer KLEINEN OERTLICHEN LAGE ruft die Feuerwehreinheit direkt beim
   Fuehrungsdienst an; auch dann alarmiert dieser intern.

In beiden Faellen steht der Fuehrungsdienst zwischen Anforderung und Einheit.
Es gibt keine automatische Durchalarmierung der Helferinnen und Helfer.

WAS DAS FUER DIESES SYSTEM BEDEUTET — eine ehrliche Grenze:

Der zweite Weg ist fuer ein Fruehwarnsystem unsichtbar. Ein Anruf der
Feuerwehr beim Fuehrungsdienst hinterlaesst keine Datenspur: keine
NINA-Meldung, keine Pressemeldung, keinen Messwert. Kleine oertliche
Verpflegungslagen kann dieses System deshalb grundsaetzlich nicht vorhersagen.

Vorhersagbar ist der erste Weg — Lagen, die gross genug sind, um ueber die
Leitstelle zu laufen, und die damit fast immer auch Spuren in Warnsystemen,
Messwerten oder der Presse hinterlassen. Genau darauf ist die Bewertung
ausgerichtet.

Wer das System beurteilt, sollte es an dieser Teilmenge messen, nicht an allen
Einsaetzen. Ein verpasster Kleineinsatz ist kein Fehler des Systems, sondern
liegt ausserhalb dessen, was es sehen kann.
        """,
        categories=["news", "fire", "official_warning"],
        tags=["Alarmierung", "Fuehrungsdienst", "Kreisleitstelle", "Feuerwehr",
              "Grenze", "Vorhersagbarkeit"],
    ),

    _local(
        "eigen.ortsstufen", "ausloeser", "troisdorf",
        "Raeumliche Abstufung der Einsatzrelevanz",
        """
Nicht jeder Ort wiegt gleich schwer:

- TROISDORF und SIEGBURG bilden das Kerngebiet. Siegburg ist dabei die
  wichtigste Nachbarkommune und zaehlt praktisch wie das eigene Stadtgebiet.
- NIEDERKASSEL, SANKT AUGUSTIN, LOHMAR und HENNEF sind ebenfalls von
  Bedeutung, aber eine Stufe darunter angeordnet.
- Der uebrige Rhein-Sieg-Kreis folgt mit deutlichem Abstand.
- Ausserhalb des Kreises wird es erst ab UEMANV-Groessenordnung relevant.

Diese Reihenfolge gilt fuer die Bewertung von Nachrichten und behoerdlichen
Warnungen, in denen ein Ort genannt wird.
        """,
        categories=["news", "official_warning", "fire", "water"],
        tags=["Siegburg", "Niederkassel", "Sankt Augustin", "Lohmar", "Hennef",
              "Kerngebiet", "Nachbarschaft", "Ortsbezug"],
    ),

    _local(
        "eigen.landesalarmierung", "erfahrung", "troisdorf",
        "Landesalarmierung des Betreuungsgespanns — Grundrate",
        """
Das in Troisdorf stationierte Betreuungsgespann kann vom Land NRW in den
Einsatz gebracht werden. Wie oft das tatsaechlich vorkommt:

- zuletzt beim AHRHOCHWASSER 2021
- davor nur ein- bis zweimal, mit sehr grossen Abstaenden dazwischen

Das ist grob eine Alarmierung pro Jahrzehnt.

Diese Grundrate ist wichtig fuer die Bewertung ueberoertlicher Lagen. Eine
Grosslage ausserhalb des Kreises ist real und gehoert angezeigt — aber die
Erwartung, deshalb selbst auszuruecken, waere nach aller Erfahrung falsch.
Deshalb werden ueberoertliche Lagen stark gedaempft.

Umgekehrt gilt: Wenn eine Lage die Groessenordnung des Ahrhochwassers
erreicht, ist die Daempfung hinfaellig. Solche Ereignisse erkennt man nicht an
einem Schwellenwert, sondern daran, dass mehrere Kategorien gleichzeitig
anschlagen und die Lage ueber Tage anhaelt.
        """,
        categories=["water", "official_warning"],
        tags=["Betreuungsgespann", "Landesalarmierung", "Ahrhochwasser",
              "Grundrate", "selten", "ueberoertlich"],
        facts={"letzte_alarmierung": "Ahrhochwasser 2021",
               "haeufigkeit": "etwa einmal pro Jahrzehnt"},
    ),
]


# ======================================================================
# Bekannte Grosslagen der Region
# ======================================================================

BONN = "Bundesstadt Bonn / Veranstalter Puetzchens Markt"
BONN_URL = "https://www.bonn.de/bonn-erleben/ausgehen-und-erleben/puetzchens-markt.php"

SEED_ENTRIES += [

    _e(
        "grosslage.puetzchens_markt", "gefahrenobjekt", "nachbarschaft",
        "Puetzchens Markt — groesste Grosslage der Region",
        """
Groesstes Volksfest der Region, jaehrlich in Bonn-Beuel, Stadtteil Puetzchen.

TERMIN: Freitag vor dem zweiten Sonntag im September bis zum Dienstag danach,
also fuenf Tage. 2026: 11. bis 15. September (657. Auflage). Die Regel gilt
jedes Jahr und ist im System hinterlegt — der Termin muss nicht gepflegt
werden.

GROESSE
- rund 1 Million Besucher, 2025 amtlich etwa 950.000
- 80.000 Quadratmeter Veranstaltungsflaeche
- etwa 500 Geschaefte, davon 170 auf dem Hauptgelaende mit 24 Fahrgeschaeften
- geoeffnet bis 3 Uhr nachts (Fr/Sa), sonst bis 1 Uhr
- Abschlussfeuerwerk am Dienstag gegen 22 Uhr

LAGE UND BEZUG ZU TROISDORF
Puetzchen liegt rechtsrheinisch in Bonn-Beuel, unmittelbar an der Grenze zu
Sankt Augustin. Es verkehren Sonderbuslinien aus der Region, darunter die
Linie P20 DIREKT AUS TROISDORF und die P40 ueber Sankt Augustin. Troisdorfer
Buergerinnen und Buerger sind dort also in relevanter Zahl unterwegs, auch
wenn Troisdorf selbst nicht Veranstaltungsort ist.

ORGANISATION DER GEFAHRENABWEHR
Feuerwehr, Rettungsdienst und Sanitaetsdienst sind gemeinsam in der
Marktschule stationiert. Dazu kommen eine Rettungswache auf dem Gelaende und
mobile Sanitaetstrupps, die die Marktstrassen abgehen. Die zentrale
Befehlsstelle liegt im Polizeipraesidium; Ordnungsamt und Polizei nutzen
Raeume in der Von-Ketteler-Strasse.
        """,
        categories=["events", "manv", "health", "traffic"],
        tags=["Puetzchens Markt", "Grossveranstaltung", "Kirmes", "Bonn",
              "Beuel", "Sanitaetsdienst", "P20", "Feuerwerk"],
        trigger={"categories": ["events"], "min_score": 30},
        facts={"besucher": 1000000, "flaeche_qm": 80000, "geschaefte": 500,
               "fahrgeschaefte": 24, "dauer_tage": 5},
        source=BONN, source_url=BONN_URL, source_date="2026-09",
    ),

    _e(
        "grosslage.puetzchens_markt.grundlast", "erfahrung", "nachbarschaft",
        "Puetzchens Markt — was normal ist (Grundlast)",
        """
Der wichtigste Teil des Wissens ueber diese Veranstaltung: Sie erzeugt im
Normalbetrieb eine hohe, aber voellig erwartbare Zahl an Hilfeleistungen.

AMTLICHE BILANZEN
2024: 98 Rettungsdiensteinsaetze, davon 13 mit Notarzt. Der Sanitaetsdienst
      leistete 279-mal Hilfe. Die Feuerwehr rueckte zu KEINEM Einsatz aus.
2025: rund 180 Behandlungen durch Sanitaets- und Rettungsdienst, davon 48
      Transporte ins Krankenhaus, 8 mit Notarztbegleitung. Die Feuerwehr war
      durchgehend praesent, musste aber ebenfalls nicht ausruecken.
      Dazu 132 abgeschleppte Fahrzeuge wegen blockierter Rettungswege und
      740 Verwarnungen wegen Falschparkens.

Beide Jahre wurden amtlich als ruhige Veranstaltung mit ueberschaubarer
Einsatzlage bewertet.

WAS DARAUS FOLGT
Eine Schlagzeile wie "Rettungsdienst im Dauereinsatz auf Puetzchens Markt"
beschreibt den NORMALZUSTAND, nicht eine Eskalation. Ohne dieses Wissen wuerde
das Fruehwarnsystem jeden September Alarm schlagen, ohne dass etwas
Ungewoehnliches passiert.

Massstab ist deshalb die Grundlast, nicht die absolute Zahl. Auffaellig wird
eine Meldung erst beim Etwa-Doppelten der Erwartungswerte.

EINE AUSNAHME: Die Grundlast der Feuerwehr ist NULL. In beiden ausgewerteten
Jahren gab es keinen einzigen Feuerwehreinsatz auf dem Gelaende. Jede Meldung
ueber einen Feuerwehreinsatz dort ist damit per Definition auffaellig — und
bei 80.000 Quadratmetern Kirmes mit Gasflaschen, Fritteusen und
Stromaggregaten ein ernstzunehmender Anlass.
        """,
        categories=["events", "news", "health", "fire"],
        tags=["Grundlast", "Erwartungswert", "Puetzchens Markt", "Bilanz",
              "Fehlalarm", "Rettungsdienst"],
        facts={"behandlungen_2024": 279, "rettungseinsaetze_2024": 98,
               "notarzt_2024": 13, "behandlungen_2025": 180,
               "transporte_2025": 48, "notarzt_2025": 8,
               "feuerwehreinsaetze": 0, "besucher_2025": 950000},
        source="Bundesstadt Bonn, Pressebilanzen 2024 und 2025",
        source_url="https://www.bonn.de/pressemitteilungen/september/erfolgreicher-puetzchens-markt-2025.php",
        source_date="2025-09",
    ),

    _e(
        "grosslage.puetzchens_markt.risiken", "ausloeser", "nachbarschaft",
        "Puetzchens Markt — woran eine echte Lage erkennbar waere",
        """
Die Veranstaltung laeuft geordnet. Die Punkte, an denen es kippen koennte:

WETTER. Fuenf Tage Freiflaeche mit bis zu sechsstelligen Besucherzahlen,
abends bis 3 Uhr. Sturm, Gewitter oder Starkregen treffen hier auf hohe
Personendichte und Fahrgeschaefte in Hoehe. Das ist der klassische Fall der
Kombilage — Veranstaltung und Wetterlage zusammen.

FEUERWERK AM DIENSTAG gegen 22 Uhr. Zeitpunkt der hoechsten Personendichte
und der schwierigsten Raeumung.

BLOCKIERTE RETTUNGSWEGE. 2025 wurden 132 Fahrzeuge abgeschleppt, weil sie
Rettungswege versperrten. Im Normalbetrieb ist das eine Ordnungswidrigkeit —
bei einer Raeumungslage waere es ein Problem.

BRANDGEFAHR. Gasflaschen, Fritteusen, Stromaggregate auf engem Raum. Die
Feuerwehr ist deshalb durchgehend vor Ort, obwohl sie in den ausgewerteten
Jahren nicht ausruecken musste.

GEWALTDELIKTE in den Abend- und Nachtstunden, schwerpunktmaessig auf dem
zentralen Platz. Die Polizei setzt 2026 zwei mobile Kameratuerme ein und hat
15 Personen mit Gewalthintergrund vorsorglich vom Gelaende ausgeschlossen.
Auf dem gesamten Gelaende gilt ein Messertrageverbot.

BEDEUTUNG FUER TROISDORF
Troisdorf ist nicht Veranstalter und stellt dort keinen regulaeren
Sanitaetsdienst. Relevant wird die Lage auf zwei Wegen: ueber die
nachbarschaftliche Hilfe bei einer Grossschadenslage, und ueber die
Troisdorfer Besucher, die mit der Sonderbuslinie P20 anreisen.
        """,
        categories=["events", "weather", "fire", "traffic", "manv"],
        tags=["Kombilage", "Feuerwerk", "Rettungsweg", "Brandgefahr",
              "Messerverbot", "Puetzchens Markt"],
        trigger={"categories": ["events", "weather"], "min_score": 40},
        source="Bundesstadt Bonn / Polizei Bonn, Einsatzkonzeption 2026",
        source_url="https://www.presseportal.de/blaulicht/pm/7304/6347705",
        source_date="2026-09",
    ),
]

# Alles, was beim Start eingespielt wird
ALL_ENTRIES = SEED_ENTRIES + LOCAL_ENTRIES
