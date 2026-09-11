# Soziale Netze als Frühwarnquelle

Wer auf einem Volksfest steht und etwas sieht, schreibt darüber — oft Minuten
bis Viertelstunden, bevor eine Leitstelle eine Meldung herausgibt. Bei einer
Großlage ist genau diese Vorlaufzeit der ganze Gewinn.

Und es ist der unzuverlässigste Kanal, den das System hat. Deshalb gelten drei
Regeln ohne Ausnahme:

1. **Ein Beitrag ist ein Gerücht, kein Ereignis.** Ausgewertet wird nie ein
   einzelner Beitrag, sondern das *Aufkommen*: mehrere unabhängige Konten, die
   binnen kurzer Zeit dasselbe zu einem Ort schreiben.
2. **Soziale Netze tragen nichts zum Gesamtrisiko bei.** Ihr Beitrag zum
   Gesamtwert ist null. Sie wirken ausschließlich über das Signal
   `social_aufkommen`, das bei *Bereitstellung* gedeckelt ist — sie können das
   System aufmerksam machen, nie alarmieren.
3. **Jeder Hinweis trägt „UNBESTÄTIGT“.** Immer, ohne Ausnahme.

---

## Stand der Zugänge

Geprüft am 11.09.2026 gegen die jeweiligen Schnittstellen.

| Netz | Zugang | Was es kostet | Status |
|---|---|---|---|
| **Mastodon** | Öffentliche Hashtag-Zeitleisten | — | **läuft** |
| **Telegram** | Öffentliche Kanalvorschau `t.me/s/<kanal>` | — | **läuft** |
| **Bluesky** | Beitragssuche, verlangt Anmeldung | — | bereit, Zugangsdaten fehlen |
| **X (Twitter)** | API v2, Suche der letzten 7 Tage | ~0,005 USD je gelesenem Beitrag | bereit, Token fehlt |
| **Facebook** | Graph API, Beiträge benannter Seiten | — (Freigabe nötig) | bereit, Token fehlt |
| **Instagram** | Graph API, Hashtag-Suche | — (Geschäftskonto nötig) | bereit, Zugangsdaten fehlen |
| **TikTok** | Research API | — (Antrag nötig) | bereit, Zugangsdaten fehlen |

Was gerade tatsächlich mithört, steht unter
`GET /api/dashboard/social/platforms`. Der Endpunkt nennt zu jedem stillen Netz
ausdrücklich, **welcher** Schalter fehlt — denn ein stilles Netz kann zweierlei
heißen: Es ist ruhig, oder es ist gar nicht angeschlossen. Für ein Warnsystem
ist das ein gewaltiger Unterschied.

---

## Was die vier großen Netze verlangen

### X (Twitter)
Der freie Zugang ist ersatzlos entfallen. Seit Februar 2026 rechnet X je Abruf
ab; die alten Pauschaltarife (Basic 200 USD/Monat) sind für Neukunden
geschlossen. Für dieses System ist die Abfrage klein — drei Ortsbegriffe, alle
paar Minuten —, aber es ist eine laufende Ausgabe und deshalb eine
Kostenentscheidung, keine technische.

*Einschalten:* App-only Bearer Token im Entwicklerportal anlegen, als
`FWS_X_BEARER_TOKEN` hinterlegen.

### Facebook
Eine allgemeine Suche über Facebook gibt es nicht mehr. Lesbar sind die
Beiträge **benannter Seiten**. Seiten, die man selbst verwaltet, gehen sofort.
Für fremde Seiten — Feuerwehr, Stadt, Polizei — braucht die App die
Berechtigung *Page Public Content Access*, die Meta einzeln prüft
(Unternehmensnachweis, mehrere Wochen).

Für ein Warnsystem ist das ohnehin der bessere Weg als eine Suche: Die
Feuerwehrseite meldet Einsätze zuverlässiger als zufällige Passanten.

*Einschalten:* `FWS_META_ACCESS_TOKEN` und `FWS_FACEBOOK_SEITEN`.

### Instagram
Die Hashtag-Suche ist die einzige öffentliche Suche, die Instagram noch
anbietet. Sie verlangt ein Business- oder Creator-Konto, verbunden mit einer
Facebook-Seite, und eine von Meta geprüfte App.

