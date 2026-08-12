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
  final double? lat;
  final double? lon;
  final String? lastUpdate;
  final List<WaterHistoryPoint> history;

  WaterStation({
    required this.stationId,
    required this.stationName,
    required this.river,
    this.currentLevel,
    required this.trend,
    required this.warningLevel,
    required this.condition,
    this.lat,
    this.lon,
    this.lastUpdate,
    this.history = const [],
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
      lat: (json['lat'] as num?)?.toDouble(),
      lon: (json['lon'] as num?)?.toDouble(),
      lastUpdate: json['last_update'] as String?,
      history: (json['history'] as List? ?? [])
          .map((h) => WaterHistoryPoint.fromJson(h as Map<String, dynamic>))
          .toList(),
    );
  }
}

class WaterHistoryPoint {
  final double? levelCm;
  final String? timestamp;

  WaterHistoryPoint({this.levelCm, this.timestamp});

  factory WaterHistoryPoint.fromJson(Map<String, dynamic> json) {
    return WaterHistoryPoint(
      levelCm: (json['level_cm'] as num?)?.toDouble(),
      timestamp: json['timestamp'] as String?,
    );
  }
}

class ScoreHistoryPoint {
  final String category;
  final double score;
  final DateTime? calculatedAt;

  ScoreHistoryPoint({required this.category, required this.score, this.calculatedAt});

  factory ScoreHistoryPoint.fromJson(Map<String, dynamic> json) {
    DateTime? ts;
    final raw = json['calculated_at'] as String?;
    if (raw != null) ts = DateTime.tryParse(raw);
    return ScoreHistoryPoint(
      category: json['category'] as String? ?? '',
      score: (json['score'] as num?)?.toDouble() ?? 0,
      calculatedAt: ts,
    );
  }
}

class OfficialWarningData {
  final int id;
  final String? sourceSystem;
  final String? severity;
  final String? category;
  final String headline;
  final String? description;
  final String? instruction;
  final String? areaDescription;
  final String? effective;
  final String? expires;

  OfficialWarningData({
    required this.id,
    this.sourceSystem,
    this.severity,
    this.category,
    required this.headline,
    this.description,
    this.instruction,
    this.areaDescription,
    this.effective,
    this.expires,
  });

  factory OfficialWarningData.fromJson(Map<String, dynamic> json) {
    return OfficialWarningData(
      id: json['id'] as int? ?? 0,
      sourceSystem: json['source_system'] as String?,
      severity: json['severity'] as String?,
      category: json['category'] as String?,
      headline: json['headline'] as String? ?? '',
      description: json['description'] as String?,
      instruction: json['instruction'] as String?,
      areaDescription: json['area_description'] as String?,
      effective: json['effective'] as String?,
      expires: json['expires'] as String?,
    );
  }
}

class AirQualityReading {
  final String? stationName;
  final double? pm25;
  final double? pm10;
  final double? ozone;
  final double? no2;
  final double? aqi;
  final String? timestamp;

  AirQualityReading({
    this.stationName,
    this.pm25,
    this.pm10,
    this.ozone,
    this.no2,
    this.aqi,
    this.timestamp,
  });

  factory AirQualityReading.fromJson(Map<String, dynamic> json) {
    return AirQualityReading(
      stationName: json['station_name'] as String?,
      pm25: (json['pm25'] as num?)?.toDouble(),
      pm10: (json['pm10'] as num?)?.toDouble(),
      ozone: (json['ozone'] as num?)?.toDouble(),
      no2: (json['no2'] as num?)?.toDouble(),
      aqi: (json['aqi'] as num?)?.toDouble(),
      timestamp: json['timestamp'] as String?,
    );
  }
}

class NewsItemData {
  final int id;
  final String title;
  final String? summary;
  final String? url;
  final String? source;
  final String? category;
  final double? relevanceScore;
  final String? publishedAt;

  NewsItemData({
    required this.id,
    required this.title,
    this.summary,
    this.url,
    this.source,
    this.category,
    this.relevanceScore,
    this.publishedAt,
  });

  factory NewsItemData.fromJson(Map<String, dynamic> json) {
    return NewsItemData(
      id: json['id'] as int? ?? 0,
      title: json['title'] as String? ?? '',
      summary: json['summary'] as String?,
      url: json['url'] as String?,
      source: json['source'] as String?,
      category: json['category'] as String?,
      relevanceScore: (json['relevance_score'] as num?)?.toDouble(),
      publishedAt: json['published_at'] as String?,
    );
  }
}

class SituationReport {
  final String report;
  final String generatedAt;
  final bool llmGenerated;

  SituationReport({
    required this.report,
    required this.generatedAt,
    required this.llmGenerated,
  });

