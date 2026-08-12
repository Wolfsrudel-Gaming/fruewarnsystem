import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:fl_chart/fl_chart.dart';
import '../theme/app_theme.dart';
import '../models/api_models.dart';
import '../services/app_state.dart';
import '../widgets/score_bar.dart';
import 'lagebild_screen.dart' show waterLevelColor;

class KategorieDetailScreen extends StatefulWidget {
  final String category;
  final String label;

  const KategorieDetailScreen({super.key, required this.category, required this.label});

  @override
  State<KategorieDetailScreen> createState() => _KategorieDetailScreenState();
}

class _KategorieDetailScreenState extends State<KategorieDetailScreen> {
  List<ScoreHistoryPoint>? _history;

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
          final detail = cs?.components?['detail'] as String?;
          final contributions = (cs?.components?['contributions'] as List?)
                  ?.map((c) => c as Map<String, dynamic>)
                  .toList() ??
              [];

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _buildScoreHeader(score, detail),
              const SizedBox(height: 16),
              _buildChart(),
              const SizedBox(height: 16),
              if (contributions.isNotEmpty) ...[
                _buildContributions(contributions),
                const SizedBox(height: 16),
              ],
              _buildDetails(state),
            ],
          );
        },
      ),
    );
  }

  Widget _card({required Widget child, EdgeInsets? padding}) {
    return Container(
      padding: padding ?? const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: child,
    );
  }

  Widget _buildScoreHeader(double score, String? detail) {
    return _card(
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(widget.label,
                    style: const TextStyle(color: AppColors.textPrimary, fontSize: 18, fontWeight: FontWeight.w600)),
              ),
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
          if (detail != null && detail.isNotEmpty) ...[
            const SizedBox(height: 10),
            Align(
              alignment: Alignment.centerLeft,
              child: Text(detail,
                  style: const TextStyle(color: AppColors.textSecondary, fontSize: 13)),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildChart() {
    final history = _history;
    if (history == null) {
      return _card(
        child: const SizedBox(
          height: 150,
          child: Center(child: CircularProgressIndicator(color: AppColors.drkRed)),
        ),
      );
    }
    if (history.isEmpty) {
      return _card(
        child: const SizedBox(
          height: 100,
          child: Center(
            child: Text('Noch keine Verlaufsdaten', style: TextStyle(color: AppColors.textMuted)),
          ),
        ),
      );
    }

    final now = DateTime.now();
    final points = history
        .where((p) => p.calculatedAt != null)
        .map((p) => FlSpot(
              // Stunden relativ zu jetzt (negativ = Vergangenheit)
              p.calculatedAt!.difference(now).inMinutes / 60.0,
              p.score,
            ))
        .toList();

    return _card(
      child: SizedBox(
        height: 180,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Score-Verlauf (24h)',
                style: TextStyle(color: AppColors.textMuted, fontSize: 12)),
            const SizedBox(height: 12),
            Expanded(child: _lineChart(points)),
          ],
        ),
      ),
    );
  }

  Widget _lineChart(List<FlSpot> points) {
    return LineChart(
      LineChartData(
        gridData: FlGridData(
          show: true,
          drawVerticalLine: false,
          horizontalInterval: 25,
          getDrawingHorizontalLine: (v) => const FlLine(color: AppColors.border, strokeWidth: 0.5),
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
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 22,
              interval: 6,
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
        lineBarsData: [
          LineChartBarData(
            spots: points,
            isCurved: false,
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
    );
  }

  /// Score-Beiträge: welche Datenquelle wie viele Punkte beisteuert
  Widget _buildContributions(List<Map<String, dynamic>> contributions) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Score-Zusammensetzung',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 15, fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        _card(
          padding: const EdgeInsets.all(12),
          child: Column(
            children: contributions.take(8).map((c) {
              final points = (c['points'] as num?)?.toDouble() ?? 0;
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: 44,
                      padding: const EdgeInsets.symmetric(vertical: 2),
                      decoration: BoxDecoration(
                        color: scoreColor(points.round()).withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        '+${points.round()}',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: scoreColor(points.round()),
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            c['source'] as String? ?? '',
                            style: const TextStyle(color: AppColors.textPrimary, fontSize: 12, fontWeight: FontWeight.w500),
                          ),
                          Text(
                            c['reason'] as String? ?? '',
                            style: const TextStyle(color: AppColors.textMuted, fontSize: 11, height: 1.3),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              );
            }).toList(),
          ),
        ),
      ],
    );
  }

  Widget _buildDetails(AppState state) {
    switch (widget.category) {
      case 'water':
        return _buildWaterDetails(state);
      case 'weather':
      case 'official_warning':
        return _buildWeatherDetails(state);
      case 'fire':
        return _buildFireDetails(state);
      case 'traffic':
        return _buildTrafficDetails(state);
      case 'air_quality':
        return _buildAirQualityDetails(state);
      default:
        return const SizedBox.shrink();
    }
  }

  Widget _sectionTitle(String text) {
    return Text(text,
        style: const TextStyle(color: AppColors.textPrimary, fontSize: 15, fontWeight: FontWeight.w600));
  }

  Widget _buildWaterDetails(AppState state) {
    if (state.waterStations.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle('Pegelstationen'),
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
              Container(
                width: 4, height: 36,
                decoration: BoxDecoration(
                  color: waterLevelColor(st.warningLevel),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(width: 10),
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
                  Text(_conditionLabel(st.condition),
                      style: TextStyle(color: waterLevelColor(st.warningLevel), fontSize: 11)),
                ],
              ),
            ],
          ),
        )),
      ],
    );
  }

  String _conditionLabel(String condition) {
    switch (condition) {
      case 'normal': return 'Normal';
      case 'unterdurchschnittlich': return 'Unterdurchschnittlich';
      case 'niedrigwasser': return 'Niedrigwasser';
      case 'drought': return 'Dürre';
      case 'hochwasser': return 'Hochwasser';
      case 'starkes_hochwasser': return 'Starkes Hochwasser';
      case 'extremhochwasser': return 'Extremhochwasser';
      default: return condition;
    }
  }

  Widget _buildWeatherDetails(AppState state) {
    if (state.weatherWarnings.isEmpty) {
      return _card(
        child: const Center(
          child: Text('Keine aktiven Wetterwarnungen', style: TextStyle(color: AppColors.textMuted)),
        ),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle('Wetterwarnungen'),
        const SizedBox(height: 8),
        ...state.weatherWarnings.take(10).map((w) => Container(
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
                  Icon(Icons.warning_amber, size: 16,
                      color: w.severity >= 50 ? AppColors.red : AppColors.yellow),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(w.title,
                        style: const TextStyle(color: AppColors.textPrimary, fontSize: 14, fontWeight: FontWeight.w500)),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(w.description,
                  style: const TextStyle(color: AppColors.textSecondary, fontSize: 12),
                  maxLines: 3, overflow: TextOverflow.ellipsis),
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
        _sectionTitle('Waldbrandrisiko'),
        const SizedBox(height: 8),
        ...state.fireRisks.take(5).map((fr) => Container(
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
                  Expanded(
                    child: Text(fr.region,
                        style: const TextStyle(color: AppColors.textPrimary, fontSize: 14, fontWeight: FontWeight.w500)),
                  ),
                  if ((fr.satelliteHotspots ?? 0) > 0)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.red.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text('${fr.satelliteHotspots} Hotspots',
                          style: const TextStyle(color: AppColors.redLight, fontSize: 11, fontWeight: FontWeight.w600)),
                    ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  _metric('Index', '${fr.riskIndex.toStringAsFixed(0)}/5'),
                  _metric('Temp.', fr.temperature != null ? '${fr.temperature!.round()}°C' : '–'),
                  _metric('Feuchte', fr.humidity != null ? '${fr.humidity!.round()}%' : '–'),
                  _metric('Wind', fr.windSpeed != null ? '${fr.windSpeed!.round()} km/h' : '–'),
                ],
              ),
            ],
          ),
        )),
      ],
    );
  }

  Widget _metric(String label, String value) {
    return Expanded(
      child: Column(
        children: [
          Text(value, style: const TextStyle(color: AppColors.textPrimary, fontSize: 13, fontWeight: FontWeight.w500)),
          Text(label, style: const TextStyle(color: AppColors.textMuted, fontSize: 10)),
        ],
      ),
    );
  }

  Widget _buildAirQualityDetails(AppState state) {
    if (state.airQuality.isEmpty) {
      return _card(
        child: const Center(
          child: Text('Keine Messdaten', style: TextStyle(color: AppColors.textMuted)),
        ),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle('Messstationen'),
        const SizedBox(height: 8),
        ...state.airQuality.take(5).map((r) => Container(
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
              Text(r.stationName ?? 'Station',
                  style: const TextStyle(color: AppColors.textPrimary, fontSize: 14, fontWeight: FontWeight.w500)),
              const SizedBox(height: 8),
              Row(
                children: [
                  _metric('PM2.5', r.pm25 != null ? '${r.pm25!.round()}' : '–'),
                  _metric('PM10', r.pm10 != null ? '${r.pm10!.round()}' : '–'),
                  _metric('Ozon', r.ozone != null ? '${r.ozone!.round()}' : '–'),
                  _metric('NO₂', r.no2 != null ? '${r.no2!.round()}' : '–'),
                  _metric('AQI', r.aqi != null ? '${r.aqi!.round()}' : '–'),
                ],
              ),
            ],
          ),
        )),
      ],
    );
  }

  Widget _buildTrafficDetails(AppState state) {
    if (state.trafficEvents.isEmpty) {
      return _card(
        child: const Center(
          child: Text('Keine Verkehrsmeldungen', style: TextStyle(color: AppColors.textMuted)),
        ),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle('Verkehrsmeldungen'),
        const SizedBox(height: 8),
        ...state.trafficEvents.take(15).map((ev) => Container(
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
                ev.eventType == 'accident' ? Icons.car_crash : Icons.traffic,
                size: 18,
                color: ev.severity >= 50 ? AppColors.red : AppColors.yellow,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(ev.title,
                        style: const TextStyle(color: AppColors.textPrimary, fontSize: 13),
                        maxLines: 2, overflow: TextOverflow.ellipsis),
                    Text('${ev.road} · ${ev.eventType}',
                        style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
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
