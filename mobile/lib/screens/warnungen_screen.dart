import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../models/api_models.dart';
import '../services/app_state.dart';

/// Behördliche Warnungen (NINA, Katwarn, MoWaS, GDACS)
class WarnungenScreen extends StatelessWidget {
  const WarnungenScreen({super.key});

  Color _severityColor(String? severity) {
    switch ((severity ?? '').toLowerCase()) {
      case 'extreme': return AppColors.purple;
      case 'severe': return AppColors.red;
      case 'moderate': return AppColors.orange;
      case 'minor': return AppColors.yellow;
      default: return AppColors.textMuted;
    }
  }

  String _severityLabel(String? severity) {
    switch ((severity ?? '').toLowerCase()) {
      case 'extreme': return 'Extrem';
      case 'severe': return 'Schwer';
      case 'moderate': return 'Moderat';
      case 'minor': return 'Gering';
      default: return 'Unbekannt';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Behördliche Warnungen'),
        backgroundColor: AppColors.surface,
      ),
      body: Consumer<AppState>(
        builder: (context, state, _) {
          final warnings = state.officialWarnings;
          if (warnings.isEmpty) {
            return const Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.verified_outlined, color: AppColors.green, size: 48),
                  SizedBox(height: 12),
                  Text('Keine aktiven Warnungen',
                      style: TextStyle(color: AppColors.textSecondary)),
                ],
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: state.refreshAll,
            color: AppColors.drkRed,
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: warnings.length,
              itemBuilder: (context, i) => _warningCard(warnings[i]),
            ),
          );
        },
      ),
    );
  }

  Widget _warningCard(OfficialWarningData w) {
    final color = _severityColor(w.severity);
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.campaign, color: color, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  w.headline,
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  _severityLabel(w.severity),
                  style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
          if (w.description != null && w.description!.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              w.description!,
              style: const TextStyle(color: AppColors.textSecondary, fontSize: 13, height: 1.4),
              maxLines: 4,
              overflow: TextOverflow.ellipsis,
            ),
          ],
          if (w.instruction != null && w.instruction!.isNotEmpty) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppColors.background,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.info_outline, size: 14, color: AppColors.yellowLight),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      w.instruction!,
                      style: const TextStyle(color: AppColors.textSecondary, fontSize: 12, height: 1.4),
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 8),
          Row(
            children: [
              if (w.sourceSystem != null)
                Text(w.sourceSystem!,
                    style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
              if (w.areaDescription != null) ...[
                const Text(' · ', style: TextStyle(color: AppColors.textMuted, fontSize: 11)),
                Expanded(
                  child: Text(
                    w.areaDescription!,
                    style: const TextStyle(color: AppColors.textMuted, fontSize: 11),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }
}
