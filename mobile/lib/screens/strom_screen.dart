import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:fl_chart/fl_chart.dart';
import '../theme/app_theme.dart';
import '../models/api_models.dart';
import '../services/app_state.dart';

/// Stromnetz im Detail — alles, was SMARD (Bundesnetzagentur) hergibt:
/// Erzeugungsmix nach Energieträger, Netzlast, Bilanz, EE-Anteil,
/// Börsenpreis und Erzeugungsprognose, bundesweit und für die
/// Regelzone Amprion, in der Troisdorf liegt.
class StromScreen extends StatefulWidget {
  const StromScreen({super.key});

  @override
  State<StromScreen> createState() => _StromScreenState();
}

class _StromScreenState extends State<StromScreen> {
  PowerDetail? _detail;
  PowerOutageReport? _outages;
  bool _loading = true;
  int _regionIndex = 0;

  /// Farben je Energieträger — an die üblichen SMARD-Farben angelehnt
  static const _partColors = {
    'Photovoltaik': Color(0xFFFACC15),
    'Wind Onshore': Color(0xFF38BDF8),
    'Wind Offshore': Color(0xFF0EA5E9),
    'Wasserkraft': Color(0xFF22D3EE),
    'Biomasse': Color(0xFF4ADE80),
    'Sonstige Erneuerbare': Color(0xFF86EFAC),
    'Erdgas': Color(0xFFFB923C),
    'Steinkohle': Color(0xFF9CA3AF),
    'Braunkohle': Color(0xFF92400E),
    'Kernenergie': Color(0xFFA855F7),
    'Pumpspeicher': Color(0xFF818CF8),
    'Sonstige Konventionelle': Color(0xFF6B7280),
  };

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final api = context.read<AppState>().api;
    final results = await Future.wait([
      api.fetchPowerDetail(),
      api.fetchOutages(),
    ]);
    if (!mounted) return;
    setState(() {
      _detail = results[0] as PowerDetail?;
      _outages = results[1] as PowerOutageReport?;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(title: const Text('Stromnetz'), backgroundColor: AppColors.surface),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: AppColors.drkRed))
          : (_detail == null || _detail!.regions.isEmpty)
              ? RefreshIndicator(
                  onRefresh: _load,
                  color: AppColors.drkRed,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [_outageCard(), const SizedBox(height: 16), _empty()],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _load,
                  color: AppColors.drkRed,
                  child: _content(),
                ),
    );
  }

  Widget _empty() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 40),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.bolt_outlined, size: 48, color: AppColors.textMuted),
            const SizedBox(height: 12),
            const Text('Noch keine Stromdaten',
                style: TextStyle(color: AppColors.textSecondary)),
            const SizedBox(height: 6),
            const Text(
              'Der Collector holt die SMARD-Daten regelmäßig; nach dem ersten '
              'Lauf erscheinen sie hier.',
              style: TextStyle(color: AppColors.textMuted, fontSize: 12),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _load,
              style: ElevatedButton.styleFrom(backgroundColor: AppColors.drkRed),
              child: const Text('Neu laden'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _content() {
    final regions = _detail!.regions;
    final idx = _regionIndex.clamp(0, regions.length - 1);
    final r = regions[idx];

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (regions.length > 1) ...[
          Row(
            children: List.generate(regions.length, (i) {
              final selected = i == idx;
              return Expanded(
                child: GestureDetector(
                  onTap: () => setState(() => _regionIndex = i),
                  child: Container(
                    margin: EdgeInsets.only(right: i < regions.length - 1 ? 8 : 0),
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    decoration: BoxDecoration(
                      color: selected ? AppColors.drkRed : AppColors.surface,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                          color: selected ? AppColors.drkRed : AppColors.border),
                    ),
                    child: Text(
                      regions[i].region == 'DE' ? 'Deutschland' : 'Amprion (lokal)',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: selected ? Colors.white : AppColors.textSecondary,
                        fontSize: 13,
                        fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
                      ),
                    ),
                  ),
                ),
              );
            }),
          ),
          const SizedBox(height: 16),
        ],

        _outageCard(),
        const SizedBox(height: 16),
        _summaryCard(r),
        const SizedBox(height: 16),
        _mixCard(r),
        const SizedBox(height: 16),
        _priceAndForecastCard(r),
        const SizedBox(height: 16),
        _historyCard(r.region),
        const SizedBox(height: 16),
        _sourceNote(r),
        const SizedBox(height: 24),
      ],
    );
  }

  /// Konkrete Stromausfälle — das eigentlich einsatzrelevante Signal.
  /// Steht bewusst ganz oben, vor der bundesweiten Erzeugungsbilanz.
  Widget _outageCard() {
    final rep = _outages;
    if (rep == null) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Kernbereich: Rhein-Sieg-Kreis — jeder Ausfall zählt
        if (!rep.hasCore)
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppColors.green.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppColors.green.withValues(alpha: 0.3)),
            ),
            child: const Row(
              children: [
                Icon(Icons.check_circle_outline, size: 20, color: AppColors.green),
                SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Keine Stromausfälle im Rhein-Sieg-Kreis',
                    style: TextStyle(color: AppColors.green, fontSize: 13),
                  ),
                ),
              ],
            ),
          )
        else
          _coreOutageCard(rep),

        // Außerhalb: nur Großereignisse ab 100 Meldungen
        if (rep.largeScale.isNotEmpty) ...[
          const SizedBox(height: 10),
          _largeScaleCard(rep),
        ],
      ],
    );
  }

  Widget _coreOutageCard(PowerOutageReport rep) {
    final hasConfirmed = rep.confirmed.isNotEmpty;
    final color = hasConfirmed ? AppColors.red : AppColors.orange;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(hasConfirmed ? Icons.power_off : Icons.help_outline,
                  size: 20, color: color),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  hasConfirmed
                      ? '${rep.confirmed.length} bestätigte${rep.confirmed.length == 1 ? "r" : ""} '
                          'Stromausfall${rep.confirmed.length == 1 ? "" : "e"}'
                      : '${rep.reported.length} unbestätigte Meldung'
                          '${rep.reported.length == 1 ? "" : "en"}',
                  style: TextStyle(
                      color: color, fontSize: 14, fontWeight: FontWeight.w700),
                ),
              ),
              if (rep.nearestKm != null)
                Text('nächster ${rep.nearestKm!.toStringAsFixed(0)} km',
                    style: TextStyle(color: color, fontSize: 11)),
            ],
          ),
          const SizedBox(height: 4),
          const Text('Rhein-Sieg-Kreis',
              style: TextStyle(color: AppColors.textMuted, fontSize: 11)),
          const SizedBox(height: 10),
          ...rep.core.take(6).map(_outageRow),
          if (rep.core.length > 6)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text('… und ${rep.core.length - 6} weitere',
                  style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
            ),
        ],
      ),
    );
  }

  /// Großereignisse außerhalb des Kreises — mögliche Amtshilfe-Lage,
  /// bewusst zurückhaltender dargestellt als lokale Ausfälle.
  Widget _largeScaleCard(PowerOutageReport rep) {
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
          Row(
            children: [
              const Icon(Icons.public, size: 18, color: AppColors.textSecondary),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  '${rep.largeScale.length} Großereignis'
                  '${rep.largeScale.length == 1 ? "" : "se"} außerhalb des Kreises',
                  style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 13,
                      fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          ...rep.largeScale.map((o) {
            // Ab 500 Meldungen gilt es als eindeutige überregionale Lage
            final clear = o.reportCount >= 500;
            final color = clear ? AppColors.orange : AppColors.textMuted;
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                    decoration: BoxDecoration(
                      color: color.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text('${o.reportCount}',
                        style: TextStyle(
                            color: color, fontSize: 11, fontWeight: FontWeight.bold)),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(o.city ?? 'Unbekannt',
                            style: const TextStyle(
                                color: AppColors.textPrimary, fontSize: 13),
                            maxLines: 1, overflow: TextOverflow.ellipsis),
                        Text(
                          '${o.distanceKm?.toStringAsFixed(0) ?? "?"} km · '
                          '${clear ? "überregionale Lage" : "Schwelle knapp erreicht"}',
                          style: TextStyle(color: color, fontSize: 11),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            );
          }),
          const SizedBox(height: 2),
          const Text(
            'Außerhalb des Kreises wird erst ab 100 Meldungen erfasst, '
            'ab 500 gilt es als klare überregionale Lage.',
            style: TextStyle(color: AppColors.textDim, fontSize: 10, height: 1.4),
          ),
        ],
      ),
    );
  }

  Widget _outageRow(PowerOutageData o) {
    final color = o.isConfirmed ? AppColors.red : AppColors.orange;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            margin: const EdgeInsets.only(top: 4),
            width: 8, height: 8,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        '${o.postalCode ?? ""} ${o.city ?? "Unbekannt"}'.trim(),
                        style: const TextStyle(
                            color: AppColors.textPrimary,
                            fontSize: 13,
                            fontWeight: FontWeight.w500),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Text('${o.distanceKm?.toStringAsFixed(0) ?? "?"} km',
                        style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
                  ],
                ),
                Text(
                  o.isConfirmed
                      ? [
                          o.operatorName ?? 'Netzbetreiber',
                          if (o.expectedEnd != null) 'bis ${_time(o.expectedEnd!)}',
                        ].join(' · ')
                      : '${o.reportCount} Bürgermeldungen · noch unbestätigt',
                  style: TextStyle(color: color, fontSize: 11),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _card({required Widget child}) => Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.border),
        ),
        child: child,
      );

  Widget _summaryCard(PowerRegionData r) {
    final balance = r.balanceMw ?? 0;
    final surplus = balance >= 0;
    return _card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.bolt, color: AppColors.yellowLight, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  r.regionLabel.isNotEmpty ? r.regionLabel : r.region,
                  style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 15,
                      fontWeight: FontWeight.w600),
                ),
              ),
              if (r.isStressed)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppColors.red.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Text('Netzstress',
                      style: TextStyle(color: AppColors.redLight, fontSize: 10)),
                ),
            ],
          ),
          if (r.stressIndicator != null) ...[
            const SizedBox(height: 6),
            Text(r.stressIndicator!,
                style: const TextStyle(color: AppColors.redLight, fontSize: 12)),
          ],
          const SizedBox(height: 14),
          Row(
            children: [
              _bigStat('Netzlast', _mw(r.consumptionMw), AppColors.textPrimary),
              _bigStat('Erzeugung', _mw(r.generationMw), AppColors.greenLight),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              _bigStat(
                surplus ? 'Überschuss' : 'Unterdeckung',
                _mw(balance.abs()),
                surplus ? AppColors.green : AppColors.orange,
              ),
              _bigStat(
                'Erneuerbar',
                r.renewableShare != null
                    ? '${(r.renewableShare! * 100).toStringAsFixed(0)} %'
                    : '–',
                AppColors.greenLight,
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _bigStat(String label, String value, Color color) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
          const SizedBox(height: 2),
          Text(value,
              style: TextStyle(color: color, fontSize: 19, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }

  String _mw(double? v) {
    if (v == null) return '–';
    if (v.abs() >= 1000) return '${(v / 1000).toStringAsFixed(1)} GW';
    return '${v.toStringAsFixed(0)} MW';
  }

  Widget _mixCard(PowerRegionData r) {
    final parts = r.sortedParts;
    if (parts.isEmpty) return const SizedBox.shrink();
    final total = parts.fold<double>(0, (s, e) => s + e.value);

    return _card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Erzeugungsmix',
              style: TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 15,
                  fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          Text('${parts.length} Energieträger · ${_mw(total)} gesamt',
              style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
          const SizedBox(height: 14),

          // Gestapelter Anteilsbalken
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: SizedBox(
              height: 12,
              child: Row(
                children: parts.map((e) {
                  return Expanded(
                    flex: (e.value / total * 1000).round().clamp(1, 1000),
                    child: Container(
                      color: _partColors[e.key] ?? AppColors.textMuted,
                    ),
                  );
                }).toList(),
              ),
            ),
          ),
          const SizedBox(height: 16),

          ...parts.map((e) {
            final share = e.value / total;
            final color = _partColors[e.key] ?? AppColors.textMuted;
            return Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Row(
                children: [
                  Container(
                    width: 10, height: 10,
                    decoration: BoxDecoration(color: color, shape: BoxShape.circle),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Row(
                      children: [
                        Flexible(
                          child: Text(e.key,
                              style: const TextStyle(
                                  color: AppColors.textPrimary, fontSize: 13),
                              overflow: TextOverflow.ellipsis),
                        ),
                        if (r.isRenewable(e.key)) ...[
                          const SizedBox(width: 5),
                          const Icon(Icons.eco, size: 12, color: AppColors.green),
                        ],
                      ],
                    ),
                  ),
                  Text('${(share * 100).toStringAsFixed(1)} %',
                      style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
                  const SizedBox(width: 10),
                  SizedBox(
                    width: 68,
                    child: Text(_mw(e.value),
                        textAlign: TextAlign.right,
                        style: const TextStyle(
                            color: AppColors.textSecondary,
                            fontSize: 12,
                            fontWeight: FontWeight.w500)),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _priceAndForecastCard(PowerRegionData r) {
    if (r.priceEurMwh == null && r.forecastTotalMw == null) {
      return const SizedBox.shrink();
    }
    final price = r.priceEurMwh;
    // Negative Preise treten bei hoher EE-Einspeisung auf
    final priceColor = price == null
        ? AppColors.textMuted
        : price < 0
            ? AppColors.purple
            : price < 50
                ? AppColors.green
                : price < 150
                    ? AppColors.yellow
                    : AppColors.orange;

    return _card(
      child: Row(
        children: [
          if (price != null)
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Börsenpreis (Day-Ahead)',
                      style: TextStyle(color: AppColors.textMuted, fontSize: 11)),
                  const SizedBox(height: 2),
                  Text('${price.toStringAsFixed(2)} €',
                      style: TextStyle(
                          color: priceColor,
                          fontSize: 19,
                          fontWeight: FontWeight.bold)),
                  const Text('je MWh',
                      style: TextStyle(color: AppColors.textDim, fontSize: 10)),
                ],
              ),
            ),
          if (r.forecastTotalMw != null)
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Erzeugungsprognose',
                      style: TextStyle(color: AppColors.textMuted, fontSize: 11)),
                  const SizedBox(height: 2),
                  Text(_mw(r.forecastTotalMw),
                      style: const TextStyle(
                          color: AppColors.textPrimary,
                          fontSize: 19,
                          fontWeight: FontWeight.bold)),
                  Text(
                    r.generationMw != null
                        ? 'real ${_mw(r.generationMw)}'
                        : 'SMARD-Prognose',
                    style: const TextStyle(color: AppColors.textDim, fontSize: 10),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _historyCard(String region) {
    final points = _detail!.history
        .where((h) => h.region == region && h.timestamp != null)
        .toList()
      ..sort((a, b) => a.timestamp!.compareTo(b.timestamp!));

    if (points.length < 2) return const SizedBox.shrink();

    final now = DateTime.now();
    FlSpot? spot(double? v, DateTime t) =>
        v == null ? null : FlSpot(t.difference(now).inMinutes / 60.0, v / 1000.0);

    final load = points.map((p) => spot(p.consumptionMw, p.timestamp!)).whereType<FlSpot>().toList();
    final gen = points.map((p) => spot(p.generationMw, p.timestamp!)).whereType<FlSpot>().toList();
    if (load.isEmpty && gen.isEmpty) return const SizedBox.shrink();

    return _card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Verlauf (GW)',
              style: TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 15,
                  fontWeight: FontWeight.w600)),
          const SizedBox(height: 12),
          SizedBox(
            height: 150,
            child: LineChart(
              LineChartData(
                gridData: FlGridData(
                  show: true,
                  drawVerticalLine: false,
                  getDrawingHorizontalLine: (v) =>
                      const FlLine(color: AppColors.border, strokeWidth: 0.5),
                ),
                titlesData: FlTitlesData(
                  topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  leftTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 32,
                      getTitlesWidget: (v, _) => Text(v.toStringAsFixed(0),
                          style: const TextStyle(
                              color: AppColors.textMuted, fontSize: 10)),
                    ),
                  ),
                  bottomTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 20,
                      interval: 6,
                      getTitlesWidget: (v, _) => Text(
                        v >= -0.5 ? 'jetzt' : '${v.round()}h',
                        style: const TextStyle(color: AppColors.textMuted, fontSize: 10),
                      ),
                    ),
                  ),
                ),
                borderData: FlBorderData(show: false),
                lineBarsData: [
                  if (load.isNotEmpty)
                    LineChartBarData(
                      spots: load,
                      isCurved: true,
                      color: AppColors.drkRedLight,
                      barWidth: 2,
                      dotData: const FlDotData(show: false),
                    ),
                  if (gen.isNotEmpty)
                    LineChartBarData(
                      spots: gen,
                      isCurved: true,
                      color: AppColors.greenLight,
                      barWidth: 2,
                      dotData: const FlDotData(show: false),
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              _legend('Netzlast', AppColors.drkRedLight),
              const SizedBox(width: 16),
              _legend('Erzeugung', AppColors.greenLight),
            ],
          ),
        ],
      ),
    );
  }

  Widget _legend(String label, Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 10, height: 3, color: color),
        const SizedBox(width: 5),
        Text(label, style: const TextStyle(color: AppColors.textSecondary, fontSize: 11)),
      ],
    );
  }

  Widget _sourceNote(PowerRegionData r) {
    return Container(
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
              const Icon(Icons.info_outline, size: 14, color: AppColors.textMuted),
              const SizedBox(width: 6),
              Text(_detail!.source ?? 'SMARD / Bundesnetzagentur',
                  style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
              const Spacer(),
              if (r.timestamp != null)
                Text('Stand ${_time(r.timestamp!)}',
                    style: const TextStyle(color: AppColors.textDim, fontSize: 11)),
            ],
          ),
          const SizedBox(height: 6),
          const Text(
            'Netzstress wird nur bundesweit bewertet — eine einzelne Regelzone '
            'hat keine eigene Bilanz. Die Netzlast enthält keinen industriellen '
            'Eigenverbrauch, daher liegt die Erzeugung systematisch darüber.',
            style: TextStyle(color: AppColors.textDim, fontSize: 10, height: 1.4),
          ),
        ],
      ),
    );
  }

  String _time(String iso) {
    final dt = DateTime.tryParse(iso)?.toLocal();
    if (dt == null) return iso;
    return '${dt.day.toString().padLeft(2, '0')}.${dt.month.toString().padLeft(2, '0')}. '
        '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
  }
}
