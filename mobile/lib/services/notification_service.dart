import 'dart:typed_data';
import 'dart:ui' show Color;
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import 'alarm_policy.dart';

/// Notification-Kanäle:
/// - fws_alarm:   Kritische Alarme — Vollbild, Alarmton, starke Vibration
/// - fws_alerts:  Normale Alarme — hohe Priorität
/// - fws_calm:    Entwarnung — leise, aber sichtbar
/// - fws_quiet:   Stille Meldung während der Ruhezeit
/// - fws_service: Persistente Notification des Hintergrund-Dienstes
class NotificationService {
  static const alarmChannelId = 'fws_alarm';
  static const alertChannelId = 'fws_alerts';
  static const serviceChannelId = 'fws_service';
  static const calmChannelId = 'fws_calm';
  static const quietChannelId = 'fws_quiet';

  static final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  static Future<void> initialize() async {
    const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
    await _plugin.initialize(
      const InitializationSettings(android: androidInit),
    );

    final android = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    if (android == null) return;

    // Der Kanal selbst muss auf Alarm-Nutzung stehen, nicht nur die einzelne
    // Meldung: Android entscheidet anhand des Kanals, ob ein Ton im
    // Stumm-Modus und bei Nicht-Stören durchkommt.
    await android.createNotificationChannel(const AndroidNotificationChannel(
      alarmChannelId,
      'Weckruf',
      description: 'Voller Weckruf, wenn ein Einsatz wahrscheinlich wird',
      importance: Importance.max,
      playSound: true,
      enableVibration: true,
      audioAttributesUsage: AudioAttributesUsage.alarm,
    ));
    await android.createNotificationChannel(const AndroidNotificationChannel(
      alertChannelId,
      'Alarme',
      description: 'Neue Alarme des Frühwarnsystems',
      importance: Importance.high,
    ));
    await android.createNotificationChannel(const AndroidNotificationChannel(
      quietChannelId,
      'Stille Meldung',
      description: 'Hinweise während der eingestellten Ruhezeit',
      importance: Importance.low,
      playSound: false,
      enableVibration: false,
    ));
    await android.createNotificationChannel(const AndroidNotificationChannel(
      calmChannelId,
      'Entwarnung',
      description: 'Meldung, wenn sich die Lage wieder entspannt',
      importance: Importance.defaultImportance,
    ));
    await android.createNotificationChannel(const AndroidNotificationChannel(
      serviceChannelId,
      'Hintergrund-Überwachung',
      description: 'Dauerhafte Verbindung zum Frühwarnsystem',
      importance: Importance.low,
    ));
  }

  /// Android 13+: Laufzeit-Permission für Notifications anfragen
  static Future<void> requestPermissions() async {
    final android = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    await android?.requestNotificationsPermission();
    // Android 14+: Vollbild-Intent kann gesondert deaktiviert sein
    await android?.requestFullScreenIntentPermission();
  }

  /// Alarm anzeigen. Bei [critical] als Vollbild-Weckruf mit Alarmton,
  /// der auch bei gesperrtem Bildschirm durchkommt.
  static Future<void> showAlert({
    required int id,
    required String title,
    required String body,
    required bool critical,
  }) async {
    final details = AndroidNotificationDetails(
      critical ? alarmChannelId : alertChannelId,
      critical ? 'Kritische Alarme' : 'Alarme',
      importance: critical ? Importance.max : Importance.high,
      priority: critical ? Priority.max : Priority.high,
      category: critical
          ? AndroidNotificationCategory.alarm
          : AndroidNotificationCategory.recommendation,
      fullScreenIntent: critical,
      playSound: true,
      audioAttributesUsage:
          critical ? AudioAttributesUsage.alarm : AudioAttributesUsage.notification,
      enableVibration: true,
      vibrationPattern: critical
          ? Int64List.fromList([0, 600, 250, 600, 250, 600, 250, 600])
          : null,
      styleInformation: BigTextStyleInformation(body),
      color: const Color(0xFFCC1A1A),
      colorized: critical,
    );

    await _plugin.show(
      id,
      title,
      body,
      NotificationDetails(android: details),
    );
  }

  /// Meldung eines Stufenwechsels der Einsatzerwartung.
  ///
  /// Die Stärke bestimmt der Aufrufer über [AlarmPolicy] — hier wird nur
  /// noch ausgegeben, was dort entschieden wurde.
  static Future<void> showStufenwechsel({
    required int id,
    required String title,
    required String body,
    required AlarmStaerke staerke,
  }) async {
    if (staerke == AlarmStaerke.keine) return;

    final weckruf = staerke == AlarmStaerke.weckruf;
    final still = staerke == AlarmStaerke.still;

    final details = AndroidNotificationDetails(
      weckruf
          ? alarmChannelId
          : still
              ? quietChannelId
              : alertChannelId,
      weckruf
          ? 'Weckruf'
          : still
              ? 'Stille Meldung'
              : 'Alarme',
      importance: weckruf
          ? Importance.max
          : still
              ? Importance.low
              : Importance.high,
      priority: weckruf
          ? Priority.max
          : still
              ? Priority.low
              : Priority.high,
      category: weckruf
          ? AndroidNotificationCategory.alarm
          : AndroidNotificationCategory.status,
      fullScreenIntent: weckruf,
      playSound: !still,
      audioAttributesUsage: weckruf
          ? AudioAttributesUsage.alarm
          : AudioAttributesUsage.notification,
      enableVibration: !still,
      vibrationPattern: weckruf
          ? Int64List.fromList([0, 600, 250, 600, 250, 600, 250, 600])
          : null,
      styleInformation: BigTextStyleInformation(body),
      color: const Color(0xFFCC1A1A),
      colorized: weckruf,
    );

    await _plugin.show(id, title, body, NotificationDetails(android: details));
  }

  /// Entwarnung — sichtbar, aber ohne Ton und ohne Vibration.
  static Future<void> showEntwarnung({
    required int id,
    required String title,
    required String body,
  }) async {
    const details = AndroidNotificationDetails(
      calmChannelId,
      'Entwarnung',
      importance: Importance.defaultImportance,
      priority: Priority.defaultPriority,
      category: AndroidNotificationCategory.status,
      playSound: false,
      enableVibration: false,
      color: Color(0xFF22C55E),
    );
    await _plugin.show(id, title, body,
        const NotificationDetails(android: details));
  }
}
