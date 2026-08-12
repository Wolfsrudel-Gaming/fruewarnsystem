import 'dart:typed_data';
import 'dart:ui' show Color;
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

/// Notification-Kanäle:
/// - fws_alarm:   Kritische Alarme — Vollbild, Alarmton, starke Vibration
/// - fws_alerts:  Normale Alarme — hohe Priorität
/// - fws_service: Persistente Notification des Hintergrund-Dienstes
class NotificationService {
  static const alarmChannelId = 'fws_alarm';
  static const alertChannelId = 'fws_alerts';
  static const serviceChannelId = 'fws_service';

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

    await android.createNotificationChannel(const AndroidNotificationChannel(
      alarmChannelId,
      'Kritische Alarme',
      description: 'Vollbild-Weckruf bei Score ≥ 80 — mit Alarmton',
      importance: Importance.max,
      playSound: true,
      enableVibration: true,
    ));
    await android.createNotificationChannel(const AndroidNotificationChannel(
      alertChannelId,
      'Alarme',
      description: 'Neue Alarme des Frühwarnsystems',
      importance: Importance.high,
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
}
