import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../models/categories.dart';
import '../services/app_state.dart';

class EskalationScreen extends StatelessWidget {
  const EskalationScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(title: const Text('Eskalation & Push'), backgroundColor: AppColors.surface),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'Eskalationspfad',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 12),
          _buildEscalationPath(),
          const SizedBox(height: 24),
          const Text(
            'Letzte Benachrichtigungen',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 12),
          Consumer<AppState>(
            builder: (context, state, _) {
              final recent = state.alerts.take(5).toList();
              if (recent.isEmpty) {
                return Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: AppColors.border),
                  ),
                  child: const Center(
                    child: Text('Keine Benachrichtigungen', style: TextStyle(color: AppColors.textMuted)),
                  ),
                );
              }
              return Column(
                children: recent.map((a) => Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.border),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        a.escalationLevel >= 3 ? Icons.phone : a.escalationLevel >= 2 ? Icons.sms : Icons.notifications,
                        size: 18,
                        color: scoreColor(a.score.round()),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(a.title, style: const TextStyle(color: AppColors.textPrimary, fontSize: 13)),
                            Text(
                              'Stufe ${a.escalationLevel} · ${categoryByKey(a.category).label}',
                              style: const TextStyle(color: AppColors.textMuted, fontSize: 11),
                            ),
                          ],
                        ),
                      ),
                      if (a.acknowledged)
                        const Icon(Icons.check_circle, size: 16, color: AppColors.green),
                    ],
                  ),
                )).toList(),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildEscalationPath() {
    final steps = [
      _EscStep(Icons.notifications, 'Push-Nachricht', '≥ 40', AppColors.yellow),
      _EscStep(Icons.send, 'Telegram', '≥ 60', AppColors.orange),
      _EscStep(Icons.sms, 'SMS', '≥ 75', AppColors.red),
      _EscStep(Icons.phone, 'Sprachanruf', '≥ 85', AppColors.purple),
    ];

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        children: List.generate(steps.length * 2 - 1, (i) {
          if (i.isOdd) {
            return Padding(
              padding: const EdgeInsets.only(left: 19),
              child: Container(width: 2, height: 24, color: AppColors.border),
            );
          }
          final step = steps[i ~/ 2];
          return Row(
            children: [
              Container(
                width: 40, height: 40,
                decoration: BoxDecoration(
                  color: step.color.withValues(alpha: 0.15),
                  shape: BoxShape.circle,
                ),
                child: Icon(step.icon, size: 20, color: step.color),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(step.label, style: const TextStyle(color: AppColors.textPrimary, fontSize: 14)),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: step.color.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(step.threshold, style: TextStyle(color: step.color, fontSize: 12, fontWeight: FontWeight.w500)),
              ),
            ],
          );
        }),
      ),
    );
  }
}

class _EscStep {
  final IconData icon;
  final String label;
  final String threshold;
  final Color color;
  _EscStep(this.icon, this.label, this.threshold, this.color);
}
