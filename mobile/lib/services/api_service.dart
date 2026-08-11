import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/api_models.dart';

class ApiService {
  String _baseUrl;

  ApiService({String baseUrl = 'http://10.0.2.2:8000'}) : _baseUrl = baseUrl;

  String get baseUrl => _baseUrl;
  set baseUrl(String url) => _baseUrl = url;

  Future<Map<String, dynamic>?> _getJson(String path) async {
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl$path'),
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
        Uri.parse('$_baseUrl/api/dashboard/alerts/$alertId/acknowledge'),
      ).timeout(const Duration(seconds: 10));
      return resp.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<Map<String, dynamic>?> fetchLiveScoring() async {
    return _getJson('/api/dashboard/scoring/live');
  }

  Future<Map<String, dynamic>?> fetchScoreHistory({
    String? category,
    int hours = 24,
  }) async {
    var path = '/api/dashboard/history/risk-scores?hours=$hours';
    if (category != null) path += '&category=$category';
    return _getJson(path);
  }

  Future<Map<String, dynamic>?> fetchThresholds() async {
    return _getJson('/api/dashboard/thresholds');
  }
}
