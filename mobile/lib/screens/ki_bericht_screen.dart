import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../services/app_state.dart';

class KiBerichtScreen extends StatefulWidget {
  const KiBerichtScreen({super.key});

  @override
  State<KiBerichtScreen> createState() => _KiBerichtScreenState();
}

class _KiBerichtScreenState extends State<KiBerichtScreen> {
  bool _loading = false;

  @override
  Widget build(BuildContext context) {
    return Consumer<AppState>(
      builder: (context, state, _) {
        final ov = state.overview;
        if (ov == null) {
          return const Center(
            child: Text('Keine Daten verfügbar', style: TextStyle(color: AppColors.textMuted)),
          );
        }

        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Container(
              padding: const EdgeInsets.all(16),
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
                      const Icon(Icons.auto_awesome, color: AppColors.purple, size: 20),
                      const SizedBox(width: 8),
                      const Expanded(
                        child: Text(
                          'KI-Lagebericht',
                          style: TextStyle(color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.w600),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: AppColors.purple.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Text(
                          'lokal',
                          style: TextStyle(color: AppColors.purple, fontSize: 10),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  _sectionHeader('Beurteilung'),
                  const SizedBox(height: 6),
                  _generateAssessment(ov, state),
                  const SizedBox(height: 16),

                  _sectionHeader('Erwarteter Bedarf'),
                  const SizedBox(height: 6),
                  _generateNeeds(state),
                  const SizedBox(height: 16),

                  _sectionHeader('Empfehlung'),
                  const SizedBox(height: 6),
                  _generateRecommendation(ov),
                ],
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _loading ? null : () async {
                      setState(() => _loading = true);
                      await state.refreshAll();
                      if (mounted) setState(() => _loading = false);
                    },
                    icon: _loading
                        ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.drkRed))
                        : const Icon(Icons.refresh, size: 16),
                    label: const Text('Aktualisieren'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppColors.textSecondary,
                      side: const BorderSide(color: AppColors.border),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Center(
              child: Text(
                'Basierend auf aktuellen Sensordaten',
                style: TextStyle(color: AppColors.textDim, fontSize: 11),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _sectionHeader(String text) {
    return Text(
      text,
      style: const TextStyle(color: AppColors.drkRedLight, fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 0.5),
    );
  }

  Widget _generateAssessment(dynamic ov, AppState state) {
    final score = ov.overallScore as double;
    final label = scoreLabel(score.round());
    final activeCount = state.alerts.where((a) => !a.acknowledged).length;

    String text = 'Das Gesamtrisiko liegt aktuell bei ${score.round()} ($label). ';
    if (activeCount > 0) {
      text += 'Es liegen $activeCount aktive Alarme vor. ';
    } else {
      text += 'Es liegen keine aktiven Alarme vor. ';
    }

    final highCats = ov.riskScores.entries
        .where((e) => (e.value.score as double) >= 40)
        .map((e) => e.key)
        .toList();
    if (highCats.isNotEmpty) {
      text += 'Erhöhte Werte in: ${highCats.join(", ")}.';
    } else {
      text += 'Alle Kategorien im Normalbereich.';
    }

    return Text(text, style: const TextStyle(color: AppColors.textSecondary, fontSize: 13, height: 1.5));
  }

  Widget _generateNeeds(AppState state) {
    final items = <String>[];
    final hasFlood = state.waterStations.any((s) =>
        s.warningLevel != 'normal' && s.warningLevel != 'unknown');
    if (hasFlood) items.add('Hochwasserschutz-Materialien bereitstellen');
    if (state.weatherWarnings.isNotEmpty) items.add('Wetterlage beobachten, ggf. Einsatzbereitschaft erhöhen');
    if (state.fireRisks.any((f) => f.riskIndex > 50)) items.add('Waldbrandvorsorge: Patrouillentätigkeit prüfen');
    if (items.isEmpty) items.add('Aktuell kein besonderer Bedarf erkennbar');

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: items.map((item) => Padding(
        padding: const EdgeInsets.only(bottom: 4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('  •  ', style: TextStyle(color: AppColors.textMuted, fontSize: 13)),
            Expanded(child: Text(item, style: const TextStyle(color: AppColors.textSecondary, fontSize: 13, height: 1.4))),
          ],
        ),
      )).toList(),
    );
  }

  Widget _generateRecommendation(dynamic ov) {
    final score = ov.overallScore as double;
    String text;
    if (score < 20) {
      text = 'Normalbetrieb. Routinemäßige Beobachtung der Lage fortsetzen.';
    } else if (score < 40) {
      text = 'Erhöhte Aufmerksamkeit empfohlen. Entwicklung der betroffenen Kategorien beobachten.';
    } else if (score < 60) {
      text = 'Einsatzbereitschaft prüfen. Verantwortliche informieren und Ressourcen vorhalten.';
    } else if (score < 80) {
      text = 'Sofortige Maßnahmen erforderlich. Einsatzleitung einberufen und Kräfte alarmieren.';
    } else {
      text = 'KRITISCHE LAGE. Vollalarm auslösen. Alle verfügbaren Kräfte mobilisieren.';
    }
    return Text(text, style: const TextStyle(color: AppColors.textSecondary, fontSize: 13, height: 1.5));
  }
}
