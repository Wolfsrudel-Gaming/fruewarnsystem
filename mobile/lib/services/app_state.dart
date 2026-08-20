import 'dart:async';
import 'package:flutter/material.dart';
import '../models/api_models.dart';
import 'api_service.dart';
import 'websocket_service.dart';
import 'alarm_policy.dart';
import 'notification_service.dart';

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

  /// Was die aktuelle Lage für die Bereitschaft Troisdorf bedeutet
  DeploymentAssessment? assessment;

  /// Zuletzt gemeldete Stufe — Grundlage für die Erkennung von Wechseln.
  /// Ohne diesen Merker würde bei jedem Abruf erneut alarmiert.
  String? _gemeldeteStufe;

  /// Ruhezeiten des Nutzers
  RuhezeitEinstellung ruhezeit = const RuhezeitEinstellung();

  /// Fortlaufende ID für Stufenwechsel-Meldungen, damit sich aufeinander
  /// folgende Meldungen nicht gegenseitig überschreiben.
  int _meldungsId = 9000;

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
    ruhezeit = await RuhezeitEinstellung.laden();
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

  /// Meldet, wenn sich die Einsatzerwartung verändert hat.
  ///
  /// Der eigentliche Alarmfall der App: Nicht ein einzelner Messwert weckt,
  /// sondern die Frage, ob für die Bereitschaft etwas daraus folgt.
  Future<void> _meldeStufenwechsel(DeploymentAssessment neu) async {
    final alt = _gemeldeteStufe;
    if (alt == neu.level) return;

    final staerke = bewerteStufenwechsel(
      alteStufe: alt,
      neueStufe: neu.level,
      jetzt: DateTime.now(),
      ruhezeit: ruhezeit,
    );
    _gemeldeteStufe = neu.level;

    // Beim ersten Abruf nach dem Start gibt es keinen Vorzustand. Dann nur
    // wecken, wenn die Lage wirklich ernst ist — sonst schreit die App bei
    // jedem Neustart los.
    if (alt == null && staerke != AlarmStaerke.weckruf) return;

    final anlass = neu.reasons.isNotEmpty ? neu.reasons.first : null;
    final text = stufenwechselText(
      alteStufe: alt,
      neueStufe: neu.level,
      neuesLabel: neu.label,
      anlass: anlass,
    );

    _meldungsId++;
    if (stufenRang(neu.level) < stufenRang(alt)) {
      await NotificationService.showEntwarnung(
        id: _meldungsId, title: text.titel, body: text.text);
    } else {
      await NotificationService.showStufenwechsel(
        id: _meldungsId, title: text.titel, body: text.text, staerke: staerke);
    }

    // Vollbild-Weckruf in der App selbst, wenn sie gerade offen ist
    if (staerke == AlarmStaerke.weckruf) {
      pendingAssessmentAlarm = neu;
    }
  }

  /// Einsatzerwartung, die einen Vollbild-Alarm ausgelöst hat
  DeploymentAssessment? pendingAssessmentAlarm;

  void clearAssessmentAlarm() {
    pendingAssessmentAlarm = null;
    notifyListeners();
  }

  /// Ruhezeiten ändern und sofort anwenden
  Future<void> setRuhezeit(RuhezeitEinstellung neu) async {
    ruhezeit = neu;
    await neu.speichern();
    notifyListeners();
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
        api.fetchAssessment(),
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
      // Fällt der Abruf aus, lieber den letzten Stand behalten als die
      // Einsatzerwartung verschwinden zu lassen.
      final neu = results[10] as DeploymentAssessment?;
      if (neu != null) {
        assessment = neu;
        await _meldeStufenwechsel(neu);
      }
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
