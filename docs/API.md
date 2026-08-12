# API-Referenz für die Mobile App

Diese Doku beschreibt die Schnittstelle zwischen Backend und Flutter-App (`mobile/`).
Alle hier gelisteten Endpunkte sind stabil: Felder werden nur ergänzt, nie umbenannt
oder entfernt (siehe `docs/ZUSAMMENARBEIT.md`).

## Basis-URL / Sync-Link

Produktion: **`https://riegel-troisdorf.de/fruelage`**

Dieser Link wird auf der Webseite (Karte „Mobile App verbinden") angezeigt und in der
App unter *Einstellungen → Server-Verbindung* eingetragen. Alle Pfade unten sind
relativ dazu, z. B. `GET https://riegel-troisdorf.de/fruelage/api/dashboard/overview`.

Interaktive Swagger-Doku: `https://riegel-troisdorf.de/fruelage/api/docs` (falls per Nginx freigegeben)
bzw. lokal `http://127.0.0.1:8010/docs` auf dem Server.

## Verbindungsdaten (maschinenlesbar)

`GET /api/system/app-connect`

```json
{
  "name": "DRK Troisdorf Frühwarnsystem",
  "sync_url": "https://riegel-troisdorf.de/fruelage",
  "api_url": "https://riegel-troisdorf.de/fruelage/api",
  "ws_url": "wss://riegel-troisdorf.de/fruelage/ws",
  "hint": "Diese URL in der App unter Einstellungen → Server-Verbindung eintragen."
}
```

Geeignet für einen späteren QR-Code-/Deeplink-Pairing-Flow in der App.

## Von der App genutzte Endpunkte

### `GET /api/dashboard/overview` — Lagebild

```json
{
  "overall_score": 42.5,
  "risk_scores": {
    "water":   { "score": 65, "components": { "detail": "...", "contributions": [ ... ] }, "calculated_at": "…" },
    "fire":    { "score": 100, "components": { ... }, "calculated_at": "…" }
  },
  "active_alerts": [
    { "id": 1, "category": "water", "score": 80, "title": "…", "description": "…",
      "escalation_level": 1, "acknowledged": false, "triggered_at": "…" }
  ],
  "last_updated": "2026-08-11T23:00:00"
}
```

**Kategorie-Schlüssel**: `risk_scores` enthält jede Kategorie unter **zwei Schlüsseln** —
dem englischen Enum-Wert und dem deutschen Alias (identisches Objekt). Die App kann
direkt die deutschen Schlüssel verwenden:

| Deutsch (Alias) | Englisch (Enum) | Label |
|---|---|---|
| `hochwasser` | `water` | Hochwasser |
| `wetter` | `weather` | Wetter |
| `waldbrand` | `fire` | Waldbrand |
| `verkehr` | `traffic` | Verkehr |
| `luftqualitaet` | `air_quality` | Luftqualität |
| `nachrichten` | `news` | Nachrichten |
| `warnungen` | `official_warning` | Behördenwarnungen |
| `erdbeben` | `seismic` | Erdbeben |
| `strahlung` | `radiation` | Strahlung |
| `gesundheit` | `health` | Gesundheit |
| `strom` | `power` | Stromnetz |
| `veranstaltungen` | `events` | Veranstaltungen |
| `schifffahrt` | `shipping` | Schifffahrt |

Jeder Score enthält zusätzlich `label` (deutscher Anzeigename). Alarme enthalten
zusätzlich `category_label`. `components.contributions` enthält die Einzelbegründungen
pro Score (`source`, `source_type`, `value`, `points`, `reason`, `timestamp`).

Der Parameter `category` bei `/api/dashboard/history/risk-scores` akzeptiert
ebenfalls beide Schreibweisen (z. B. `?category=hochwasser`).

### `GET /api/dashboard/water?hours=24` — Pegelstände

```json
{ "stations": [ { "station_id": "…", "station_name": "…", "river": "Sieg",
  "current_level": 82, "trend": "falling", "warning_level": 0,
  "condition": "niedrigwasser", "last_update": "…",
  "history": [ { "level_cm": 82, "timestamp": "…", "trend": "falling" } ] } ] }
```

### `GET /api/dashboard/weather?hours=24` — Wetterwarnungen/Vorhersagen

```json
{ "warnings": [ … ], "forecasts": [ … ], "radar": [ … ] }
```

Jedes Element: `id`, `type`, `region`, `severity`, `title`, `description`,
`parameters`, `valid_from`, `valid_to`, `source`, `created_at`.

### `GET /api/dashboard/weather-forecast` — Aktuelles Wetter + 24h + 30 Tage

```json
{
  "current":     { "temperature": 31.2, "apparent_temperature": 33.0, "humidity": 38,
                   "precipitation": 0.0, "weather_code": 1, "wind_speed": 12.4, "wind_gusts": 28.1 },
  "hourly_24h":  { "time": [...], "temperature_2m": [...], "precipitation": [...],
                   "precipitation_probability": [...], "weather_code": [...], "wind_speed_10m": [...] },
  "climate_30d": { "hot_days": 16, "very_hot_days": 3, "dry_days": 26, "max_dry_streak": 12,
                   "rain_sum_mm": 15.2, "avg_tmax": 29.8, "heat_drought_level": 3,
                   "heat_drought_label": "hoch", "summary": "…",
                   "rain_next_24h_mm": 0.0, "max_hourly_rain_mm": 0.0,
                   "rain_last_24h_mm": 0.0, "rain_last_72h_mm": 0.0 },
  "climate_daily": { "time": [...], "temperature_2m_max": [...], "precipitation_sum": [...] },
  "updated_at": "…"
}
```

### `GET /api/dashboard/fire` — Waldbrandgefahr

```json
{ "risks": [ { "id": 1, "region": "Köln/Bonn (Wahner Heide)", "risk_index": 3,
  "temperature": null, "humidity": null, "wind_speed": null, "wind_direction": null,
  "rain_last_24h": null, "satellite_hotspots": 0, "timestamp": "…", "source": "dwd_fire_index" } ] }
```

`risk_index` = offizieller DWD-Waldbrandgefahrenindex **1–5**.

### `GET /api/dashboard/traffic?active_only=true` — Verkehr

```json
{ "events": [ { "id": 1, "road": "A59", "event_type": "…", "title": "…", "description": "…",
  "lat": 50.8, "lon": 7.1, "severity": 2, "source": "…", "started_at": "…" } ] }
```

### `GET /api/dashboard/alerts?active_only=true&limit=100` — Alarme

```json
{ "alerts": [ { "id": 1, "category": "water", "score": 80, "title": "…", "description": "…",
  "is_active": true, "acknowledged": false, "escalation_level": 1,
  "triggered_at": "…", "resolved_at": null } ] }
```

### `POST /api/dashboard/alerts/{id}/acknowledge` — Alarm quittieren

Antwort: `{ "status": "acknowledged", "id": 1 }`. Unbekannte ID → HTTP 404.

### `GET /api/dashboard/power?hours=24` — Stromnetz im Detail

Liefert je Regelzone den aktuellsten Stand plus Verlauf: Erzeugungsmix nach
Energieträger, Netzlast, Bilanz, EE-Anteil, Börsenpreis und Erzeugungsprognose.

```json
{
  "regions": [
    {
      "region": "DE", "region_label": "Deutschland",
      "consumption_mw": 55243.0, "generation_mw": 72425.0,
      "balance_mw": 17182.0, "renewable_share": 0.931,
      "price_eur_mwh": 14.57, "forecast_total_mw": 73855.0,
      "is_stressed": false, "stress_indicator": null,
      "generation_parts": { "Photovoltaik": 57146.0, "Biomasse": 4863.0 },
      "renewable_parts": { "Photovoltaik": 57146.0 }
    }
  ],
  "history": [ … ]
}
```

Erfasst werden zwei Regelzonen: `DE` (bundesweit) und `Amprion` — die
Regelzone, in der Troisdorf liegt. Netzstress wird **nur bundesweit**
bewertet, eine einzelne Regelzone hat keine eigene Bilanz.

#### Verifizierte SMARD-Filter

Alle IDs wurden empirisch gegen die Live-API geprüft. Zwei Fallstricke, die
hier bereits Fehler verursacht haben, sind eigens vermerkt.

| ID | Bedeutung | Einheit |
|---|---|---|
| 410 | Netzlast (Stromverbrauch) | MW |
| 1223 / 1225 / 1226 / 1227 | Biomasse / Braunkohle / Steinkohle / Erdgas | MW |
| 4066 / 4067 / **124** / 4068 | Wasserkraft / Wind Onshore / **Wind Offshore** / Photovoltaik | MW |
| 4069 / 4070 / 4071 / 1224 | Sonstige EE / Pumpspeicher / Sonstige Konv. / Kernenergie | MW |
| 122 | Prognostizierte Erzeugung gesamt | MW |
| 252 | Großhandelspreis Deutschland/Luxemburg | EUR/MWh |

**Nicht verwenden:**
- **4359** ist *kein* „Erzeugung gesamt". SMARD hat überhaupt keinen
  Summenfilter — die Gesamterzeugung muss aus den Einzelarten summiert
  werden. 4359 fällt, wenn die PV-Einspeisung steigt (residuallast-artig).
- **4169** ist *kein* Wind Offshore, sondern eine Preiszeitreihe in EUR/MWh
  (läuft im Gleichlauf mit 252). Wind Offshore ist **124**.

Verfügbar sind 6 Auflösungen (`quarterhour`, `hour`, `day`, `week`, `month`,
`year`) und 11 Regionen (`DE`, `AT`, `LU`, `DE-LU`, `DE-AT-LU`, die vier
Übertragungsnetzbetreiber `50Hertz`/`Amprion`/`TenneT`/`TransnetBW`, `APG`,
`CREOS`). Nicht jede Erzeugungsart existiert in jeder Regelzone — Amprion
hat z.B. keine Braunkohle.

## Lernschleife: Rückmeldungen und Selbstkalibrierung

Das System lernt aus den Rückmeldungen der Einsatzkräfte, wie zuverlässig
seine Warnungen sind, und passt Gewichtung und Auslöseschwelle je Kategorie
täglich an (nachts um 3:30 Uhr, oder manuell per `recompute`).

### `POST /api/dashboard/alerts/{id}/feedback` — Kam es zum Einsatz?

```json
{
  "outcome": "einsatz",
  "deployment_type": "Kellerauspumpen",
  "forces_count": 12,
  "severity_rating": 4,
  "notes": "Pegel stieg schneller als erwartet"
}
```

`outcome` ist eines von `einsatz` (Volltreffer), `vorsorge` (kein Einsatz,
aber Warnung war berechtigt — zählt halb), `kein_einsatz` (Fehlalarm),
`unklar` (fließt nicht ins Lernen ein). Alle Felder außer `outcome` sind
optional. Erneutes Senden zur selben Alarm-ID korrigiert die Rückmeldung.
Bei `einsatz` wird automatisch ein verknüpfter Einsatz protokolliert.

### `GET /api/dashboard/alerts/pending-feedback?days=14` — offene Rückmeldungen

Quittierte Alarme ohne Rückmeldung. Die App zeigt sie als eigenen Tab.

### `POST /api/dashboard/deployments` — Einsatz melden

Auch **ohne** vorherigen Alarm — das ist die wichtigste Lernquelle, weil
solche Einsätze zeigen, wo das System blind war.

```json
{
  "category": "hochwasser",
  "title": "Kellerauspumpen Bergstraße",
  "occurred_at": "2026-08-11T18:00:00",
  "forces_count": 8,
  "severity_rating": 3
}
```

Der Server sucht selbst nach einem passenden Alarm (gleiche Kategorie,
in den 12 Stunden vor dem Einsatz) und setzt `was_predicted` entsprechend.
Antwort enthält `was_predicted`, `matched_alert_id` und einen Klartext-`hinweis`.

| Endpunkt | Inhalt |
|---|---|
| `GET /api/dashboard/deployments?days=180` | Einsatzhistorie |
| `DELETE /api/dashboard/deployments/{id}` | Fehleingabe zurücknehmen |
| `GET /api/dashboard/calibration` | Lernstatus: Precision/Recall gesamt und je Kategorie, gelernte Anpassungen mit Begründung |
| `POST /api/dashboard/calibration/recompute?window_days=180` | Kalibrierung sofort neu berechnen |
| `PUT /api/dashboard/calibration/{category}/lock?locked=true` | Kategorie gegen Auto-Anpassung sperren |

**Wie angepasst wird:** Ab 5 bewertbaren Rückmeldungen je Kategorie. Ein
verpasster Einsatz wiegt doppelt so schwer wie ein Fehlalarm — das System
wird lieber einmal zu oft laut. Anpassungen sind gedämpft (35% pro Lauf) und
begrenzt (Gewicht 0,7–2,0×, Schwelle ±15 Punkte). Behördliche Warnungen und
Strahlungsalarme werden nie gedämpft, nur empfindlicher.

## Weitere verfügbare Endpunkte (aktuell nicht von der App genutzt)

| Endpunkt | Inhalt |
|---|---|
| `GET /api/dashboard/news?relevant_only=false&limit=100` | News inkl. KI-Analyse (`ai_analysis`), Relevanz-Score, `is_relevant` |
| `GET /api/dashboard/warnings` | Behördenwarnungen (NINA etc.) |
| `GET /api/dashboard/air-quality` | Luftqualität |
| `GET /api/dashboard/thresholds` | Alarm-Schwellenwerte |
| `GET /api/dashboard/history/risk-scores?category=hochwasser&hours=24` | Score-Verlauf (Kategorie optional, deutsche Aliasse ok) |
| `GET /api/dashboard/scoring/live` | Live-Scoring mit allen Beiträgen |
| `GET /api/system/status`, `GET /api/system/health` | Systemstatus |

### Rohdaten-Endpunkte (alles, was der Server sammelt)

`GET /api/dashboard/data` listet alle Datensätze mit Eintragszahl der letzten 7 Tage.
`GET /api/dashboard/data/{dataset}?hours=168&limit=200` liefert die Rohdaten
(alle Tabellenspalten, neueste zuerst; `include_raw=true` liefert zusätzlich `raw_data`).

| Datensatz | Inhalt |
|---|---|
| `seismic` | Erdbeben (BGR/EMSC) |
| `radiation` | Radioaktivität / ODL-Messnetz (BfS) |
| `health` | Intensivbetten-Kapazität (RKI) |
| `power` | Stromnetz-Status |
| `shipping` | Schifffahrts-Warnungen (PEGELONLINE) |
| `fuel` | Kraftstoff-Verfügbarkeit (Tankerkönig) |
| `transit` | ÖPNV/Bahn-Störungen |
| `lightning` | Blitzdaten |
| `soil-moisture` | Bodenfeuchte |
| `drought` | Dürremonitor |
| `flood-warnings` | Hochwasser-Meldestufen |
| `gdac` | GDACS Katastrophen-Alerts |
| `events` | Veranstaltungskalender |

Quellen (Stand 2026-08): Intensivregister über RKI-GitHub-CSV, Strom über SMARD
(Filter 4359/410), Schifffahrt über PEGELONLINE (GlW/HSW Bonn/Köln), ÖPNV über
KVB-Betriebslage + VRR-ADDINFO, Hochwasser-Meldestufen über OpenHygon (LANUV)
+ PEGELONLINE Rhein.

## WebSocket (Live-Updates)

`wss://riegel-troisdorf.de/fruelage/ws` — die App bildet die URL selbst aus der
Basis-URL (`http`→`ws`, + `/ws`).

- Client darf `"ping"` (Text) senden → Server antwortet `{"type": "pong"}`.
- Der Server broadcastet nach jedem Collector-Lauf:

```json
{ "type": "score_update", "source": "<collector-name>", "scores": { "<kategorie>": { "score": …, … } } }
```

Nach einer `update`-Nachricht sollte die App die betroffenen Daten neu laden
(oder direkt die mitgelieferten Scores verwenden).

## Risiko-Logik (Kurzüberblick für App-Darstellung)

- Score pro Kategorie: **0–100**; Stufen im Frontend: <25 grün, <50 gelb, <75 orange, ≥75 rot.
- Querauswertungen fließen als eigene `contributions` ein, z. B.:
  - Regenprognose → Überflutungs-Boost im Wasser-Score (verstärkt ×1,5 bei erhöhten Pegeln).
  - 30-Tage-Hitze/Trockenheit → Boost im Feuer- und Wetter-Score.
  - Niedrigwasser/Dürre → Boost im Feuer-Score.
- `source_type: "cross_analysis"` kennzeichnet solche Querauswertungs-Beiträge.

## Bekannte Punkte in der App (für Claude Code)

1. **`FireRiskData.windDirection`**: Die App parst `wind_direction` als `String?`,
   der Server liefert aber **Float** (Grad). Sobald das Feld befüllt ist, wirft
   `fromJson` eine Exception — und weil `refreshAll()` alle Fetches in einem
   `Future.wait` bündelt, reißt ein einzelner Parse-Fehler **alle** Daten mit
   („Verbindung fehlgeschlagen"). Empfehlung: `(json['wind_direction'] as num?)?.toDouble()`
   und die Fetches einzeln absichern.
2. **`FireRiskData.satelliteHotspots`**: App erwartet `int?`, Server liefert **JSONB**
   (Liste/Objekt der Hotspots). Empfehlung: als Liste parsen oder `length` verwenden.
3. Kategorie-Schlüssel: erledigt — der Server liefert jetzt deutsche Aliasse
   (siehe Tabelle oben), die App muss nichts ändern.
4. WebSocket: erledigt — der Server sendet jetzt `type: "score_update"`,
   wie von der App erwartet.
