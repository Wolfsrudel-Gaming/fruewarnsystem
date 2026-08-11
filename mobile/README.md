# DRK Troisdorf Frühwarnsystem — Mobile App (Flutter)

Flutter-App zum Frühwarnsystem. Zeigt Lagebild, Pegelstände, Waldbrandgefahr,
Verkehr und Alarme des Backends an und empfängt Live-Updates per WebSocket.

## Anbindung an den Server (Sync)

1. Das Web-Dashboard (https://riegel-troisdorf.de/fruelage) zeigt unten die Karte
   **„Mobile App verbinden"** mit dem Sync-Link.
2. Diesen Link in der App unter **Einstellungen → Server-Verbindung** eintragen
   und speichern (Persistenz über `shared_preferences`, Key `server_url`).
3. Die App nutzt danach automatisch:
   - REST-API: `<sync_url>/api/dashboard/...`
   - WebSocket: `<sync_url>` mit `http→ws` ersetzt + `/ws`

Maschinenlesbare Verbindungsdaten liefert `GET <sync_url>/api/system/app-connect`
(z. B. für einen künftigen QR-Code-Pairing-Flow).

**Vollständige API-Referenz mit allen Endpunkten und Datenformaten:
[`../docs/API.md`](../docs/API.md)** — bitte bei App-Erweiterungen dagegen entwickeln.

## Struktur

```
lib/
  main.dart                 App-Einstieg, Navigation
  models/api_models.dart    Datenmodelle für die API-Antworten
  services/
    api_service.dart        REST-Client (Basis-URL konfigurierbar)
    websocket_service.dart  Live-Updates mit Auto-Reconnect
    app_state.dart          Zentraler App-State
  screens/                  10 Screens (Lagebild, Alarme, Karte, Verlauf, ...)
  widgets/                  Risk-Gauge, Karten, Score-Balken
  theme/app_theme.dart      DRK-Dunkeltheme
```

## Entwicklung

```bash
cd mobile
flutter pub get
flutter run          # gegen Emulator; Standard-URL http://10.0.2.2:8000
flutter test
flutter build apk    # Release-Build Android
```

Für Tests gegen die Produktion in den App-Einstellungen
`https://riegel-troisdorf.de/fruelage` als Server-URL setzen.

## Zusammenarbeit

Die App (`mobile/`) wird von Claude Code weiterentwickelt, Webseite/Backend von Cursor —
Details und Regeln in [`../docs/ZUSAMMENARBEIT.md`](../docs/ZUSAMMENARBEIT.md).
Wichtigste Regel: Das Backend ändert von der App genutzte Endpunkte nie inkompatibel;
neue Anforderungen an die API in `docs/API.md` dokumentieren.
