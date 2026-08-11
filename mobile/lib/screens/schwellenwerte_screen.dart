import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
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
          final thresholds = state.thresholds;

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.drkRed.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppColors.drkRed.withValues(alpha: 0.3)),
                ),
                child: Row(
                  children: const [
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
                'Kategorie-Schwellenwerte',
                style: TextStyle(color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 8),
              if (thresholds != null)
                ...['hochwasser', 'wetter', 'waldbrand', 'luftqualitaet', 'verkehr'].map(
                  (cat) => _buildThresholdCard(cat, thresholds),
                )
              else
                Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: AppColors.border),
                  ),
                  child: const Center(
                    child: Text('Schwellenwerte werden geladen...', style: TextStyle(color: AppColors.textMuted)),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildEscalationTable() {
    final levels = [
      _EscLevel('Push', 40, AppColors.yellow),
      _EscLevel('Telegram', 60, AppColors.orange),
      _EscLevel('SMS', 75, AppColors.red),
      _EscLevel('Sprachanruf', 85, AppColors.purple),
    ];

    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            child: Row(
              children: const [
                Expanded(flex: 2, child: Text('Kanal', style: TextStyle(color: AppColors.textMuted, fontSize: 11))),
                Expanded(child: Text('Ab Score', style: TextStyle(color: AppColors.textMuted, fontSize: 11))),
              ],
            ),
          ),
          const Divider(color: AppColors.border, height: 1),
          ...levels.map((l) => Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            child: Row(
              children: [
                Expanded(
                  flex: 2,
                  child: Text(l.label, style: const TextStyle(color: AppColors.textPrimary, fontSize: 14)),
                ),
                Expanded(
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: l.color.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      '≥ ${l.threshold}',
                      style: TextStyle(color: l.color, fontSize: 13, fontWeight: FontWeight.w600),
                      textAlign: TextAlign.center,
                    ),
                  ),
                ),
              ],
            ),
          )),
        ],
      ),
    );
  }

  Widget _buildThresholdCard(String category, Map<String, dynamic> thresholds) {
    final catData = thresholds[category] as Map<String, dynamic>? ?? {};
    final label = {
      'hochwasser': 'Hochwasser',
      'wetter': 'Wetter',
      'waldbrand': 'Waldbrand',
      'luftqualitaet': 'Luftqualität',
      'verkehr': 'Verkehr',
    }[category] ?? category;

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
          Text(label, style: const TextStyle(color: AppColors.textPrimary, fontSize: 14, fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          if (catData.isEmpty)
            const Text('Keine Schwellenwerte konfiguriert', style: TextStyle(color: AppColors.textMuted, fontSize: 12))
          else
            ...catData.entries.take(4).map((e) => Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(e.key.toString(), style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                  Text(e.value.toString(), style: const TextStyle(color: AppColors.textPrimary, fontSize: 12)),
                ],
              ),
            )),
        ],
      ),
    );
  }
}

class _EscLevel {
  final String label;
  final int threshold;
  final Color color;
  _EscLevel(this.label, this.threshold, this.color);
}
