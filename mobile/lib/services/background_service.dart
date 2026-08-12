import 'dart:async';
import 'dart:convert';
import 'dart:ui';

import 'package:flutter_background_service/flutter_background_service.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import 'notification_service.dart';

/// Hintergrund-Dienst: hält auch bei geschlossener App eine Verbindung
/// zum Frühwarnsystem (WebSocket + Polling-Fallback) und schlägt bei
/// neuen Alarmen Alarm — kritische (Score >= 80) als Vollbild-Weckruf.
class BackgroundAlarmService {
  static const _prefEnabled = 'bg_service_enabled';
  static const _prefSeenIds = 'bg_seen_alert_ids';

  static Future<bool> isEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_prefEnabled) ?? true;
  }

  static Future<void> setEnabled(bool enabled) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_prefEnabled, enabled);
    final service = FlutterBackgroundService();
    if (enabled) {
      await service.startService();
    } else {
      service.invoke('stop');
    }
  }

  static Future<void> initialize() async {
    final service = FlutterBackgroundService();
    final enabled = await isEnabled();

    await service.configure(
      androidConfiguration: AndroidConfiguration(
        onStart: onStart,
        isForegroundMode: true,
        autoStart: enabled,
        autoStartOnBoot: enabled,
        notificationChannelId: NotificationService.serviceChannelId,
        initialNotificationTitle: 'DRK Frühwarnsystem',
        initialNotificationContent: 'Überwachung aktiv',
        foregroundServiceNotificationId: 888,
        foregroundServiceTypes: [AndroidForegroundType.dataSync],
      ),
      iosConfiguration: IosConfiguration(),
    );
  }
}

@pragma('vm:entry-point')
void onStart(ServiceInstance service) async {
  DartPluginRegistrant.ensureInitialized();
  await NotificationService.initialize();

  WebSocketChannel? channel;
  Timer? reconnectTimer;
  Timer? pollTimer;
  var stopped = false;

  Future<String> baseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.reload();
    return prefs.getString('server_url') ?? 'http://10.0.2.2:8000';
  }

  Future<void> handleAlert(Map<String, dynamic> alert) async {
    final id = alert['id'] as int? ?? 0;
    final score = (alert['score'] as num?)?.toDouble() ?? 0;
    final acknowledged = alert['acknowledged'] as bool? ?? false;
    if (acknowledged) return;

    final prefs = await SharedPreferences.getInstance();
    await prefs.reload();
    final seen = prefs.getStringList(BackgroundAlarmService._prefSeenIds) ?? [];
    if (seen.contains('$id')) return;
    seen.add('$id');
    // Liste begrenzen, damit die Prefs nicht unbegrenzt wachsen
    while (seen.length > 200) {
      seen.removeAt(0);
    }
    await prefs.setStringList(BackgroundAlarmService._prefSeenIds, seen);

    final critical = score >= 80;
    await NotificationService.showAlert(
      id: id,
      title: critical
          ? '🔴 KRITISCHER ALARM (Score ${score.round()})'
          : '⚠️ Alarm: Score ${score.round()}',
      body: '${alert['title'] ?? ''}\n${alert['description'] ?? ''}',
      critical: critical,
    );
  }

  Future<void> pollAlerts() async {
    try {
      final url = await baseUrl();
      final resp = await http
          .get(Uri.parse('$url/api/dashboard/alerts?active_only=true'))
          .timeout(const Duration(seconds: 20));
      if (resp.statusCode != 200) return;
      final data = jsonDecode(resp.body) as Map<String, dynamic>;
      for (final a in (data['alerts'] as List? ?? [])) {
        await handleAlert(a as Map<String, dynamic>);
      }
    } catch (_) {}
  }

  // connect und scheduleReconnect rufen sich gegenseitig auf
  late final Future<void> Function() connect;

  void scheduleReconnect() {
    if (stopped) return;
    reconnectTimer?.cancel();
    reconnectTimer = Timer(const Duration(seconds: 30), connect);
  }

  connect = () async {
    if (stopped) return;
    try {
      final url = await baseUrl();
      final wsUrl = url.replaceFirst('http', 'ws');
      channel = WebSocketChannel.connect(Uri.parse('$wsUrl/ws'));
      channel!.stream.listen(
        (data) {
          try {
            final msg = jsonDecode(data as String) as Map<String, dynamic>;
            if (msg['type'] == 'alert' && msg['alert'] is Map<String, dynamic>) {
              handleAlert(msg['alert'] as Map<String, dynamic>);
            }
          } catch (_) {}
        },
        onError: (_) => scheduleReconnect(),
        onDone: () => scheduleReconnect(),
      );
    } catch (_) {
      scheduleReconnect();
    }
  };

  service.on('stop').listen((_) async {
    stopped = true;
    reconnectTimer?.cancel();
    pollTimer?.cancel();
    channel?.sink.close();
    await service.stopSelf();
  });

  await connect();
  // Polling-Fallback: fängt Alarme ab, die während WS-Ausfällen entstanden sind
  pollTimer = Timer.periodic(const Duration(minutes: 3), (_) => pollAlerts());
  await pollAlerts();
}
