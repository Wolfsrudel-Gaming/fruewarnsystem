class OverviewData {
  final double overallScore;
  final Map<String, CategoryScore> riskScores;
  final List<AlertData> activeAlerts;
  final String lastUpdated;

  OverviewData({
    required this.overallScore,
    required this.riskScores,
    required this.activeAlerts,
    required this.lastUpdated,
  });

  factory OverviewData.fromJson(Map<String, dynamic> json) {
    final scores = <String, CategoryScore>{};
    final raw = json['risk_scores'] as Map<String, dynamic>? ?? {};
    for (final e in raw.entries) {
      scores[e.key] = CategoryScore.fromJson(e.value as Map<String, dynamic>);
    }
    final alerts = (json['active_alerts'] as List? ?? [])
        .map((a) => AlertData.fromJson(a as Map<String, dynamic>))
        .toList();
    return OverviewData(
      overallScore: (json['overall_score'] as num?)?.toDouble() ?? 0,
      riskScores: scores,
      activeAlerts: alerts,
      lastUpdated: json['last_updated'] as String? ?? '',
    );
  }
}

class CategoryScore {
  final double score;
  final Map<String, dynamic>? components;
  final String? calculatedAt;

  CategoryScore({required this.score, this.components, this.calculatedAt});

  factory CategoryScore.fromJson(Map<String, dynamic> json) {
    return CategoryScore(
      score: (json['score'] as num?)?.toDouble() ?? 0,
      components: json['components'] as Map<String, dynamic>?,
      calculatedAt: json['calculated_at'] as String?,
    );
  }
}

class AlertData {
  final int id;
  final String category;
  final double score;
  final String title;
  final String description;
  final int escalationLevel;
  final bool acknowledged;
  final String? triggeredAt;

  AlertData({
    required this.id,
    required this.category,
    required this.score,
    required this.title,
    required this.description,
    required this.escalationLevel,
    required this.acknowledged,
    this.triggeredAt,
  });

  factory AlertData.fromJson(Map<String, dynamic> json) {
    return AlertData(
      id: json['id'] as int? ?? 0,
      category: json['category'] as String? ?? '',
      score: (json['score'] as num?)?.toDouble() ?? 0,
      title: json['title'] as String? ?? '',
      description: json['description'] as String? ?? '',
      escalationLevel: json['escalation_level'] as int? ?? 0,
      acknowledged: json['acknowledged'] as bool? ?? false,
      triggeredAt: json['triggered_at'] as String?,
    );
  }
}

class WaterStation {
  final String stationId;
  final String stationName;
  final String river;
  final double? currentLevel;
  final String trend;
  final String warningLevel;
  final String condition;
  final String? lastUpdate;

  WaterStation({
    required this.stationId,
    required this.stationName,
    required this.river,
    this.currentLevel,
    required this.trend,
    required this.warningLevel,
    required this.condition,
    this.lastUpdate,
  });

  factory WaterStation.fromJson(Map<String, dynamic> json) {
    return WaterStation(
      stationId: json['station_id'] as String? ?? '',
      stationName: json['station_name'] as String? ?? '',
      river: json['river'] as String? ?? '',
      currentLevel: (json['current_level'] as num?)?.toDouble(),
      trend: json['trend'] as String? ?? 'unknown',
      warningLevel: json['warning_level'] as String? ?? 'unknown',
      condition: json['condition'] as String? ?? 'unknown',
      lastUpdate: json['last_update'] as String?,
    );
  }
}

class WeatherWarning {
  final String type;
  final String? region;
  final int severity;
  final String title;
  final String description;
  final String? validFrom;
  final String? validTo;
  final String? source;

  WeatherWarning({
    required this.type,
    this.region,
    required this.severity,
    required this.title,
    required this.description,
    this.validFrom,
    this.validTo,
    this.source,
  });

  factory WeatherWarning.fromJson(Map<String, dynamic> json) {
    return WeatherWarning(
      type: json['type'] as String? ?? '',
      region: json['region'] as String?,
      severity: json['severity'] as int? ?? 0,
      title: json['title'] as String? ?? '',
      description: json['description'] as String? ?? '',
      validFrom: json['valid_from'] as String?,
      validTo: json['valid_to'] as String?,
      source: json['source'] as String?,
    );
  }
}

class FireRiskData {
  final String region;
  final double riskIndex;
  final double? temperature;
  final double? humidity;
  final double? windSpeed;
  final String? windDirection;
  final double? rainLast24h;
  final int? satelliteHotspots;

  FireRiskData({
    required this.region,
    required this.riskIndex,
    this.temperature,
    this.humidity,
    this.windSpeed,
    this.windDirection,
    this.rainLast24h,
    this.satelliteHotspots,
  });

  factory FireRiskData.fromJson(Map<String, dynamic> json) {
    return FireRiskData(
      region: json['region'] as String? ?? '',
      riskIndex: (json['risk_index'] as num?)?.toDouble() ?? 0,
      temperature: (json['temperature'] as num?)?.toDouble(),
      humidity: (json['humidity'] as num?)?.toDouble(),
      windSpeed: (json['wind_speed'] as num?)?.toDouble(),
      windDirection: json['wind_direction'] as String?,
      rainLast24h: (json['rain_last_24h'] as num?)?.toDouble(),
      satelliteHotspots: json['satellite_hotspots'] as int?,
    );
  }
}

class TrafficEventData {
  final String road;
  final String eventType;
  final String title;
  final String description;
  final int severity;
  final String source;

  TrafficEventData({
    required this.road,
    required this.eventType,
    required this.title,
    required this.description,
    required this.severity,
    required this.source,
  });

  factory TrafficEventData.fromJson(Map<String, dynamic> json) {
    return TrafficEventData(
      road: json['road'] as String? ?? '',
      eventType: json['event_type'] as String? ?? '',
      title: json['title'] as String? ?? '',
      description: json['description'] as String? ?? '',
      severity: json['severity'] as int? ?? 0,
      source: json['source'] as String? ?? '',
    );
  }
}
