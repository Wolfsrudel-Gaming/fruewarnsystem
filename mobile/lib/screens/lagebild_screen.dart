import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../services/app_state.dart';
import '../widgets/risk_gauge.dart';
import '../widgets/category_card.dart';
import '../widgets/alert_card.dart';
import 'kategorie_detail_screen.dart';

class LagebildScreen extends StatelessWidget {
  const LagebildScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<AppState>(
      builder: (context, state, _) {
        if (state.loading) {
          return const Center(
            child: CircularProgressIndicator(color: AppColors.drkRed),
          );
        }
        if (state.error != null && state.overview == null) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.cloud_off, color: AppColors.textMuted, size: 48),
                const SizedBox(height: 12),
                Text(state.error!, style: const TextStyle(color: AppColors.textSecondary)),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: state.refreshAll,
                  style: ElevatedButton.styleFrom(backgroundColor: AppColors.drkRed),
                  child: const Text('Erneut versuchen'),
                ),
              ],
            ),
          );
        }

        final ov = state.overview;
        final activeAlerts = state.alerts.where((a) => !a.acknowledged).toList();

        return RefreshIndicator(
          onRefresh: state.refreshAll,
          color: AppColors.drkRed,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Center(
                child: RiskGauge(
                  score: ov?.overallScore ?? 0,
                  size: MediaQuery.of(context).size.width * 0.55,
                ),
              ),
              const SizedBox(height: 8),
              Center(
                child: Text(
                  'Gesamtrisiko',
                  style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
                ),
              ),
              const SizedBox(height: 16),

              if (activeAlerts.isNotEmpty) ...[
                _buildAlertBanner(activeAlerts),
                const SizedBox(height: 16),
              ],

              _sectionTitle('Kategorien'),
              const SizedBox(height: 8),
              _buildCategoryGrid(context, ov),
              const SizedBox(height: 20),

              if (state.waterStations.isNotEmpty) ...[
                _sectionTitle('Pegelstände'),
                const SizedBox(height: 8),
                _buildWaterTable(state),
                const SizedBox(height: 20),
              ],

              _buildSystemStatus(ov),
              const SizedBox(height: 24),
            ],
          ),
        );
      },
    );
  }

  Widget _sectionTitle(String text) {
    return Text(
      text,
      style: const TextStyle(
        color: AppColors.textPrimary,
        fontSize: 16,
        fontWeight: FontWeight.w600,
      ),
    );
  }

  Widget _buildAlertBanner(List<dynamic> alerts) {
    final count = alerts.length;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.drkRed.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.drkRed.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          const Icon(Icons.warning_amber_rounded, color: AppColors.drkRedLight, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '$count aktive${count == 1 ? 'r Alarm' : ' Alarme'}',
              style: const TextStyle(color: AppColors.drkRedAccent, fontSize: 13, fontWeight: FontWeight.w500),
            ),
          ),
          const Icon(Icons.chevron_right, color: AppColors.drkRedAccent, size: 18),
        ],
      ),
    );
  }

  Widget _buildCategoryGrid(BuildContext context, dynamic ov) {
    final categories = <_Cat>[
      _Cat('Hochwasser', 'hochwasser', Icons.water),
      _Cat('Wetter', 'wetter', Icons.thunderstorm),
      _Cat('Waldbrand', 'waldbrand', Icons.local_fire_department),
      _Cat('Luftqualität', 'luftqualitaet', Icons.air),
      _Cat('Verkehr', 'verkehr', Icons.traffic),
    ];

    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 10,
      crossAxisSpacing: 10,
      childAspectRatio: 1.5,
      children: categories.map((cat) {
        final cs = ov?.riskScores[cat.key];
        return CategoryCard(
          icon: cat.icon,
          label: cat.label,
          score: cs?.score ?? 0,
          subtitle: scoreLabel((cs?.score ?? 0).round()),
          onTap: () {
            Navigator.of(context).push(MaterialPageRoute(
              builder: (_) => KategorieDetailScreen(category: cat.key, label: cat.label),
            ));
          },
        );
      }).toList(),
    );
  }

  Widget _buildWaterTable(AppState state) {
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
                Expanded(flex: 3, child: Text('Station', style: TextStyle(color: AppColors.textMuted, fontSize: 11))),
                Expanded(flex: 2, child: Text('Pegel', style: TextStyle(color: AppColors.textMuted, fontSize: 11))),
                Expanded(flex: 2, child: Text('Trend', style: TextStyle(color: AppColors.textMuted, fontSize: 11))),
              ],
            ),
          ),
          const Divider(color: AppColors.border, height: 1),
          ...state.waterStations.take(5).map((st) => Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            child: Row(
              children: [
                Expanded(
                  flex: 3,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(st.stationName, style: const TextStyle(color: AppColors.textPrimary, fontSize: 13)),
                      Text(st.river, style: const TextStyle(color: AppColors.textMuted, fontSize: 10)),
                    ],
                  ),
                ),
                Expanded(
                  flex: 2,
                  child: Text(
                    st.currentLevel != null ? '${st.currentLevel!.toStringAsFixed(0)} cm' : '–',
                    style: TextStyle(
                      color: _waterColor(st.warningLevel),
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
                Expanded(
                  flex: 2,
                  child: Row(
                    children: [
                      Icon(
                        st.trend == 'rising' ? Icons.trending_up
                            : st.trend == 'falling' ? Icons.trending_down
                            : Icons.trending_flat,
                        size: 16,
                        color: st.trend == 'rising' ? AppColors.orange
                            : st.trend == 'falling' ? AppColors.green
                            : AppColors.textMuted,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        st.trend == 'rising' ? 'Steigend'
                            : st.trend == 'falling' ? 'Fallend'
                            : 'Stabil',
                        style: const TextStyle(color: AppColors.textSecondary, fontSize: 11),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          )),
        ],
      ),
    );
  }

  Color _waterColor(String level) {
    switch (level) {
      case 'normal': return AppColors.green;
      case 'meldepegel': return AppColors.yellow;
      case 'hochwasser_1': return AppColors.orange;
      case 'hochwasser_2': return AppColors.red;
      case 'hochwasser_3': return AppColors.purple;
      default: return AppColors.textSecondary;
    }
  }

  Widget _buildSystemStatus(dynamic ov) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          Container(
            width: 8, height: 8,
            decoration: BoxDecoration(
              color: ov != null ? AppColors.green : AppColors.red,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            ov != null ? 'System aktiv' : 'Offline',
            style: TextStyle(
              color: ov != null ? AppColors.green : AppColors.red,
              fontSize: 12,
            ),
          ),
          const Spacer(),
          if (ov?.lastUpdated != null && ov!.lastUpdated.isNotEmpty)
            Text(
              'Aktualisiert: ${_formatTime(ov.lastUpdated)}',
              style: const TextStyle(color: AppColors.textMuted, fontSize: 11),
            ),
        ],
      ),
    );
  }

  String _formatTime(String iso) {
    try {
      final dt = DateTime.parse(iso);
      return '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) {
      return iso;
    }
  }
}

class _Cat {
  final String label;
  final String key;
  final IconData icon;
  _Cat(this.label, this.key, this.icon);
}
