import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../models/categories.dart';
import '../services/app_state.dart';

class SchwellenwerteScreen extends StatelessWidget {
  const SchwellenwerteScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(title: const Text('Schwellenwerte'), backgroundColor: AppColors.surface),
      body: Consumer<AppState>(
        builder: (context, state, _) {
          return RefreshIndicator(
            onRefresh: state.refreshAll,
            color: AppColors.drkRed,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.drkRed.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.drkRed.withValues(alpha: 0.3)),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.lock, size: 16, color: AppColors.drkRedAccent),
                      SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Nur Einsatzleitung kann Schwellenwerte ändern',
                          style: TextStyle(color: AppColors.drkRedAccent, fontSize: 12),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),

                const Text(
                  'Eskalationsstufen',
                  style: TextStyle(color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 8),
                _buildEscalationTable(),
                const SizedBox(height: 24),

                const Text(
                  'Alarm-Schwellenwerte',
                  style: TextStyle(color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 8),
                if (state.thresholds.isEmpty)
                  Container(
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      color: AppColors.surface,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: const Center(
                      child: Text('Keine Schwellenwerte geladen',
                          style: TextStyle(color: AppColors.textMuted)),
                    ),
                  )
                else
                  ...state.thresholds.map(_buildThresholdCard),
                const SizedBox(height: 16),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildEscalationTable() {
    final levels = [
      _EscLevel('Push (ntfy)', 'Stufe 1', AppColors.yellow),
      _EscLevel('+ Telegram', 'Stufe 2 · Score ≥ 60', AppColors.orange),
      _EscLevel('+ SMS', 'Stufe 3 · Score ≥ 75', AppColors.red),
      _EscLevel('+ E-Mail / Anruf', 'Stufe 4 · Score ≥ 85', AppColors.purple),
    ];

    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        children: levels.map((l) => Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          child: Row(
            children: [
              Container(
                width: 10, height: 10,
                decoration: BoxDecoration(color: l.color, shape: BoxShape.circle),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(l.label,
                    style: const TextStyle(color: AppColors.textPrimary, fontSize: 14)),
              ),
              Text(l.detail,
                  style: TextStyle(color: l.color, fontSize: 12, fontWeight: FontWeight.w500)),
            ],
          ),
        )).toList(),
      ),
    );
  }

  /// Server-Format: {id, category, name, condition: {min_score, type?},
  ///                 score_contribution, notification_channels, is_enabled}
  Widget _buildThresholdCard(Map<String, dynamic> t) {
    final cat = categoryByKey(t['category'] as String? ?? '');
    final condition = t['condition'] as Map<String, dynamic>? ?? {};
    final minScore = (condition['min_score'] as num?)?.toInt() ?? 50;
    final channels = (t['notification_channels'] as List?)?.cast<String>() ?? [];
    final enabled = t['is_enabled'] as bool? ?? false;

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(cat.icon, size: 18,
                  color: enabled ? AppColors.drkRedLight : AppColors.textDim),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  t['name'] as String? ?? cat.label,
                  style: TextStyle(
                    color: enabled ? AppColors.textPrimary : AppColors.textDim,
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: scoreColor(minScore).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  '≥ $minScore',
                  style: TextStyle(
                      color: scoreColor(minScore), fontSize: 13, fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Text(cat.label, style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
              if (condition['type'] != null) ...[
                const Text(' · ', style: TextStyle(color: AppColors.textMuted, fontSize: 11)),
                Text(condition['type'].toString(),
                    style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
              ],
              const Spacer(),
              ...channels.map((c) => Padding(
                padding: const EdgeInsets.only(left: 6),
                child: Icon(
                  c == 'push' ? Icons.notifications
                      : c == 'telegram' ? Icons.send
                      : c == 'sms' ? Icons.sms
                      : Icons.email,
                  size: 14,
                  color: AppColors.textSecondary,
                ),
              )),
              if (!enabled)
                const Padding(
                  padding: EdgeInsets.only(left: 8),
                  child: Text('Deaktiviert',
                      style: TextStyle(color: AppColors.textDim, fontSize: 11)),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _EscLevel {
  final String label;
  final String detail;
  final Color color;
  _EscLevel(this.label, this.detail, this.color);
}
