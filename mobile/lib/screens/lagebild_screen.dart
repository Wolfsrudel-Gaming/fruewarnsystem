import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../models/categories.dart';
import '../services/app_state.dart';
import '../widgets/risk_gauge.dart';
import '../widgets/category_card.dart';
import 'kategorie_detail_screen.dart';
import 'warnungen_screen.dart';
import 'lernstatus_screen.dart';

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
                const SizedBox(height: 8),
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 40),
                  child: Text(
                    'Server-URL unter Mehr → Einstellungen prüfen',
                    style: TextStyle(color: AppColors.textMuted, fontSize: 12),
                    textAlign: TextAlign.center,
                  ),
                ),
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
              const Center(
                child: Text(
                  'Gesamtrisiko',
                  style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
                ),
              ),
              // Woher der Wert kommt — der Gesamtscore folgt dem höchsten
              // Einzelrisiko, nicht einem Durchschnitt.
              if (ov?.driverLabel != null) ...[
                const SizedBox(height: 4),
                Center(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 24),
                    child: Text(
                      ov!.concurrentLabels.isEmpty
                          ? 'bestimmt durch ${ov.driverLabel}'
                          : 'bestimmt durch ${ov.driverLabel}, verschärft durch '
                              '${ov.concurrentLabels.take(3).join(", ")}',
                      style: const TextStyle(color: AppColors.textMuted, fontSize: 11),
                      textAlign: TextAlign.center,
                    ),
                  ),
                ),
              ],
              const SizedBox(height: 16),

              if (activeAlerts.isNotEmpty) ...[
                _banner(
                  icon: Icons.warning_amber_rounded,
                  text: '${activeAlerts.length} aktive${activeAlerts.length == 1 ? 'r Alarm' : ' Alarme'}',
                  color: AppColors.drkRedLight,
                ),
                const SizedBox(height: 10),
              ],
              if (state.officialWarnings.isNotEmpty) ...[
                GestureDetector(
                  onTap: () => Navigator.push(context, MaterialPageRoute(
                    builder: (_) => const WarnungenScreen(),
                  )),
                  child: _banner(
                    icon: Icons.campaign,
                    text: '${state.officialWarnings.length} behördliche Warnung${state.officialWarnings.length == 1 ? '' : 'en'} (NINA)',
                    color: AppColors.orange,
                  ),
                ),
                const SizedBox(height: 10),
              ],
              if (state.pendingFeedback.isNotEmpty) ...[
                GestureDetector(
                  onTap: () => Navigator.push(context, MaterialPageRoute(
                    builder: (_) => const LernstatusScreen(),
                  )),
                  child: _banner(
                    icon: Icons.help_outline,
                    text: '${state.pendingFeedback.length} Alarm'
                        '${state.pendingFeedback.length == 1 ? '' : 'e'} ohne Rückmeldung',
                    color: AppColors.purpleLight,
                  ),
                ),
                const SizedBox(height: 10),
              ],
              const SizedBox(height: 6),

              _sectionTitle('Kategorien'),
              const SizedBox(height: 8),
              _buildCategoryGrid(context, state),
              const SizedBox(height: 20),

              if (state.waterStations.isNotEmpty) ...[
                _sectionTitle('Pegelstände'),
                const SizedBox(height: 8),
                _buildWaterTable(state),
                const SizedBox(height: 20),
              ],

              _buildSystemStatus(state),
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

  Widget _banner({required IconData icon, required String text, required Color color}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: TextStyle(color: color, fontSize: 13, fontWeight: FontWeight.w500),
            ),
          ),
          Icon(Icons.chevron_right, color: color, size: 18),
        ],
      ),
    );
  }

  Widget _buildCategoryGrid(BuildContext context, AppState state) {
    final ov = state.overview;

    // Nach Score sortieren — die brisantesten Kategorien zuerst
    final sorted = List<RiskCategory>.from(kRiskCategories);
    double scoreOf(RiskCategory c) => ov?.riskScores[c.key]?.score ?? 0;
    sorted.sort((a, b) => scoreOf(b).compareTo(scoreOf(a)));

    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 10,
      crossAxisSpacing: 10,
      childAspectRatio: 1.5,
      children: sorted.map((cat) {
        final cs = ov?.riskScores[cat.key];
        final score = cs?.score ?? 0;
        final detail = (cs?.components?['detail'] as String?) ?? scoreLabel(score.round());
        return CategoryCard(
          icon: cat.icon,
          label: cat.label,
          score: score,
          subtitle: detail,
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
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            child: Row(
              children: [
                Expanded(flex: 3, child: Text('Station', style: TextStyle(color: AppColors.textMuted, fontSize: 11))),
                Expanded(flex: 2, child: Text('Pegel', style: TextStyle(color: AppColors.textMuted, fontSize: 11))),
                Expanded(flex: 2, child: Text('Trend', style: TextStyle(color: AppColors.textMuted, fontSize: 11))),
              ],
            ),
          ),
          const Divider(color: AppColors.border, height: 1),
          ...state.waterStations.take(6).map((st) => Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            child: Row(
              children: [
                Expanded(
                  flex: 3,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(st.stationName, style: const TextStyle(color: AppColors.textPrimary, fontSize: 13),
                          maxLines: 1, overflow: TextOverflow.ellipsis),
                      Text(st.river, style: const TextStyle(color: AppColors.textMuted, fontSize: 10)),
                    ],
                  ),
                ),
                Expanded(
                  flex: 2,
                  child: Text(
                    st.currentLevel != null ? '${st.currentLevel!.toStringAsFixed(0)} cm' : '–',
                    style: TextStyle(
                      color: waterLevelColor(st.warningLevel),
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

  Widget _buildSystemStatus(AppState state) {
    final ov = state.overview;
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
            ov != null
                ? (state.wsConnected ? 'System aktiv · Live' : 'System aktiv · Polling')
                : 'Offline',
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
    final dt = DateTime.tryParse(iso)?.toLocal();
    if (dt == null) return iso;
    return '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
  }
}

/// Farbzuordnung fuer die Server-Warnstufen der Pegel
/// (normal/below_normal/low/extreme_low/high/very_high/extreme_high).
Color waterLevelColor(String level) {
  switch (level) {
    case 'normal': return AppColors.green;
    case 'below_normal': return AppColors.yellowLight;
    case 'low': return AppColors.yellow;
    case 'extreme_low': return AppColors.orange;
    case 'high': return AppColors.orange;
    case 'very_high': return AppColors.red;
    case 'extreme_high': return AppColors.purple;
    default: return AppColors.textSecondary;
  }
}