Harte Grenze: **30 verschiedene Hashtags je Woche und Konto.** Deshalb fragt
das System nur drei Hashtags ab und merkt sich deren Kennungen, statt sie bei
jedem Durchlauf neu zu holen — sonst wäre das Wochenkontingent binnen Stunden
aufgebraucht und die Quelle für den Rest der Woche tot.

Instagram gibt bei der Hashtag-Suche keinen Urheber heraus. Da die
Aufkommensmessung *unabhängige Konten* zählt, dient die Beitragskennung als
Ersatzurheber — sonst würden hundert Beiträge als ein Konto zählen.

*Einschalten:* `FWS_META_ACCESS_TOKEN` und `FWS_INSTAGRAM_BUSINESS_ID`.

### TikTok
Öffentliche Daten gibt TikTok nur über die Research API heraus. Zugang haben
Forschungseinrichtungen und **gemeinnützige Organisationen mit einem
Forschungszweck im öffentlichen Interesse** — ein Warnsystem im
Bevölkerungsschutz kann das begründen, muss den Antrag aber stellen; einen
Selbstbedienungszugang gibt es nicht.

Die zweite Schnittstelle (Display API) zeigt ausschließlich die eigenen Videos
des angemeldeten Kontos und ist für Lagefrüherkennung wertlos.

*Einschalten:* `FWS_TIKTOK_CLIENT_KEY` und `FWS_TIKTOK_CLIENT_SECRET`.

---

## Was bewusst *nicht* gebaut wurde

Für jedes dieser Netze gibt es Umwege: Spiegelseiten wie Nitter, gemietete
Weiterleitungen wie RSSHub, ausgelesene Web-Oberflächen, undokumentierte
Endpunkte der Apps. Sie sind hier nicht eingebaut, und das ist eine
Entscheidung, keine Lücke:

- Sie verstoßen gegen die Nutzungsbedingungen der Betreiber.
- Sie brechen bei jeder Änderung der Gegenseite — ohne Vorwarnung und ohne
  Fehlermeldung, die nach einem Fehler aussieht. Sie liefern dann einfach
  nichts mehr, und **nichts sieht aus wie Ruhe.**

Eine Frühwarnquelle, die sich jederzeit lautlos in Stille verwandeln kann, ist
schlimmer als eine, die es gar nicht erst verspricht. Ein Test hält das fest
(`test_keine_umgehung_ueber_spiegelseiten`).

---

## Telegram im Besonderen

Telegram ist das einzige der neu erschlossenen Netze, das ohne Schlüssel läuft:
Jeder öffentliche Kanal ist unter `t.me/s/<name>` als schlichte HTML-Seite
lesbar. Das ist keine Umgehung, sondern die von Telegram dafür vorgesehene
Vorschau.

Die Einschränkung: **Es gibt keine Suche.** Man muss die Kanäle kennen. Eine
Recherche nach offiziellen Kanälen von Feuerwehr, Polizei oder Kreis in der
Region hat keine ergeben — deutsche Behörden nutzen Telegram kaum.
Voreingestellt ist deshalb nur die `tagesschau`, die bei einer überörtlichen
Lage früh berichtet und über die Ortserkennung auch flächige Lagen
(„bundesweit", „Nordrhein-Westfalen") erfasst.

Regionale Kanäle lassen sich jederzeit über `FWS_TELEGRAM_KANAELE` ergänzen,
kommagetrennt und ohne `@`.

---

## Wie ein Beitrag durchs System läuft

```
Netz  →  Beitrag  →  bewerte_beitrag()  →  gespeichert?  →  finde_aufkommen()
                     Ereignis UND Ort       nur wenn ja      mehrere Konten?
                                                                   ↓
                                                        social_aufkommen-Signal
                                                        (max. Bereitstellung,
                                                         immer UNBESTÄTIGT)
```

`bewerte_beitrag()` verlangt **beides**: ein Ereigniswort *und* einen Ortsbezug.
„Großbrand in Hamburg" fällt durch (kein Ortsbezug), „Schöner Sonnenuntergang
über Troisdorf" ebenfalls (kein Ereignis). Übungsankündigungen und Rückblicke
werden ausdrücklich entwertet.

Beiträge ohne Ereignisbezug werden gar nicht erst gespeichert; gespeicherte
Beiträge werden nach drei Tagen gelöscht. Als Archiv taugen Gerüchte ohnehin
nicht.
