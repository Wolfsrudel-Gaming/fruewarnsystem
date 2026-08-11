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
  Map<String, dynamic>? thresholds;
  Map<String, dynamic>? liveScoring;

  bool loading = true;
  String? error;

  AppState({required this.api}) {
    _ws = WebSocketService(baseUrl: api.baseUrl);
    _init();
  }

  Future<void> _init() async {
    await refreshAll();
    _ws.connect();
    _ws.stream.listen((msg) {
      if (msg['type'] == 'score_update' || msg['type'] == 'alert') {
        refreshAll();
      }
    });
    _pollTimer = Timer.periodic(const Duration(seconds: 60), (_) => refreshAll());
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
      ]);

      overview = results[0] as OverviewData?;
      alerts = results[1] as List<AlertData>? ?? [];
      waterStations = results[2] as List<WaterStation>? ?? [];
      weatherWarnings = results[3] as List<WeatherWarning>? ?? [];
      fireRisks = results[4] as List<FireRiskData>? ?? [];
      trafficEvents = results[5] as List<TrafficEventData>? ?? [];
      thresholds = results[6] as Map<String, dynamic>?;
      error = null;
    } catch (e) {
      error = 'Verbindung fehlgeschlagen';
    }
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
