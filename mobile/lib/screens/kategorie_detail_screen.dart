import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:fl_chart/fl_chart.dart';
import '../theme/app_theme.dart';
import '../services/app_state.dart';
import '../services/api_service.dart';
import '../widgets/score_bar.dart';

class KategorieDetailScreen extends StatefulWidget {
  final String category;
  final String label;

  const KategorieDetailScreen({super.key, required this.category, required this.label});

  @override
  State<KategorieDetailScreen> createState() => _KategorieDetailScreenState();
}

class _KategorieDetailScreenState extends State<KategorieDetailScreen> {
  Map<String, dynamic>? _history;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    final api = context.read<AppState>().api;
    final data = await api.fetchScoreHistory(category: widget.category, hours: 24);
    if (mounted) setState(() => _history = data);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(widget.label),
        backgroundColor: AppColors.surface,
      ),
      body: Consumer<AppState>(
        builder: (context, state, _) {
          final cs = state.overview?.riskScores[widget.category];
          final score = cs?.score ?? 0;

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _buildScoreHeader(score),
              const SizedBox(height: 16),
              _buildChart(),
              const SizedBox(height: 16),
              _buildDetails(state),
            ],
          );
        },
      ),
    );
  }

  Widget _buildScoreHeader(double score) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(widget.label, style: const TextStyle(color: AppColors.textPrimary, fontSize: 18, fontWeight: FontWeight.w600)),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                decoration: BoxDecoration(
                  color: scoreColor(score.round()).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '${score.round()} – ${scoreLabel(score.round())}',
                  style: TextStyle(color: scoreColor(score.round()), fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ScoreBar(score: score, height: 8),
        ],
      ),
    );
  }

  Widget _buildChart() {
    final history = _history;
    if (history == null) {
      return Container(
        height: 180,
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.border),
        ),
        child: const Center(child: CircularProgressIndicator(color: AppColors.drkRed)),
      );
    }

    final points = (history['data_points'] as List?)
        ?.map((p) => FlSpot(
              (p['timestamp_hours'] as num?)?.toDouble() ?? 0,
              (p['score'] as num?)?.toDouble() ?? 0,
            ))
        .toList() ?? [];

    if (points.isEmpty) {
      return Container(
        height: 180,
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.border),
        ),
        child: const Center(
          child: Text('Keine Verlaufsdaten', style: TextStyle(color: AppColors.textMuted)),
        ),
      );
    }

    return Container(
      height: 180,
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
                getTitlesWidget: (v, _) => Text(
                  v.round().toString(),
                  style: const TextStyle(color: AppColors.textMuted, fontSize: 10),
                ),
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
              belowBarData: BarAreaData(
                show: true,
                color: AppColors.drkRed.withValues(alpha: 0.1),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDetails(AppState state) {
    switch (widget.category) {
      case 'hochwasser':
        return _buildWaterDetails(state);
      case 'wetter':
        return _buildWeatherDetails(state);
      case 'waldbrand':
        return _buildFireDetails(state);
      case 'verkehr':
        return _buildTrafficDetails(state);
      default:
        return const SizedBox.shrink();
    }
  }

  Widget _buildWaterDetails(AppState state) {
    if (state.waterStations.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Pegelstationen', style: TextStyle(color: AppColors.textPrimary, fontSize: 15, fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        ...state.waterStations.map((st) => Container(
          margin: const EdgeInsets.only(bottom: 8),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.border),
          ),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(st.stationName, style: const TextStyle(color: AppColors.textPrimary, fontSize: 14)),
                    Text(st.river, style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    st.currentLevel != null ? '${st.currentLevel!.toStringAsFixed(0)} cm' : '–',
                    style: const TextStyle(color: AppColors.textPrimary, fontSize: 14, fontWeight: FontWeight.w500),
                  ),
                  Text(st.condition, style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
                ],
              ),
            ],
          ),
        )),
      ],
    );
  }

  Widget _buildWeatherDetails(AppState state) {
    if (state.weatherWarnings.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.border),
        ),
        child: const Center(
          child: Text('Keine aktiven Wetterwarnungen', style: TextStyle(color: AppColors.textMuted)),
        ),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Wetterwarnungen', style: TextStyle(color: AppColors.textPrimary, fontSize: 15, fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        ...state.weatherWarnings.map((w) => Container(
          margin: const EdgeInsets.only(bottom: 8),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.warning_amber, size: 16, color: w.severity >= 3 ? AppColors.red : AppColors.yellow),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(w.title, style: const TextStyle(color: AppColors.textPrimary, fontSize: 14, fontWeight: FontWeight.w500)),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(w.description, style: const TextStyle(color: AppColors.textSecondary, fontSize: 12), maxLines: 2, overflow: TextOverflow.ellipsis),
            ],
          ),
        )),
      ],
    );
  }

  Widget _buildFireDetails(AppState state) {
    if (state.fireRisks.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Waldbrandrisiko', style: TextStyle(color: AppColors.textPrimary, fontSize: 15, fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        ...state.fireRisks.map((fr) => Container(
          margin: const EdgeInsets.only(bottom: 8),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(fr.region, style: const TextStyle(color: AppColors.textPrimary, fontSize: 14, fontWeight: FontWeight.w500)),
              const SizedBox(height: 8),
              Row(
                children: [
                  _fireMetric('Risiko', fr.riskIndex.toStringAsFixed(1)),
                  _fireMetric('Temp.', fr.temperature != null ? '${fr.temperature!.round()}°C' : '–'),
                  _fireMetric('Feuchte', fr.humidity != null ? '${fr.humidity!.round()}%' : '–'),
                  _fireMetric('Wind', fr.windSpeed != null ? '${fr.windSpeed!.round()} km/h' : '–'),
                ],
              ),
            ],
          ),
        )),
      ],
    );
  }

  Widget _fireMetric(String label, String value) {
    return Expanded(
      child: Column(
        children: [
          Text(value, style: const TextStyle(color: AppColors.textPrimary, fontSize: 13, fontWeight: FontWeight.w500)),
          Text(label, style: const TextStyle(color: AppColors.textMuted, fontSize: 10)),
        ],
      ),
    );
  }

  Widget _buildTrafficDetails(AppState state) {
    if (state.trafficEvents.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.border),
        ),
        child: const Center(
          child: Text('Keine Verkehrsmeldungen', style: TextStyle(color: AppColors.textMuted)),
        ),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Verkehrsmeldungen', style: TextStyle(color: AppColors.textPrimary, fontSize: 15, fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        ...state.trafficEvents.map((ev) => Container(
          margin: const EdgeInsets.only(bottom: 8),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.border),
          ),
          child: Row(
            children: [
              Icon(Icons.traffic, size: 18, color: ev.severity >= 3 ? AppColors.red : AppColors.yellow),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(ev.title, style: const TextStyle(color: AppColors.textPrimary, fontSize: 13)),
                    Text('${ev.road} · ${ev.eventType}', style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
                  ],
                ),
              ),
            ],
          ),
        )),
      ],
    );
  }
}
