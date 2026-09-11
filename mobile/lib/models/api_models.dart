import 'package:flutter/material.dart' show IconData, Icons;

class OverviewData {
  final double overallScore;
  final Map<String, CategoryScore> riskScores;
  final List<AlertData> activeAlerts;
  final String lastUpdated;

  /// Kategorie, die die Gesamtlage bestimmt (höchstes gewichtetes Risiko)
  final String? driverLabel;

  /// Weitere gleichzeitig erhöhte Kategorien, die die Lage verschärfen
  final List<String> concurrentLabels;

  OverviewData({
    required this.overallScore,
    required this.riskScores,
    required this.activeAlerts,
    required this.lastUpdated,
    this.driverLabel,
    this.concurrentLabels = const [],
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
      driverLabel: json['overall_driver_label'] as String?,
      concurrentLabels: (json['overall_concurrent'] as List? ?? [])
          .map((c) => c.toString())
          .toList(),
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

  /// Alter des Berichts in Minuten — er wird im Hintergrund erzeugt,
  /// nicht bei jedem Abruf neu.
  final double ageMinutes;

  /// Im Hintergrund läuft gerade eine Neuberechnung
  final bool refreshing;

  final String? model;

  SituationReport({
    required this.report,
    required this.generatedAt,
    required this.llmGenerated,
    this.ageMinutes = 0,
    this.refreshing = false,
    this.model,
  });

  factory SituationReport.fromJson(Map<String, dynamic> json) {
    return SituationReport(
      report: json['report'] as String? ?? '',
      generatedAt: json['generated_at'] as String? ?? '',
      llmGenerated: json['llm_generated'] as bool? ?? false,
      ageMinutes: (json['age_minutes'] as num?)?.toDouble() ?? 0,
      refreshing: json['refreshing'] as bool? ?? false,
      model: json['model'] as String?,
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

/// Stromnetz-Detaildaten einer Regelzone (SMARD/Bundesnetzagentur)
class PowerRegionData {
  final String region;
  final String regionLabel;
  final double? generationMw;
  final double? consumptionMw;
  final double? balanceMw;
  final double? renewableShare;
  final double? priceEurMwh;
  final double? forecastTotalMw;
  final bool isStressed;
  final String? stressIndicator;
  final String? timestamp;
  final Map<String, double> generationParts;
  final Map<String, double> renewableParts;

  PowerRegionData({
    required this.region,
    required this.regionLabel,
    this.generationMw,
    this.consumptionMw,
    this.balanceMw,
    this.renewableShare,
    this.priceEurMwh,
    this.forecastTotalMw,
    required this.isStressed,
    this.stressIndicator,
    this.timestamp,
    this.generationParts = const {},
    this.renewableParts = const {},
  });

  static Map<String, double> _parts(dynamic raw) {
    if (raw is! Map) return {};
    final out = <String, double>{};
    raw.forEach((k, v) {
      final d = (v as num?)?.toDouble();
      if (d != null) out[k.toString()] = d;
    });
    return out;
  }

  factory PowerRegionData.fromJson(Map<String, dynamic> json) {
    return PowerRegionData(
      region: json['region'] as String? ?? '',
      regionLabel: json['region_label'] as String? ?? '',
      generationMw: (json['generation_mw'] as num?)?.toDouble(),
      consumptionMw: (json['consumption_mw'] as num?)?.toDouble(),
      balanceMw: (json['balance_mw'] as num?)?.toDouble(),
      renewableShare: (json['renewable_share'] as num?)?.toDouble(),
      priceEurMwh: (json['price_eur_mwh'] as num?)?.toDouble(),
      forecastTotalMw: (json['forecast_total_mw'] as num?)?.toDouble(),
      isStressed: json['is_stressed'] as bool? ?? false,
      stressIndicator: json['stress_indicator'] as String?,
      timestamp: json['timestamp'] as String?,
      generationParts: _parts(json['generation_parts']),
      renewableParts: _parts(json['renewable_parts']),
    );
  }

  /// Erzeugungsarten absteigend nach Leistung, nur mit Wert > 0
  List<MapEntry<String, double>> get sortedParts {
    final list = generationParts.entries.where((e) => e.value > 0).toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    return list;
  }

  bool isRenewable(String name) => renewableParts.containsKey(name);
}

class PowerHistoryPoint {
  final String region;
  final DateTime? timestamp;
  final double? consumptionMw;
  final double? generationMw;
  final double? priceEurMwh;

  PowerHistoryPoint({
    required this.region,
    this.timestamp,
    this.consumptionMw,
    this.generationMw,
    this.priceEurMwh,
  });

  factory PowerHistoryPoint.fromJson(Map<String, dynamic> json) {
    return PowerHistoryPoint(
      region: json['region'] as String? ?? '',
      timestamp: DateTime.tryParse(json['timestamp'] as String? ?? ''),
      consumptionMw: (json['consumption_mw'] as num?)?.toDouble(),
      generationMw: (json['generation_mw'] as num?)?.toDouble(),
      priceEurMwh: (json['price_eur_mwh'] as num?)?.toDouble(),
    );
  }
}

class PowerDetail {
  final List<PowerRegionData> regions;
  final List<PowerHistoryPoint> history;
  final String? source;

  PowerDetail({required this.regions, required this.history, this.source});

  factory PowerDetail.fromJson(Map<String, dynamic> json) {
    return PowerDetail(
      regions: (json['regions'] as List? ?? [])
          .map((r) => PowerRegionData.fromJson(r as Map<String, dynamic>))
          .toList(),
      history: (json['history'] as List? ?? [])
          .map((h) => PowerHistoryPoint.fromJson(h as Map<String, dynamic>))
          .toList(),
      source: json['source'] as String?,
    );
  }
}

/// Konkreter Stromausfall aus der Störungsauskunft der Netzbetreiber
class PowerOutageData {
  final int id;
  /// "confirmed" = vom Netzbetreiber bestätigt, "reported" = Bürgermeldungen
  final String kind;
  final String? operatorName;
  final String? postalCode;
  final String? city;
  final String? street;
  final double? lat;
  final double? lon;
  final double? distanceKm;
  final int reportCount;
  final String? startedAt;
  final String? expectedEnd;
  final String? info;

  PowerOutageData({
    required this.id,
    required this.kind,
    this.operatorName,
    this.postalCode,
    this.city,
    this.street,
    this.lat,
    this.lon,
    this.distanceKm,
    this.reportCount = 1,
    this.startedAt,
    this.expectedEnd,
    this.info,
  });

  bool get isConfirmed => kind == 'confirmed';

  factory PowerOutageData.fromJson(Map<String, dynamic> json) {
    return PowerOutageData(
      id: json['id'] as int? ?? 0,
      kind: json['kind'] as String? ?? 'confirmed',
      operatorName: json['operator_name'] as String?,
      postalCode: json['postal_code'] as String?,
      city: json['city'] as String?,
      street: json['street'] as String?,
      lat: (json['lat'] as num?)?.toDouble(),
      lon: (json['lon'] as num?)?.toDouble(),
      distanceKm: (json['distance_km'] as num?)?.toDouble(),
      reportCount: json['report_count'] as int? ?? 1,
      startedAt: json['started_at'] as String?,
      expectedEnd: json['expected_end'] as String?,
      info: json['info'] as String?,
    );
  }
}

/// Drei Relevanzzonen: In Troisdorf zählt jeder Ausfall, im Rhein-Sieg-Kreis
/// nur Großlagen, außerhalb nur Extremlagen.
class PowerOutageReport {
  /// Troisdorf: vom Netzbetreiber bestätigt
  final List<PowerOutageData> confirmed;

  /// Troisdorf: gebündelte Bürgermeldungen, noch unbestätigt
  final List<PowerOutageData> reported;

  /// Rhein-Sieg-Kreis: flächiger Ausfall ab 100 Meldungen
  final List<PowerOutageData> grosslagen;

  /// Außerhalb des Kreises: Extremlage ab 500 Meldungen
  final List<PowerOutageData> extremlagen;

  final double? nearestKm;

  PowerOutageReport({
    required this.confirmed,
    required this.reported,
    this.grosslagen = const [],
    this.extremlagen = const [],
    this.nearestKm,
  });

  /// Ausfälle in Troisdorf selbst — die unmittelbar einsatzrelevanten
  List<PowerOutageData> get local => [...confirmed, ...reported];
  bool get hasLocal => local.isNotEmpty;
  bool get isEmpty => local.isEmpty && grosslagen.isEmpty && extremlagen.isEmpty;
  List<PowerOutageData> get all => [...local, ...grosslagen, ...extremlagen];

  factory PowerOutageReport.fromJson(Map<String, dynamic> json) {
    List<PowerOutageData> parse(String key) => (json[key] as List? ?? [])
        .map((o) => PowerOutageData.fromJson(o as Map<String, dynamic>))
        .toList();
    return PowerOutageReport(
      confirmed: parse('confirmed'),
      reported: parse('reported'),
      grosslagen: parse('grosslagen'),
      extremlagen: parse('extremlagen'),
      nearestKm: (json['nearest_km'] as num?)?.toDouble(),
    );
  }
}

/// Einsatzerwartung für die Bereitschaft Troisdorf.
///
/// Bewusst getrennt vom Gesamtrisiko: Das Gesamtrisiko beschreibt die Lage,
/// die Einsatzerwartung ihre Folgen für die eigene Einheit. Ein Großbrand im
/// Nachbarkreis kann ein hohes Gesamtrisiko und trotzdem eine niedrige
/// Einsatzerwartung ergeben — Troisdorf wird dafür nicht gezogen.
class DeploymentAssessment {
  /// ruhe | beobachtung | bereitstellung_moeglich |
  /// bereitstellung_wahrscheinlich | einsatz_wahrscheinlich
  final String level;
  final String label;
  final String description;
  final double value;
  final String? driver;
  final String? driverLabel;
  final double driverScore;

  /// Gleichzeitig erhöhte Kategorien, die die Lage verschärfen
  final List<String> contributing;

  /// Voraussichtlich gebrauchte DRK-Komponenten
  final List<String> components;

  /// Nachvollziehbare Begründung, Satz für Satz
  final List<String> reasons;

  /// Belegstellen aus der Wissensdatenbank
  final List<KnowledgeSummary> knowledge;

  /// Erkannter Hinweis auf eine Evakuierung. Im Kerngebiet (Troisdorf,
  /// Siegburg) ist der Einsatz erfahrungsgemäß so gut wie sicher, in der
  /// direkten Nachbarschaft eine Stufe darunter.
  final String? evacuationOrt;

  /// 'kerngebiet' oder 'nachbarschaft'
  final String? evacuationZone;

  /// Erkannte Konstellationen: Kampfmittel, Verpflegungsbedarf, Kombilage
  final List<LageSignal> signals;

  /// Ist das System gerade hochgefahren? Während einer Großlage in der Nähe
  /// fragt es häufiger ab und gewichtet schärfer.
  final bool vigilanceRaised;
  final String? vigilanceGrund;

  DeploymentAssessment({
    required this.level,
    required this.label,
    required this.description,
    required this.value,
    this.driver,
    this.driverLabel,
    this.driverScore = 0,
    this.contributing = const [],
    this.components = const [],
    this.reasons = const [],
    this.knowledge = const [],
    this.evacuationOrt,
    this.evacuationZone,
    this.signals = const [],
    this.vigilanceRaised = false,
    this.vigilanceGrund,
  });

  bool get hasEvacuation => evacuationOrt != null;
  bool get isCoreEvacuation => evacuationZone == 'kerngebiet';

  /// Ab hier ist Handeln angezeigt, nicht nur Zurkenntnisnahme
  bool get isActionable =>
      level == 'einsatz_wahrscheinlich' ||
      level == 'bereitstellung_wahrscheinlich';

  factory DeploymentAssessment.fromJson(Map<String, dynamic> json) {
    return DeploymentAssessment(
      level: json['level'] as String? ?? 'ruhe',
      label: json['label'] as String? ?? 'Unbekannt',
      description: json['description'] as String? ?? '',
      value: (json['value'] as num?)?.toDouble() ?? 0,
      driver: json['driver'] as String?,
      driverLabel: json['driver_label'] as String?,
      driverScore: (json['driver_score'] as num?)?.toDouble() ?? 0,
      contributing: (json['contributing'] as List? ?? []).cast<String>(),
      components: (json['components'] as List? ?? []).cast<String>(),
      reasons: (json['reasons'] as List? ?? []).cast<String>(),
      knowledge: (json['knowledge'] as List? ?? [])
          .map((k) => KnowledgeSummary.fromJson(k as Map<String, dynamic>))
          .toList(),
      evacuationOrt:
          (json['evacuation'] as Map<String, dynamic>?)?['ort'] as String?,
      evacuationZone:
          (json['evacuation'] as Map<String, dynamic>?)?['zone'] as String?,
      signals: (json['signals'] as List? ?? [])
          .map((s) => LageSignal.fromJson(s as Map<String, dynamic>))
          .toList(),
      vigilanceRaised:
          (json['vigilance'] as Map<String, dynamic>?)?['stufe'] == 'erhoeht',
      vigilanceGrund:
          (json['vigilance'] as Map<String, dynamic>?)?['grund'] as String?,
    );
  }
}

/// Ein Eintrag der DRK-Wissensdatenbank.
class KnowledgeEntryData {
  final int id;
  final String kind;
  final String scope;
  final String title;
  final String body;
  final List<String> categories;
  final List<String> tags;
  final Map<String, dynamic>? facts;
  final String? source;
  final String? sourceUrl;
  final String? sourceDate;

  /// Aus öffentlicher, belegter Quelle recherchiert
  final bool isOfficial;

  /// Teil des mitgelieferten Grundbestands (nicht löschbar)
  final bool isSeed;
  final String? createdBy;

  KnowledgeEntryData({
    required this.id,
    required this.kind,
    required this.scope,
    required this.title,
    required this.body,
    this.categories = const [],
    this.tags = const [],
    this.facts,
    this.source,
    this.sourceUrl,
    this.sourceDate,
    this.isOfficial = false,
    this.isSeed = false,
    this.createdBy,
  });

  factory KnowledgeEntryData.fromJson(Map<String, dynamic> json) {
    return KnowledgeEntryData(
      id: json['id'] as int? ?? 0,
      kind: json['kind'] as String? ?? 'doktrin',
      scope: json['scope'] as String? ?? 'rhein_sieg',
      title: json['title'] as String? ?? '',
      body: json['body'] as String? ?? '',
      categories: (json['categories'] as List? ?? []).cast<String>(),
      tags: (json['tags'] as List? ?? []).cast<String>(),
      facts: json['facts'] as Map<String, dynamic>?,
      source: json['source'] as String?,
      sourceUrl: json['source_url'] as String?,
      sourceDate: json['source_date'] as String?,
      isOfficial: json['is_official'] as bool? ?? false,
      isSeed: json['is_seed'] as bool? ?? false,
      createdBy: json['created_by'] as String?,
    );
  }
}

/// Kurzform ohne Fließtext — für Belegstellen unter der Einsatzerwartung.
class KnowledgeSummary {
  final int id;
  final String title;
  final String kind;
  final String? source;
  final bool isOfficial;

  KnowledgeSummary({
    required this.id,
    required this.title,
    required this.kind,
    this.source,
    this.isOfficial = false,
  });

  factory KnowledgeSummary.fromJson(Map<String, dynamic> json) {
    return KnowledgeSummary(
      id: json['id'] as int? ?? 0,
      title: json['title'] as String? ?? '',
      kind: json['kind'] as String? ?? '',
      source: json['source'] as String?,
      isOfficial: json['is_official'] as bool? ?? false,
    );
  }
}

/// Anzeigenamen der Wissensarten
const Map<String, String> kKnowledgeKindLabels = {
  'doktrin': 'Grundlage',
  'organisation': 'Einheiten',
  'gefahrenobjekt': 'Gefahrenschwerpunkt',
  'eskalationsstufe': 'Stufen',
  'ausloeser': 'Auslöser',
  'ressource': 'Material',
  'erfahrung': 'Erfahrung',
};

const Map<String, String> kKnowledgeScopeLabels = {
  'troisdorf': 'Troisdorf',
  'rhein_sieg': 'Rhein-Sieg-Kreis',
  'nrw': 'NRW',
  'bund': 'Bund',
};


/// Eine erkannte Konstellation, die erfahrungsgemäß zum Einsatz führt.
///
/// Anders als ein Messwert beschreibt ein Signal einen Zusammenhang:
/// Bombenfund im Kerngebiet, lange Lage mit vielen Kräften, Veranstaltung
/// bei Unwetter. Der Hinweis ist bereits fertig formuliert und kann direkt
/// angezeigt werden.
class LageSignal {
  /// 'kampfmittel' | 'verpflegungsbedarf' | 'kombilage'
  final String kind;
  final String hinweis;
  final String? ort;
  final String? zone;

  /// Nur bei Verpflegungsbedarf gesetzt
  final int? kraefte;
  final int? stunden;

  LageSignal({
    required this.kind,
    required this.hinweis,
    this.ort,
    this.zone,
    this.kraefte,
    this.stunden,
  });

  factory LageSignal.fromJson(Map<String, dynamic> json) {
    return LageSignal(
      kind: json['kind'] as String? ?? '',
      hinweis: json['hinweis'] as String? ?? '',
      ort: json['ort'] as String?,
      zone: json['zone'] as String?,
      kraefte: json['kraefte'] as int?,
      stunden: json['stunden'] as int?,
    );
  }
}

/// Symbole der Signalarten
const Map<String, IconData> kSignalIcons = {
  'kampfmittel': Icons.dangerous_outlined,
  'verpflegungsbedarf': Icons.soup_kitchen_outlined,
  'kombilage': Icons.thunderstorm_outlined,
};
