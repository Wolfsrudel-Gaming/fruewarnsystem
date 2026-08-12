import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import '../theme/app_theme.dart';
import '../models/api_models.dart';
import '../models/categories.dart';
import '../services/api_service.dart';

class VerlaufScreen extends StatefulWidget {
  final ApiService api;
  const VerlaufScreen({super.key, required this.api});

  @override
  State<VerlaufScreen> createState() => _VerlaufScreenState();
}

class _VerlaufScreenState extends State<VerlaufScreen> {
  static const _seriesColors = [
    AppColors.drkRedLight,
    AppColors.orange,
    AppColors.yellow,
    AppColors.purpleLight,
    AppColors.greenLight,
  ];

  int _selectedHours = 24;
  List<ScoreHistoryPoint> _points = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final data = await widget.api.fetchScoreHistory(hours: _selectedHours);
    if (mounted) setState(() { _points = data; _loading = false; });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(title: const Text('Verlauf'), backgroundColor: AppColors.surface),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                _periodChip('24h', 24),
                const SizedBox(width: 8),
                _periodChip('7 Tage', 168),
                const SizedBox(width: 8),
                _periodChip('30 Tage', 720),
              ],
            ),
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator(color: AppColors.drkRed))
                : _buildContent(),
          ),
        ],
      ),
    );
  }

  Widget _periodChip(String label, int hours) {
    final selected = _selectedHours == hours;
    return GestureDetector(
      onTap: () {
        _selectedHours = hours;
        _load();
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? AppColors.drkRed : AppColors.surface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: selected ? AppColors.drkRed : AppColors.border),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: selected ? Colors.white : AppColors.textSecondary,
            fontSize: 13,
            fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
          ),
        ),
      ),
    );
  }

  Widget _buildContent() {
    if (_points.isEmpty) {
      return const Center(
        child: Text('Noch keine Verlaufsdaten', style: TextStyle(color: AppColors.textMuted)),
      );
    }

    // Nach Kategorie gruppieren
    final byCategory = <String, List<ScoreHistoryPoint>>{};
    for (final p in _points) {
      if (p.calculatedAt == null) continue;
      byCategory.putIfAbsent(p.category, () => []).add(p);
    }

    // Die 5 auffälligsten Kategorien (höchster Maximalwert) anzeigen
    final ranked = byCategory.entries.toList()
      ..sort((a, b) {
        final maxA = a.value.map((p) => p.score).reduce((x, y) => x > y ? x : y);
        final maxB = b.value.map((p) => p.score).reduce((x, y) => x > y ? x : y);
        return maxB.compareTo(maxA);
      });
    final top = ranked.take(5).toList();

    final now = DateTime.now();
    final series = <LineChartBarData>[];
    for (var i = 0; i < top.length; i++) {
      final spots = top[i].value
          .map((p) => FlSpot(
                p.calculatedAt!.difference(now).inMinutes / 60.0,
                p.score,
              ))
          .toList()
        ..sort((a, b) => a.x.compareTo(b.x));
      series.add(LineChartBarData(
        spots: spots,
        isCurved: false,
        color: _seriesColors[i % _seriesColors.length],
        barWidth: 2,
        dotData: const FlDotData(show: false),
      ));
    }

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      child: Column(
        children: [
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: AppColors.border),
              ),
              child: LineChart(
                LineChartData(
                  gridData: FlGridData(
                    show: true,
                    drawVerticalLine: false,
                    horizontalInterval: 25,
                    getDrawingHorizontalLine: (v) =>
                        const FlLine(color: AppColors.border, strokeWidth: 0.5),
                  ),
                  titlesData: FlTitlesData(
                    topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                    rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                    leftTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        reservedSize: 30,
                        interval: 25,
                        getTitlesWidget: (v, _) => Text(v.round().toString(),
                            style: const TextStyle(color: AppColors.textMuted, fontSize: 10)),
                      ),
                    ),
                    bottomTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        reservedSize: 22,
                        interval: _selectedHours <= 24 ? 6 : (_selectedHours ~/ 4).toDouble(),
                        getTitlesWidget: (v, _) => Text(
                          v >= 0 ? 'jetzt' : '${v.round()}h',
                          style: const TextStyle(color: AppColors.textMuted, fontSize: 10),
                        ),
                      ),
                    ),
                  ),
                  borderData: FlBorderData(show: false),
                  minY: 0,
                  maxY: 100,
                  lineBarsData: series,
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 12,
            runSpacing: 6,
            children: List.generate(top.length, (i) {
              final cat = categoryByKey(top[i].key);
              return Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 10, height: 10,
                    decoration: BoxDecoration(
                      color: _seriesColors[i % _seriesColors.length],
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 5),
                  Text(cat.label,
                      style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                ],
              );
            }),
          ),
        ],
      ),
    );
  }
}
