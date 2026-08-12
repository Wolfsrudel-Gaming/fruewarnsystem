import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../models/api_models.dart';
import '../models/categories.dart';
import '../services/app_state.dart';

/// Zeigt, wie zuverlässig das System warnt und was es aus den
/// Einsatz-Rückmeldungen bereits gelernt hat.
class LernstatusScreen extends StatefulWidget {
  const LernstatusScreen({super.key});

  @override
  State<LernstatusScreen> createState() => _LernstatusScreenState();
}

class _LernstatusScreenState extends State<LernstatusScreen> {
  CalibrationReport? _report;
  bool _loading = true;
  bool _recomputing = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final api = context.read<AppState>().api;
    final report = await api.fetchCalibration();
    if (mounted) setState(() { _report = report; _loading = false; });
  }

  Future<void> _recompute() async {
    setState(() => _recomputing = true);
    final api = context.read<AppState>().api;
    await api.recomputeCalibration();
    await _load();
    if (mounted) setState(() => _recomputing = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Lernstatus'),
        backgroundColor: AppColors.surface,
        actions: [
          IconButton(
            icon: _recomputing
                ? const SizedBox(
                    width: 18, height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.drkRed))
                : const Icon(Icons.refresh),
            onPressed: _recomputing ? null : _recompute,
            tooltip: 'Neu berechnen',
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: AppColors.drkRed))
          : _report == null
              ? const Center(
                  child: Text('Lernstatus nicht verfügbar',
                      style: TextStyle(color: AppColors.textMuted)))
              : RefreshIndicator(
                  onRefresh: _load,
                  color: AppColors.drkRed,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      _buildOverallCard(_report!),
                      const SizedBox(height: 16),
                      _buildPendingHint(),
                      const SizedBox(height: 16),
                      const Text('Nach Kategorie',
                          style: TextStyle(
                              color: AppColors.textPrimary,
                              fontSize: 16,
                              fontWeight: FontWeight.w600)),
                      const SizedBox(height: 8),
                      if (_report!.categories.isEmpty)
                        _emptyCard('Noch keine Rückmeldungen erfasst.\n'
                            'Sobald Alarme bewertet oder Einsätze gemeldet werden, '
                            'erscheint hier die Treffsicherheit je Kategorie.')
                      else
                        ..._report!.categories.map(_buildCategoryCard),
                      const SizedBox(height: 16),
                      _buildExplainer(_report!),
                      const SizedBox(height: 24),
                    ],
                  ),
                ),
    );
  }

  Widget _emptyCard(String text) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Text(text,
          style: const TextStyle(color: AppColors.textMuted, fontSize: 13, height: 1.5),
          textAlign: TextAlign.center),
    );
  }

  Widget _buildOverallCard(CalibrationReport r) {
    return Container(
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
              const Icon(Icons.school, color: AppColors.purple, size: 20),
              const SizedBox(width: 8),
              const Expanded(
                child: Text('Treffsicherheit gesamt',
                    style: TextStyle(
                        color: AppColors.textPrimary,
                        fontSize: 16,
                        fontWeight: FontWeight.w600)),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AppColors.purple.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(r.maturity,
                    style: const TextStyle(color: AppColors.purple, fontSize: 10)),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _metricTile(
                  'Trefferquote',
                  r.recall,
                  r.targetRecall,
                  'Anteil echter Einsätze, vor denen gewarnt wurde',
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _metricTile(
                  'Genauigkeit',
                  r.precision,
                  r.targetPrecision,
                  'Anteil der Alarme, die berechtigt waren',
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          const Divider(color: AppColors.border, height: 1),
          const SizedBox(height: 12),
          Row(
            children: [
              _countChip('Treffer', r.truePositives, AppColors.green),
              const SizedBox(width: 8),
              _countChip('Fehlalarme', r.falsePositives, AppColors.yellow),
              const SizedBox(width: 8),
              _countChip('Verpasst', r.falseNegatives, AppColors.red),
            ],
          ),
        ],
      ),
    );
  }

  Widget _metricTile(String label, double? value, double target, String hint) {
    final pct = value != null ? (value * 100).round() : null;
    final good = value != null && value >= target;
    final color = value == null
        ? AppColors.textMuted
        : good
            ? AppColors.green
            : value >= target * 0.7
                ? AppColors.yellow
                : AppColors.red;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
          const SizedBox(height: 4),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(pct != null ? '$pct%' : '–',
                  style: TextStyle(
                      color: color, fontSize: 24, fontWeight: FontWeight.bold)),
              const SizedBox(width: 6),
              Text('Ziel ${(target * 100).round()}%',
                  style: const TextStyle(color: AppColors.textDim, fontSize: 10)),
            ],
          ),
          const SizedBox(height: 6),
          LinearProgressIndicator(
            value: value ?? 0,
            minHeight: 4,
            backgroundColor: AppColors.border,
            valueColor: AlwaysStoppedAnimation(color),
          ),
          const SizedBox(height: 6),
          Text(hint,
              style: const TextStyle(color: AppColors.textDim, fontSize: 10, height: 1.3)),
        ],
      ),
    );
  }

  Widget _countChip(String label, int count, Color color) {
    return Expanded(
      child: Column(
        children: [
          Text('$count',
              style: TextStyle(color: color, fontSize: 18, fontWeight: FontWeight.bold)),
          Text(label, style: const TextStyle(color: AppColors.textMuted, fontSize: 10)),
        ],
      ),
    );
  }

  Widget _buildPendingHint() {
    return Consumer<AppState>(
      builder: (context, state, _) {
        final pending = state.pendingFeedback.length;
        if (pending == 0) return const SizedBox.shrink();
        return Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppColors.orange.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.orange.withValues(alpha: 0.3)),
          ),
          child: Row(
            children: [
              const Icon(Icons.pending_actions, size: 18, color: AppColors.orange),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  '$pending Alarm${pending == 1 ? '' : 'e'} ohne Rückmeldung — '
                  'unter "Alarme" bewertbar',
                  style: const TextStyle(color: AppColors.orange, fontSize: 12, height: 1.4),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildCategoryCard(CategoryCalibration c) {
    final cat = categoryByKey(c.category);
    final multiplier = c.weightMultiplier;
    final offset = c.thresholdOffset;
    final adjusted = (multiplier - 1.0).abs() > 0.01 || offset.abs() > 0.5;

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
              Icon(cat.icon, size: 18, color: AppColors.textSecondary),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  c.categoryLabel.isNotEmpty ? c.categoryLabel : cat.label,
                  style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 14,
                      fontWeight: FontWeight.w600),
                ),
              ),
              if (c.isLocked)
                const Icon(Icons.lock, size: 14, color: AppColors.textMuted),
              const SizedBox(width: 6),
              Text('${c.sampleCount} Meldungen',
                  style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              _miniStat('Trefferquote', c.recall),
              _miniStat('Genauigkeit', c.precision),
              _miniStat2('Treffer', '${c.truePositives}', AppColors.green),
              _miniStat2('Verpasst', '${c.falseNegatives}',
                  c.falseNegatives > 0 ? AppColors.red : AppColors.textMuted),
            ],
          ),
          if (adjusted) ...[
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppColors.background,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        multiplier > 1.0 || offset < 0
                            ? Icons.trending_up
                            : Icons.trending_down,
                        size: 14,
                        color: multiplier > 1.0 || offset < 0
                            ? AppColors.orange
                            : AppColors.green,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        multiplier > 1.0 || offset < 0
                            ? 'System warnt hier empfindlicher'
                            : 'System ist hier zurückhaltender',
                        style: TextStyle(
                          color: multiplier > 1.0 || offset < 0
                              ? AppColors.orange
                              : AppColors.green,
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      Text('Gewicht ×${multiplier.toStringAsFixed(2)}',
                          style: const TextStyle(
                              color: AppColors.textSecondary, fontSize: 11)),
                      const SizedBox(width: 12),
                      Text(
                        'Schwelle ${offset >= 0 ? '+' : ''}${offset.toStringAsFixed(0)}',
                        style: const TextStyle(
                            color: AppColors.textSecondary, fontSize: 11),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
          if (c.reason != null && c.reason!.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(c.reason!,
                style: const TextStyle(
                    color: AppColors.textMuted, fontSize: 11, height: 1.4)),
          ],
        ],
      ),
    );
  }

  Widget _miniStat(String label, double? value) {
    return Expanded(
      child: Column(
        children: [
          Text(value != null ? '${(value * 100).round()}%' : '–',
              style: const TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 14,
                  fontWeight: FontWeight.w600)),
          Text(label, style: const TextStyle(color: AppColors.textMuted, fontSize: 10)),
        ],
      ),
    );
  }

  Widget _miniStat2(String label, String value, Color color) {
    return Expanded(
      child: Column(
        children: [
          Text(value,
              style: TextStyle(color: color, fontSize: 14, fontWeight: FontWeight.w600)),
          Text(label, style: const TextStyle(color: AppColors.textMuted, fontSize: 10)),
        ],
      ),
    );
  }

  Widget _buildExplainer(CalibrationReport r) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.info_outline, size: 16, color: AppColors.textMuted),
              SizedBox(width: 8),
              Text('Wie das System lernt',
                  style: TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 14,
                      fontWeight: FontWeight.w600)),
            ],
          ),
          const SizedBox(height: 10),
          const Text(
            'Jede Rückmeldung zu einem Alarm und jeder gemeldete Einsatz fließen '
            'in die Bewertung ein. Einmal täglich passt das System daraus Gewichtung '
            'und Auslöseschwelle jeder Kategorie an.\n\n'
            'Ein verpasster Einsatz wiegt dabei schwerer als ein Fehlalarm — das System '
            'wird lieber einmal zu oft laut. Anpassungen erfolgen gedämpft und begrenzt, '
            'damit einzelne Meldungen nichts kippen. Behördliche Warnungen und '
            'Strahlungsalarme werden nie gedämpft.',
            style: TextStyle(color: AppColors.textSecondary, fontSize: 12, height: 1.5),
          ),
          const SizedBox(height: 10),
          Text(
            'Ab ${r.sampleCount >= 5 ? "" : "5 "}Rückmeldungen je Kategorie beginnt die '
            'automatische Anpassung — aktuell ${r.sampleCount} insgesamt.',
            style: const TextStyle(color: AppColors.textDim, fontSize: 11, height: 1.4),
          ),
        ],
      ),
    );
  }
}
