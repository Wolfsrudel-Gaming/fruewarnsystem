import 'package:shared_preferences/shared_preferences.dart';

/// Wie laut ein Ereignis gemeldet wird.
enum AlarmStaerke {
  /// Voller Weckruf: Vollbild, Alarmton, starke Vibration — kommt auch bei
  /// gesperrtem Bildschirm und im Stumm-Modus durch.
  weckruf,

  /// Normale Benachrichtigung mit Ton.
  meldung,

  /// Nur ein Eintrag in der Leiste, kein Ton.
  still,

  /// Gar nichts.
  keine,
}

/// Einstellbare Ruhezeiten.
///
/// Die Einheit wollte einen vollen Weckalarm, aber frei einstellbare
/// Ruhezeiten — nicht „nachts nie" und nicht „immer volle Lautstärke".
/// Innerhalb der Ruhezeit weckt nur noch, was die Schwelle überschreitet.
class RuhezeitEinstellung {
  final bool aktiv;

  /// Minuten seit Mitternacht
  final int startMinute;
  final int endeMinute;

  /// Ab dieser Einsatzerwartung wird auch in der Ruhezeit geweckt.
  /// Standard: nur „Einsatz wahrscheinlich".
  final String weckStufe;

  const RuhezeitEinstellung({
    this.aktiv = false,
    this.startMinute = 22 * 60,
    this.endeMinute = 6 * 60,
    this.weckStufe = 'einsatz_wahrscheinlich',
  });

  /// Liegt der Zeitpunkt in der Ruhezeit?
  ///
  /// Behandelt den Normalfall mit: Die Ruhezeit läuft über Mitternacht,
  /// Start liegt also später am Tag als das Ende.
  bool giltZu(DateTime zeit) {
    if (!aktiv) return false;
    final minute = zeit.hour * 60 + zeit.minute;
    if (startMinute == endeMinute) return false;
    if (startMinute < endeMinute) {
      return minute >= startMinute && minute < endeMinute;
    }
    return minute >= startMinute || minute < endeMinute;
  }

  String get startText => _hhmm(startMinute);
  String get endeText => _hhmm(endeMinute);

  static String _hhmm(int minuten) {
    final h = (minuten ~/ 60).toString().padLeft(2, '0');
    final m = (minuten % 60).toString().padLeft(2, '0');
    return '$h:$m';
  }

  RuhezeitEinstellung copyWith({
    bool? aktiv,
    int? startMinute,
    int? endeMinute,
    String? weckStufe,
  }) {
    return RuhezeitEinstellung(
      aktiv: aktiv ?? this.aktiv,
      startMinute: startMinute ?? this.startMinute,
      endeMinute: endeMinute ?? this.endeMinute,
      weckStufe: weckStufe ?? this.weckStufe,
    );
  }

  static const _kAktiv = 'ruhezeit_aktiv';
  static const _kStart = 'ruhezeit_start';
  static const _kEnde = 'ruhezeit_ende';
  static const _kStufe = 'ruhezeit_weckstufe';

  static Future<RuhezeitEinstellung> laden() async {
    final prefs = await SharedPreferences.getInstance();
    return RuhezeitEinstellung(
      aktiv: prefs.getBool(_kAktiv) ?? false,
      startMinute: prefs.getInt(_kStart) ?? 22 * 60,
      endeMinute: prefs.getInt(_kEnde) ?? 6 * 60,
      weckStufe: prefs.getString(_kStufe) ?? 'einsatz_wahrscheinlich',
    );
  }

  Future<void> speichern() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_kAktiv, aktiv);
    await prefs.setInt(_kStart, startMinute);
    await prefs.setInt(_kEnde, endeMinute);
    await prefs.setString(_kStufe, weckStufe);
  }
}

/// Rangfolge der Einsatzerwartung. Höher heißt dringender.
const Map<String, int> kStufenRang = {
  'ruhe': 0,
  'beobachtung': 1,
  'bereitstellung_moeglich': 2,
  'bereitstellung_wahrscheinlich': 3,
  'einsatz_wahrscheinlich': 4,
};

int stufenRang(String? stufe) => kStufenRang[stufe] ?? 0;

/// Entscheidet, wie laut eine Änderung der Einsatzerwartung gemeldet wird.
///
/// Bewusst eine reine Funktion ohne Zugriff auf Zeit, Einstellungen oder
/// Plugins — damit die Regel prüfbar bleibt. Sie ist der Kern der
/// Alarmierung, und ein Fehler hier bedeutet entweder einen verschlafenen
/// Einsatz oder einen Weckruf um drei Uhr nachts ohne Anlass.
AlarmStaerke bewerteStufenwechsel({
  required String? alteStufe,
  required String neueStufe,
  required DateTime jetzt,
  required RuhezeitEinstellung ruhezeit,
}) {
  final alt = stufenRang(alteStufe);
  final neu = stufenRang(neueStufe);

  // Entspannung: Eine Entwarnung ist auch eine Information — man weiß, dass
  // man wieder abschalten kann. Aber sie weckt niemanden.
  if (neu < alt) {
    return neu <= stufenRang('beobachtung')
        ? AlarmStaerke.meldung
        : AlarmStaerke.still;
  }

  // Keine Änderung: nichts melden. Ohne diese Regel meldete sich die App bei
  // jedem Abruf erneut.
  if (neu == alt) return AlarmStaerke.keine;

  final inRuhezeit = ruhezeit.giltZu(jetzt);
  final ueberWeckschwelle = neu >= stufenRang(ruhezeit.weckStufe);

  if (neu >= stufenRang('einsatz_wahrscheinlich')) {
    // Der eigentliche Alarmfall. In der Ruhezeit nur, wenn die eingestellte
    // Weckschwelle das hergibt — sie steht standardmäßig genau hier.
    if (inRuhezeit && !ueberWeckschwelle) return AlarmStaerke.meldung;
    return AlarmStaerke.weckruf;
  }

  if (neu >= stufenRang('bereitstellung_wahrscheinlich')) {
    if (inRuhezeit && !ueberWeckschwelle) return AlarmStaerke.still;
    return AlarmStaerke.meldung;
  }

  if (neu >= stufenRang('bereitstellung_moeglich')) {
    return inRuhezeit ? AlarmStaerke.still : AlarmStaerke.meldung;
  }

  return AlarmStaerke.still;
}

/// Text für die Benachrichtigung eines Stufenwechsels.
({String titel, String text}) stufenwechselText({
  required String? alteStufe,
  required String neueStufe,
  required String neuesLabel,
  String? anlass,
}) {
  final steigt = stufenRang(neueStufe) > stufenRang(alteStufe);
  if (!steigt) {
    return (
      titel: 'Lage entspannt sich',
      text: anlass == null
          ? 'Einsatzerwartung zurück auf: $neuesLabel'
          : 'Einsatzerwartung zurück auf: $neuesLabel — $anlass',
    );
  }
  return (
    titel: neuesLabel,
    text: anlass ?? 'Die Einsatzerwartung für die Bereitschaft ist gestiegen.',
  );
}
