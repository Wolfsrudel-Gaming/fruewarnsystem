import 'package:flutter_test/flutter_test.dart';

import 'package:fruewarnsystem/models/api_models.dart';
import 'package:fruewarnsystem/models/categories.dart';
import 'package:fruewarnsystem/theme/app_theme.dart';

void main() {
  test('scoreColor thresholds match design spec', () {
    expect(scoreColor(0), AppColors.green);
    expect(scoreColor(25), AppColors.yellow);
    expect(scoreColor(45), AppColors.orange);
    expect(scoreColor(65), AppColors.red);
    expect(scoreColor(85), AppColors.purple);
  });

  test('category registry covers backend AlertCategory keys', () {
    const backendKeys = [
      'water', 'weather', 'fire', 'traffic', 'air_quality',
      'official_warning', 'news', 'seismic', 'radiation',
      'health', 'power', 'events', 'shipping',
    ];
    for (final key in backendKeys) {
      final cat = categoryByKey(key);
      expect(cat.key, key);
      expect(cat.label.isNotEmpty, true, reason: 'Label fehlt für $key');
    }
  });

  test('OverviewData parses backend response shape', () {
    final data = OverviewData.fromJson({
      'overall_score': 42.5,
      'risk_scores': {
        'water': {'score': 55.0, 'components': {'detail': 'Hochwasser'}},
      },
      'active_alerts': [
        {
          'id': 1,
          'category': 'water',
          'score': 55.0,
          'title': 'Test',
          'description': 'Test-Alarm',
          'escalation_level': 2,
          'acknowledged': false,
        },
      ],
      'last_updated': '2026-08-12T10:00:00',
    });
    expect(data.overallScore, 42.5);
    expect(data.riskScores['water']!.score, 55.0);
    expect(data.activeAlerts.length, 1);
    expect(data.activeAlerts.first.escalationLevel, 2);
  });

  test('FeedbackOutcome values match backend enum', () {
    expect(FeedbackOutcome.einsatz.apiValue, 'einsatz');
    expect(FeedbackOutcome.vorsorge.apiValue, 'vorsorge');
    expect(FeedbackOutcome.keinEinsatz.apiValue, 'kein_einsatz');
    expect(FeedbackOutcome.unklar.apiValue, 'unklar');
  });

  test('CalibrationReport parses learning status', () {
    final r = CalibrationReport.fromJson({
      'overall': {
        'precision': 0.75,
        'recall': 0.5,
        'true_positives': 6,
        'false_positives': 2,
        'false_negatives': 6,
        'sample_count': 14,
        'maturity': 'Erste Anpassungen aktiv',
      },
      'categories': [
        {
          'category': 'water',
          'category_label': 'Hochwasser',
          'weight_multiplier': 1.35,
          'threshold_offset': -6.0,
          'precision': 0.75,
          'recall': 0.5,
          'true_positives': 6,
          'false_negatives': 6,
          'sample_count': 14,
          'is_locked': false,
          'reason': 'Trefferquote unter Ziel',
        },
      ],
      'target_precision': 0.6,
      'target_recall': 0.85,
    });

    expect(r.recall, 0.5);
    expect(r.maturity, 'Erste Anpassungen aktiv');
    expect(r.categories.length, 1);
    final water = r.categories.first;
    expect(water.categoryLabel, 'Hochwasser');
    // Verpasste Einsaetze -> empfindlicher: Gewicht hoch, Schwelle runter
    expect(water.weightMultiplier, greaterThan(1.0));
    expect(water.thresholdOffset, lessThan(0));
  });

  test('DeploymentData flags unpredicted deployments', () {
    final d = DeploymentData.fromJson({
      'id': 3,
      'category': 'water',
      'category_label': 'Hochwasser',
      'title': 'Kellerauspumpen',
      'occurred_at': '2026-08-11T18:00:00',
      'was_predicted': false,
    });
    expect(d.wasPredicted, false);
    expect(d.title, 'Kellerauspumpen');
  });

  test('ScoreHistoryPoint parses server history format', () {
    final p = ScoreHistoryPoint.fromJson({
      'category': 'fire',
      'score': 33.0,
      'calculated_at': '2026-08-12T09:30:00',
    });
    expect(p.category, 'fire');
    expect(p.score, 33.0);
    expect(p.calculatedAt, isNotNull);
  });
}
