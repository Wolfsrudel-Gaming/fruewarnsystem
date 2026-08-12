import 'dart:async';
import 'package:flutter/material.dart';
import '../models/api_models.dart';
import 'api_service.dart';
import 'websocket_service.dart';

class AppState extends ChangeNotifier {
  final ApiService api;
  late final WebSocketService _ws;
  Timer? _pollTimer;

  OverviewData? overview;
  List<AlertData> alerts = [];
  List<WaterStation> waterStations = [];
  List<WeatherWarning> weatherWarnings = [];
  List<FireRiskData> fireRisks = [];
  List<TrafficEventData> trafficEvents = [];
  List<OfficialWarningData> officialWarnings = [];
  List<AirQualityReading> airQuality = [];
  List<Map<String, dynamic>> thresholds = [];
  Map<String, dynamic>? liveScoring;

  bool loading = true;
  String? error;
  bool wsConnected = false;

  /// Wird gesetzt, wenn per WebSocket ein kritischer Alarm (Score >= 80)
  /// eintrifft. Die UI zeigt dann den Vollbild-Alarm und ruft
  /// [clearCriticalAlert] auf.
  AlertData? pendingCriticalAlert;
  final Set<int> _seenCriticalIds = {};

  AppState({required this.api}) {
    _ws = WebSocketService(baseUrl: api.baseUrl);
    _init();
  }

  Future<void> _init() async {
    await refreshAll();
    _connectWs();
    _pollTimer = Timer.periodic(const Duration(seconds: 60), (_) => refreshAll());
  }

  void _connectWs() {
    _ws.connect();
    _ws.stream.listen((msg) {
      final type = msg['type'] as String?;
      if (type == 'update') {
        // Collector-Lauf abgeschlossen — Scores haben sich evtl. geaendert
        refreshAll();
      } else if (type == 'alert') {
        final alertJson = msg['alert'] as Map<String, dynamic>?;
        if (alertJson != null) {
          final alert = AlertData.fromJson(alertJson);
          if (alert.score >= 80 && !_seenCriticalIds.contains(alert.id)) {
            _seenCriticalIds.add(alert.id);
            pendingCriticalAlert = alert;
          }
        }
        refreshAll();
      }
    });
  }

  void clearCriticalAlert() {
    pendingCriticalAlert = null;
  }

  /// Nach Aenderung der Server-URL: Verbindung neu aufbauen.
  void reconnect() {
    _ws.reset(api.baseUrl);
    refreshAll();
  }

  Future<void> refreshAll() async {
    try {
      final results = await Future.wait([
        api.fetchOverview(),
        api.fetchAlerts(),
        api.fetchWaterStations(),
        api.fetchWeatherWarnings(),
        api.fetchFireRisk(),
        api.fetchTraffic(),
        api.fetchThresholds(),
        api.fetchOfficialWarnings(),
        api.fetchAirQuality(),
      ]);

      overview = results[0] as OverviewData?;
      alerts = results[1] as List<AlertData>? ?? [];
      waterStations = results[2] as List<WaterStation>? ?? [];
      weatherWarnings = results[3] as List<WeatherWarning>? ?? [];
      fireRisks = results[4] as List<FireRiskData>? ?? [];
      trafficEvents = results[5] as List<TrafficEventData>? ?? [];
      thresholds = results[6] as List<Map<String, dynamic>>? ?? [];
      officialWarnings = results[7] as List<OfficialWarningData>? ?? [];
      airQuality = results[8] as List<AirQualityReading>? ?? [];
      error = overview == null ? 'Verbindung fehlgeschlagen' : null;

      // Fallback: Kritische Alarme auch ohne WS-Event erkennen (z.B. App
      // war im Hintergrund, Poll findet neuen unquittierten Alarm >= 80).
      for (final a in alerts) {
        if (a.score >= 80 && !a.acknowledged && !_seenCriticalIds.contains(a.id)) {
          _seenCriticalIds.add(a.id);
          pendingCriticalAlert = a;
        }
      }
    } catch (e) {
      error = 'Verbindung fehlgeschlagen';
    }
    wsConnected = _ws.isConnected;
    loading = false;
    notifyListeners();
  }

  Future<bool> acknowledgeAlert(int alertId) async {
    final ok = await api.acknowledgeAlert(alertId);
    if (ok) await refreshAll();
    return ok;
  }

  Future<void> fetchScoring() async {
    liveScoring = await api.fetchLiveScoring();
    notifyListeners();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _ws.dispose();
    super.dispose();
  }
}
