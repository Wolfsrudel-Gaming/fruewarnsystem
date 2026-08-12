import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/api_models.dart';

class ApiService {
  String baseUrl;

  ApiService({this.baseUrl = 'http://10.0.2.2:8000'});

  Future<Map<String, dynamic>?> _getJson(String path) async {
    try {
      final resp = await http.get(
        Uri.parse('$baseUrl$path'),
        headers: {'Accept': 'application/json'},
      ).timeout(const Duration(seconds: 15));
      if (resp.statusCode == 200) {
        return jsonDecode(resp.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return null;
  }

  Future<OverviewData?> fetchOverview() async {
    final data = await _getJson('/api/dashboard/overview');
    return data != null ? OverviewData.fromJson(data) : null;
  }

  Future<List<WaterStation>> fetchWaterStations() async {
    final data = await _getJson('/api/dashboard/water');
    if (data == null) return [];
    return (data['stations'] as List? ?? [])
        .map((s) => WaterStation.fromJson(s as Map<String, dynamic>))
        .toList();
  }

  Future<List<WeatherWarning>> fetchWeatherWarnings() async {
    final data = await _getJson('/api/dashboard/weather');
    if (data == null) return [];
    return (data['warnings'] as List? ?? [])
        .map((w) => WeatherWarning.fromJson(w as Map<String, dynamic>))
        .toList();
  }

  Future<List<FireRiskData>> fetchFireRisk() async {
    final data = await _getJson('/api/dashboard/fire');
    if (data == null) return [];
    return (data['risks'] as List? ?? [])
        .map((r) => FireRiskData.fromJson(r as Map<String, dynamic>))
        .toList();
  }

  Future<List<TrafficEventData>> fetchTraffic() async {
    final data = await _getJson('/api/dashboard/traffic');
    if (data == null) return [];
    return (data['events'] as List? ?? [])
        .map((e) => TrafficEventData.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<List<AlertData>> fetchAlerts({bool activeOnly = true}) async {
    final data = await _getJson('/api/dashboard/alerts?active_only=$activeOnly');
    if (data == null) return [];
    return (data['alerts'] as List? ?? [])
        .map((a) => AlertData.fromJson(a as Map<String, dynamic>))
        .toList();
  }

  Future<bool> acknowledgeAlert(int alertId) async {
    try {
      final resp = await http.post(
        Uri.parse('$baseUrl/api/dashboard/alerts/$alertId/acknowledge'),
      ).timeout(const Duration(seconds: 10));
      return resp.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<Map<String, dynamic>?> fetchLiveScoring() async {
    return _getJson('/api/dashboard/scoring/live');
  }

  /// Server-Format: {"history": [{"category", "score", "calculated_at"}]}
  Future<List<ScoreHistoryPoint>> fetchScoreHistory({
    String? category,
    int hours = 24,
  }) async {
    var path = '/api/dashboard/history/risk-scores?hours=$hours';
    if (category != null) path += '&category=$category';
    final data = await _getJson(path);
    if (data == null) return [];
    return (data['history'] as List? ?? [])
        .map((p) => ScoreHistoryPoint.fromJson(p as Map<String, dynamic>))
        .toList();
  }

  /// Server-Format: {"thresholds": [{id, category, name, condition, ...}]}
  Future<List<Map<String, dynamic>>> fetchThresholds() async {
    final data = await _getJson('/api/dashboard/thresholds');
    if (data == null) return [];
    return (data['thresholds'] as List? ?? [])
        .map((t) => t as Map<String, dynamic>)
        .toList();
  }

  Future<List<OfficialWarningData>> fetchOfficialWarnings() async {
    final data = await _getJson('/api/dashboard/warnings');
    if (data == null) return [];
    return (data['warnings'] as List? ?? [])
        .map((w) => OfficialWarningData.fromJson(w as Map<String, dynamic>))
        .toList();
  }

  Future<List<AirQualityReading>> fetchAirQuality() async {
    final data = await _getJson('/api/dashboard/air-quality');
    if (data == null) return [];
    return (data['readings'] as List? ?? [])
        .map((r) => AirQualityReading.fromJson(r as Map<String, dynamic>))
        .toList();
  }

  Future<List<NewsItemData>> fetchNews({int limit = 30}) async {
    final data = await _getJson('/api/dashboard/news?limit=$limit');
    if (data == null) return [];
    return (data['items'] as List? ?? [])
        .map((n) => NewsItemData.fromJson(n as Map<String, dynamic>))
        .toList();
  }

  // --- Lernschleife: Rückmeldungen und Kalibrierung ---

  /// Rückmeldung zu einem Alarm: kam es zum Einsatz?
  Future<bool> submitFeedback({
    required int alertId,
    required FeedbackOutcome outcome,
    String? deploymentType,
    int? forcesCount,
    int? severityRating,
    String? notes,
    String? reportedBy,
  }) async {
    try {
      final resp = await http.post(
        Uri.parse('$baseUrl/api/dashboard/alerts/$alertId/feedback'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'outcome': outcome.apiValue,
          if (deploymentType != null) 'deployment_type': deploymentType,
          if (forcesCount != null) 'forces_count': forcesCount,
          if (severityRating != null) 'severity_rating': severityRating,
          if (notes != null) 'notes': notes,
          if (reportedBy != null) 'reported_by': reportedBy,
        }),
      ).timeout(const Duration(seconds: 15));
      return resp.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Alarme, zu denen noch eine Rückmeldung fehlt
  Future<List<AlertData>> fetchPendingFeedback() async {
    final data = await _getJson('/api/dashboard/alerts/pending-feedback');
    if (data == null) return [];
    return (data['alerts'] as List? ?? [])
        .map((a) => AlertData.fromJson(a as Map<String, dynamic>))
        .toList();
  }

  /// Einsatz melden — auch nachträglich und ohne vorherigen Alarm
  Future<Map<String, dynamic>?> logDeployment({
    required String category,
    required String title,
    String? description,
    DateTime? occurredAt,
    int? forcesCount,
    int? severityRating,
    String? reportedBy,
  }) async {
    try {
      final resp = await http.post(
        Uri.parse('$baseUrl/api/dashboard/deployments'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'category': category,
          'title': title,
          if (description != null) 'description': description,
          if (occurredAt != null) 'occurred_at': occurredAt.toUtc().toIso8601String(),
          if (forcesCount != null) 'forces_count': forcesCount,
          if (severityRating != null) 'severity_rating': severityRating,
          if (reportedBy != null) 'reported_by': reportedBy,
        }),
      ).timeout(const Duration(seconds: 15));
      if (resp.statusCode == 200) {
        return jsonDecode(resp.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return null;
  }

  Future<List<DeploymentData>> fetchDeployments({int days = 180}) async {
    final data = await _getJson('/api/dashboard/deployments?days=$days');
    if (data == null) return [];
    return (data['deployments'] as List? ?? [])
        .map((d) => DeploymentData.fromJson(d as Map<String, dynamic>))
        .toList();
  }

  Future<bool> deleteDeployment(int id) async {
    try {
      final resp = await http
          .delete(Uri.parse('$baseUrl/api/dashboard/deployments/$id'))
          .timeout(const Duration(seconds: 10));
      return resp.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<CalibrationReport?> fetchCalibration() async {
    final data = await _getJson('/api/dashboard/calibration');
    return data != null ? CalibrationReport.fromJson(data) : null;
  }

  Future<bool> recomputeCalibration() async {
    try {
      final resp = await http
          .post(Uri.parse('$baseUrl/api/dashboard/calibration/recompute'))
          .timeout(const Duration(seconds: 60));
      return resp.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<SituationReport?> fetchReport() async {
    // Der LLM-Report kann dauern — grosszuegiger Timeout.
    try {
      final resp = await http.get(
        Uri.parse('$baseUrl/api/dashboard/report'),
        headers: {'Accept': 'application/json'},
      ).timeout(const Duration(seconds: 90));
      if (resp.statusCode == 200) {
        return SituationReport.fromJson(
            jsonDecode(resp.body) as Map<String, dynamic>);
      }
    } catch (_) {}
    return null;
  }
}
