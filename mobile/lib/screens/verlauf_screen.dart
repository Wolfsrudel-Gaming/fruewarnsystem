import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import '../theme/app_theme.dart';
import '../services/api_service.dart';

class VerlaufScreen extends StatefulWidget {
  final ApiService api;
  const VerlaufScreen({super.key, required this.api});

  @override
  State<VerlaufScreen> createState() => _VerlaufScreenState();
}

class _VerlaufScreenState extends State<VerlaufScreen> {
  int _selectedHours = 24;
  Map<String, dynamic>? _data;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final data = await widget.api.fetchScoreHistory(hours: _selectedHours);
    if (mounted) setState(() { _data = data; _loading = false; });
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
    if (_data == null) {
      return const Center(child: Text('Keine Daten', style: TextStyle(color: AppColors.textMuted)));
    }

    final points = (_data!['data_points'] as List?)
        ?.map((p) => FlSpot(
              (p['timestamp_hours'] as num?)?.toDouble() ?? 0,
              (p['score'] as num?)?.toDouble() ?? 0,
            ))
        .toList() ?? [];

    return Padding(
      padding: const EdgeInsets.all(16),
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
              child: points.isEmpty
                  ? const Center(child: Text('Keine Verlaufsdaten', style: TextStyle(color: AppColors.textMuted)))
                  : LineChart(
                      LineChartData(
                        gridData: FlGridData(
                          show: true,
                          drawVerticalLine: false,
                          horizontalInterval: 25,
                          getDrawingHorizontalLine: (v) => FlLine(color: AppColors.border, strokeWidth: 0.5),
                        ),
                        titlesData: FlTitlesData(
                          topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                          rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                          leftTitles: AxisTitles(
                            sideTitles: SideTitles(
                              showTitles: true,
                              reservedSize: 30,
                              interval: 25,
                              getTitlesWidget: (v, _) => Text(v.round().toString(), style: const TextStyle(color: AppColors.textMuted, fontSize: 10)),
                            ),
                          ),
                          bottomTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                        ),
                        borderData: FlBorderData(show: false),
                        minY: 0,
                        maxY: 100,
                        lineBarsData: [
                          LineChartBarData(
                            spots: points,
                            isCurved: true,
                            color: AppColors.drkRed,
                            barWidth: 2,
                            dotData: const FlDotData(show: false),
                            belowBarData: BarAreaData(show: true, color: AppColors.drkRed.withValues(alpha: 0.1)),
                          ),
                        ],
                      ),
                    ),
            ),
          ),
        ],
      ),
    );
  }
}
