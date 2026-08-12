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