  factory SituationReport.fromJson(Map<String, dynamic> json) {
    return SituationReport(
      report: json['report'] as String? ?? '',
      generatedAt: json['generated_at'] as String? ?? '',
      llmGenerated: json['llm_generated'] as bool? ?? false,
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
  final double? lat;
  final double? lon;

  TrafficEventData({
    required this.road,
    required this.eventType,
    required this.title,
    required this.description,
    required this.severity,
    required this.source,
    this.lat,
    this.lon,
  });

  factory TrafficEventData.fromJson(Map<String, dynamic> json) {
    return TrafficEventData(
      road: json['road'] as String? ?? '',
      eventType: json['event_type'] as String? ?? '',
      title: json['title'] as String? ?? '',
      description: json['description'] as String? ?? '',
      severity: (json['severity'] as num?)?.toInt() ?? 0,
      source: json['source'] as String? ?? '',
      lat: (json['lat'] as num?)?.toDouble(),
      lon: (json['lon'] as num?)?.toDouble(),
    );
  }
}

/// Ergebnis einer Alarm-Rückmeldung — muss zum Backend-Enum passen.
enum FeedbackOutcome {
  einsatz('einsatz', 'Einsatz erfolgt', 'Der Alarm war berechtigt'),
  vorsorge('vorsorge', 'Vorsorge berechtigt', 'Kein Einsatz, aber Warnung war richtig'),
  keinEinsatz('kein_einsatz', 'Fehlalarm', 'Es passierte nichts'),
  unklar('unklar', 'Unklar', 'Nicht bewertbar');

  final String apiValue;
  final String label;
  final String description;
  const FeedbackOutcome(this.apiValue, this.label, this.description);
}

class DeploymentData {
  final int id;
  final String category;
  final String categoryLabel;
  final String title;
  final String? description;
  final String? occurredAt;
  final int? forcesCount;
  final int? severityRating;
  final bool wasPredicted;
  final int? matchedAlertId;

  DeploymentData({
    required this.id,
    required this.category,
    required this.categoryLabel,
    required this.title,
    this.description,
    this.occurredAt,
    this.forcesCount,
    this.severityRating,
    required this.wasPredicted,
    this.matchedAlertId,
  });

  factory DeploymentData.fromJson(Map<String, dynamic> json) {
    return DeploymentData(
      id: json['id'] as int? ?? 0,
      category: json['category'] as String? ?? '',
      categoryLabel: json['category_label'] as String? ?? '',
      title: json['title'] as String? ?? '',
      description: json['description'] as String?,
      occurredAt: json['occurred_at'] as String?,
      forcesCount: json['forces_count'] as int?,
      severityRating: json['severity_rating'] as int?,
      wasPredicted: json['was_predicted'] as bool? ?? false,
      matchedAlertId: json['matched_alert_id'] as int?,
    );
  }
}

/// Lernstatus einer einzelnen Kategorie
class CategoryCalibration {
  final String category;
  final String categoryLabel;
  final double weightMultiplier;
  final double thresholdOffset;
  final double? precision;
  final double? recall;
  final int truePositives;
  final int partialPositives;
  final int falsePositives;
  final int falseNegatives;
  final int sampleCount;
  final bool isLocked;
  final String? reason;

  CategoryCalibration({
    required this.category,
    required this.categoryLabel,
    required this.weightMultiplier,
    required this.thresholdOffset,
    this.precision,
    this.recall,
    required this.truePositives,
    required this.partialPositives,
    required this.falsePositives,
    required this.falseNegatives,
    required this.sampleCount,
    required this.isLocked,
    this.reason,
  });

  factory CategoryCalibration.fromJson(Map<String, dynamic> json) {
    return CategoryCalibration(
      category: json['category'] as String? ?? '',
      categoryLabel: json['category_label'] as String? ?? '',
      weightMultiplier: (json['weight_multiplier'] as num?)?.toDouble() ?? 1.0,
      thresholdOffset: (json['threshold_offset'] as num?)?.toDouble() ?? 0.0,
      precision: (json['precision'] as num?)?.toDouble(),
      recall: (json['recall'] as num?)?.toDouble(),
      truePositives: json['true_positives'] as int? ?? 0,
      partialPositives: json['partial_positives'] as int? ?? 0,
      falsePositives: json['false_positives'] as int? ?? 0,
      falseNegatives: json['false_negatives'] as int? ?? 0,
      sampleCount: json['sample_count'] as int? ?? 0,
      isLocked: json['is_locked'] as bool? ?? false,
      reason: json['reason'] as String?,
    );
  }
}

/// Gesamtbild der Systemgüte
class CalibrationReport {
  final double? precision;
  final double? recall;
  final int truePositives;
  final int falsePositives;
  final int falseNegatives;
  final int sampleCount;
  final String maturity;
  final List<CategoryCalibration> categories;
  final double targetPrecision;
  final double targetRecall;

  CalibrationReport({
    this.precision,
    this.recall,
    required this.truePositives,
    required this.falsePositives,
    required this.falseNegatives,
    required this.sampleCount,
    required this.maturity,
    required this.categories,
    required this.targetPrecision,
    required this.targetRecall,
  });

  factory CalibrationReport.fromJson(Map<String, dynamic> json) {
    final overall = json['overall'] as Map<String, dynamic>? ?? {};
    return CalibrationReport(
      precision: (overall['precision'] as num?)?.toDouble(),
      recall: (overall['recall'] as num?)?.toDouble(),
      truePositives: overall['true_positives'] as int? ?? 0,
      falsePositives: overall['false_positives'] as int? ?? 0,
      falseNegatives: overall['false_negatives'] as int? ?? 0,
      sampleCount: overall['sample_count'] as int? ?? 0,
      maturity: overall['maturity'] as String? ?? '',
      categories: (json['categories'] as List? ?? [])
          .map((c) => CategoryCalibration.fromJson(c as Map<String, dynamic>))
          .toList(),
      targetPrecision: (json['target_precision'] as num?)?.toDouble() ?? 0.6,
      targetRecall: (json['target_recall'] as num?)?.toDouble() ?? 0.85,
    );
  }
}
