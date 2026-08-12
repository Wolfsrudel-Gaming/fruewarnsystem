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

  /// Quittierte Alarme, zu denen noch eine Einsatz-Rückmeldung fehlt.
  /// Diese Rückmeldungen sind die Lernquelle des Systems.
  List<AlertData> pendingFeedback = [];

  bool loading = true;
  String? error;
  bool wsConnected = false;

  /// Wird gesetzt, wenn per WebSocket ein kritischer Alarm (Score >= 80)
  /// eintrifft. Die UI zeigt dann den Vollbild-Alarm und ruft
  /// [clearCriticalAlert] auf.
  AlertData? pendingCriticalAlert;

  /// Schlüssel ist "id:eskalationsstufe": Ein anhaltender Alarm behält seine
  /// ID und soll nicht erneut wecken — steigt aber die Eskalationsstufe, ist
  /// das eine neue Lage und der Vollbild-Alarm erscheint wieder.
  final Set<String> _seenCriticalKeys = {};

  void _maybeRaiseCritical(AlertData alert) {
    if (alert.score < 80 || alert.acknowledged) return;
    final key = '${alert.id}:${alert.escalationLevel}';
    if (_seenCriticalKeys.contains(key)) return;
    _seenCriticalKeys.add(key);
    pendingCriticalAlert = alert;
  }

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
      // Server nutzt je nach Stand "update" oder "score_update" — beide
      // akzeptieren, damit die App bei Server-Umbenennungen nicht taub wird.
      if (type == 'update' || type == 'score_update') {
        // Collector-Lauf abgeschlossen — Scores haben sich evtl. geaendert
        refreshAll();
      } else if (type == 'alert') {
        final alertJson = msg['alert'] as Map<String, dynamic>?;
        if (alertJson != null) {
          final alert = AlertData.fromJson(alertJson);
          _maybeRaiseCritical(alert);
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
        api.fetchPendingFeedback(),
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
      pendingFeedback = results[9] as List<AlertData>? ?? [];
      error = overview == null ? 'Verbindung fehlgeschlagen' : null;

      // Fallback: Kritische Alarme auch ohne WS-Event erkennen (z.B. App
      // war im Hintergrund, Poll findet neuen unquittierten Alarm >= 80).
      for (final a in alerts) {
        _maybeRaiseCritical(a);
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

  /// Rückmeldung abgeben — das System lernt daraus.
  Future<bool> submitFeedback({
    required int alertId,
    required FeedbackOutcome outcome,
    String? deploymentType,
    int? forcesCount,
    int? severityRating,
    String? notes,
  }) async {
    final ok = await api.submitFeedback(
      alertId: alertId,
      outcome: outcome,
      deploymentType: deploymentType,
      forcesCount: forcesCount,
      severityRating: severityRating,
      notes: notes,
    );
    if (ok) {
      pendingFeedback.removeWhere((a) => a.id == alertId);
      notifyListeners();
      await refreshAll();
    }
    return ok;
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _ws.dispose();
    super.dispose();
  }
}
