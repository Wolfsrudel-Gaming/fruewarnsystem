# Zusammenarbeit & Workflow

Dieses Dokument beschreibt, wie an diesem Projekt gearbeitet wird: wer welchen Bereich
verantwortet, wie Deployment funktioniert und welche Regeln beim Committen gelten.

## Arbeitsteilung

| Bereich | Verzeichnisse | Verantwortlich |
|---|---|---|
| **Webseite & Server** (Backend, Frontend, Deployment, Collectors, Risiko-Engine) | `backend/`, `frontend/`, `docker/`, `docker-compose.yml`, `scripts/` | **Cursor** (arbeitet direkt auf dem Server) |
| **Mobile App** (Flutter) | `mobile/` | **Claude Code** |
| Doku & Design-Referenzen | `docs/` | beide |

Regeln:

- Jeder bleibt in seinem Bereich. Änderungen am jeweils anderen Bereich nur, wenn nötig
  (z. B. neuer Backend-Endpunkt für die App) — dann im Commit klar benennen.
- Die App spricht das Backend **ausschließlich über die dokumentierte API** an,
  siehe [`docs/API.md`](API.md). Neue Endpunkt-Wünsche dort ergänzen bzw. anfragen.
- Backend-Endpunkte, die die App bereits nutzt, dürfen nicht inkompatibel geändert werden
  (Felder nur hinzufügen, nicht umbenennen/entfernen).

## Branch & Deployment

- Arbeitsbranch: **`claude/drk-troisdorf-early-warning-h4bdz3`** — alle committen direkt hierauf.
- Produktion: `https://riegel-troisdorf.de/fruelage` (Server-Checkout: `/opt/fruewarnsystem`).
- **Auto-Deploy**: Ein dedizierter Updater-Container prüft **alle 60 Sekunden** auf neue
  Commits auf dem Branch. Bei Änderungen: Pull → gezielter Rebuild/Neustart nur der
  betroffenen Services → Health-Check → ntfy-Benachrichtigung.
  - Änderungen in `backend/` → Backend wird neu gebaut und neu gestartet.
  - Änderungen in `frontend/` → Frontend wird neu gebaut und neu gestartet.
  - Änderungen in `mobile/` oder `docs/` → **kein** Neustart (kein Server-Deployment nötig).
- **Rücksynchronisation**: Commits, die direkt auf dem Server entstehen, werden vom
  Updater automatisch nach GitHub gepusht. Vor dem Push von außen daher immer erst
  `git pull` — der Branch kann sich durch Server-Commits bewegt haben.

## Commit-Regeln

- Deutsche, aussagekräftige Commit-Messages: erste Zeile = Was/Warum, danach Details
  als Aufzählung (siehe `git log` für den etablierten Stil).
- Ein Commit pro Thema; App- und Webseiten-Änderungen nicht mischen.
- Nie force-pushen — der Server-Updater erkennt Non-Fast-Forward nicht und
  Produktions-Commits könnten verloren gehen.
- Keine Secrets committen: `.env` ist gitignored, Konfig-Vorlagen gehören in `.env.example`.

## Wichtige Konfiguration (Server)

- `.env` auf dem Server (nicht im Repo), relevante Werte:
  - `FWS_PUBLIC_URL=https://riegel-troisdorf.de/fruelage` — öffentliche Basis-URL,
    wird u. a. für den App-Sync-Link verwendet.
  - `FWS_OLLAMA_MODEL=llama3.2:3b` — lokales LLM für News-Analyse.
  - `FWS_AUTO_UPDATE_ENABLED=false` — der interne Backend-Updater ist deaktiviert,
    der dedizierte Updater-Container ist die einzige Deployment-Instanz.
- Alle Ports sind localhost-only gebunden; öffentlich erreichbar ist nur der
  Host-Nginx unter `/fruelage` (Frontend, `/fruelage/api` Backend, `/fruelage/ws` WebSocket).

## App ⇄ Webseite

- Die Webseite zeigt unten die Karte **„Mobile App verbinden"** mit dem Sync-Link
  (`FWS_PUBLIC_URL`). Dieser Link wird in der App unter
  *Einstellungen → Server-Verbindung* eingetragen.
- Maschinenlesbar liefert `GET /api/system/app-connect` dieselben Verbindungsdaten
  (API-URL, WebSocket-URL) — nützlich z. B. für einen späteren QR-Code-/Deeplink-Flow.
- Details zu allen Endpunkten und Datenformaten: [`docs/API.md`](API.md).
