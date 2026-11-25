# Quellenbefund vom 25.11.2026

Alle 50 in den Collectors hinterlegten Adressen einzeln live abgefragt.

## Behoben

| Quelle | Befund | Maßnahme |
|---|---|---|
| **Radioaktivität BfS** | `odlinfo.bfs.de/json/stat.json` → **404**. Pfad nach `/daten/json/` umgezogen *und* Form geändert: dort stehen nur noch Kennzahlen, keine Stationsreihen. | WFS `imis.bfs.de` zur Hauptquelle gemacht (1673 Stationen, Stundenwerte, 15 im Umkreis inkl. **Troisdorf-Altenrath**). Bundesmittel aus dem neuen Pfad als Plausibilitätsprüfung. |
| **Pegel Sieg + Agger** | PEGELONLINE führt nur Bundeswasserstraßen. Von 102 geführten Gewässern ist **keines** Sieg oder Agger. Beide Einträge standen mit `uuid=None` in der Liste und lieferten still `None`. | Aus der PEGELONLINE-Liste entfernt. Sieg und Agger kommen über OpenHygon/LANUV (Menden, Siegburg Kaldenhausen, Lohmar, Eitorf) — das lief schon im `hochwasser_collector`. |
| **Luftqualität OpenAQ** | v2 → **HTTP 410** („Version 1 and Version 2 API endpoints are retired"), v3 verlangt API-Schlüssel. | Stillgelegt. Das Umweltbundesamt liefert dieselben Werte ohne Schlüssel und lief bereits parallel. |
| **Verkehr NRW** | `verkehr.nrw/.../getAll` → **404** mit 209 KB HTML-Fehlerseite. Kein dokumentierter Nachfolger. | Ausfall im Code dokumentiert. Autobahn-GmbH-API deckt A3, A59, A560 ab und läuft. **Lücke: Landes- und Kreisstraßen.** |
| **OpenData Bonn** | Beide genutzten Datensätze (`warnmeldung-feuerwehr-bonn`, `veranstaltungen-veranstaltungkalender-bonn`) → **404**. Von 288 Datensätzen existiert nur noch `standorte-der-berufs-und-freiwilligen-feuerwehr` (statisch). | Feuerwehr Bonn läuft jetzt über presseportal (Dienststelle 115888). **Lücke: Veranstaltungskalender Bonn.** |

## Braucht einen Schlüssel oder eine Anmeldung

| Quelle | Befund |
|---|---|
| **NASA FIRMS** (Satelliten-Hotspots) | `Invalid MAP_KEY` — kostenlose Registrierung nötig. Scheitert derzeit bei jedem Durchlauf. |
| **Störungsauskunft Strom** | **401** — war offen, verlangt jetzt Authentifizierung. |
| **Bahn-Störungen** | **403 `OPS_BLOCKED`** — blockt Rechenzentrums-Adressen. Vom eigenen Server **möglicherweise** erreichbar. |

## Läuft

PEGELONLINE · OpenHygon/LANUV · DWD Warnungen · DWD Waldbrandindex · NINA/MoWaS · SMARD · Autobahn GmbH · Umweltbundesamt · BfS-WFS · USGS · GDACS · KVB · VRR · ogc-api.nrw Erdbeben · Mastodon · Telegram

## Umgebungsabhängig

`open-meteo` antwortete mit **429** und `luadb.it.nrw.de` war nicht erreichbar. Beides kommt aus **dieser** Umgebung (Rechenzentrums-Adresse hinter einem Proxy) und sagt nichts über den eigenen Server — wie schon bei Bluesky im September.

## Was das strukturell heißt

Fünf Ausfälle, und **keiner davon war sichtbar**. Zwei Muster:

1. **404 mit großem HTML-Körper.** Verkehr NRW lieferte 209 KB Fehlerseite — für jede Prüfung, die auf die Antwortgröße schaut, eine besonders ergiebige Quelle.
2. **Ein stiller Rückfall deckt den Ausfall.** Die Radioaktivität lief über den WFS weiter. Das ist gut — aber monatelang unbemerkt auf einem Rückfall zu stehen, ausgerechnet in der Kategorie, die dieses System nie abwertet, ist kein guter Zustand.

Deshalb meldet seit dem 14.09. jeder Nachrichtenabruf seinen Erfolg oder Misserfolg an `source_health` (`/api/dashboard/sources`). Für die übrigen Collectors steht das noch aus.
