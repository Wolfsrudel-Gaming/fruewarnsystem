# DRK Troisdorf Frühwarnsystem

Echtzeit-Frühwarnsystem für das Deutsche Rote Kreuz Troisdorf. Erkennt eskalierende Lagen und warnt automatisch bei drohendem Einsatzbedarf.

## Features

- **Hochwasser-Monitoring**: Pegelstände (Rhein, Sieg, Agger + Nebenbäche), adaptive Abfrageintervalle, Trend-Analyse
- **Wetter**: DWD-Warnungen, animiertes Regenradar, MOSMIX-Vorhersagen, Echtzeit-Blitzdaten, Windanalyse
- **Waldbrand**: DWD-Gefahrenindex, NASA FIRMS Satellitenhotspots, Wahner Heide Geofencing
- **Luftqualität**: PM2.5/PM10, Ozon, NO2 mit Anomalie-Erkennung
- **Behördenwarnungen**: NINA, KATWARN, MoWaS, EU-Alert
- **Nachrichten**: RSS-Feed Aggregation mit KI-Relevanzfilter (lokales LLM)
- **Verkehr**: Autobahn-API, Bahnstörungen, Gefahrgut-Monitoring
- **Veranstaltungen**: Web-Scraping + manuelle Eingabe für Großevents

### Alarmsystem

- Dynamischer Risiko-Score (0-100) pro Kategorie
- Konfigurierbarer mehrstufiger Eskalationspfad: Push → Telegram → SMS → Anruf
- Komplette Alarm-Historisierung
- KI-gestützte Lageberichte (lokales Ollama LLM)

### Ausgabekanäle

- **Web-Dashboard**: Grafana-ähnlich, Drag&Drop Widgets, DRK-Dunkelrot-Theme, Kiosk-Modus
- **Telegram Bot**: Interaktiv mit Karten, Charts, Inline-Buttons
- **Push**: FCM + ntfy.sh Self-hosted Fallback
- **E-Mail**: Täglicher Lagebericht
- **Home Assistant**: Bidirektionale MQTT-Integration

### Auto-Update

Das System hält sich automatisch aktuell:
- Dedizierter Auto-Update Container prüft alle 30 Minuten auf neue Commits
- Automatischer Pull, Build und Neustart
- Rollback bei fehlgeschlagenem Build
- Health-Check nach Update
- Benachrichtigung über ntfy.sh bei Updates

## Schnellstart

```bash
git clone https://github.com/wolfsrudel-gaming/fruewarnsystem.git
cd fruewarnsystem
./scripts/install.sh
```

Das Install-Script:
1. Prüft Docker, Docker Compose, Git
2. Erstellt `.env` aus Template mit sicherem Key
3. Baut alle Container
4. Startet das System
5. Lädt das LLM-Modell

## Manueller Start

```bash
cp .env.example .env
# .env anpassen
docker compose up -d
```

## Services

| Service | Port | Beschreibung |
|---------|------|-------------|
| Dashboard | 3000 | Web-Frontend |
| API | 8000 | Backend REST + WebSocket |
| API Docs | 8000/docs | Swagger UI |
| Prometheus | 9090 | Metriken |
| Grafana | 3001 | Monitoring-Dashboards |
| Uptime Kuma | 3002 | Uptime-Monitoring |
| Nginx | 80/443 | Reverse Proxy |

## Architektur

```
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Frontend │  │ Telegram │  │ Flutter  │
│ Next.js  │  │   Bot    │  │   App    │
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │              │
     └──────┬──────┴──────────────┘
            │ REST + WebSocket
     ┌──────┴──────┐
     │   Backend   │
     │   FastAPI   │
     ├─────────────┤
     │ Collectors  │─── DWD, Pegelonline, NINA, ...
     │ Analyzers   │─── Ollama LLM, Regelbasiert
     │ Alerting    │─── Score-Engine, Eskalation
     │ Notifier    │─── Push, Telegram, SMS, Email
     │ Auto-Update │─── Git Pull, Docker Rebuild
     └──────┬──────┘
            │
  ┌─────────┼─────────┐
  │         │         │
┌─┴──┐  ┌──┴──┐  ┌──┴───┐
│ PG │  │Redis│  │Ollama│
└────┘  └─────┘  └──────┘
```

## Konfiguration

Alle Einstellungen über Umgebungsvariablen in `.env`. Siehe `.env.example` für alle Optionen.

## Lizenz

MIT
