import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../models/api_models.dart';
import '../services/app_state.dart';
import 'lagebild_screen.dart' show waterLevelColor;

/// Interaktive Lagekarte: Pegelstationen und Verkehrsereignisse
/// rund um Troisdorf auf OpenStreetMap.
class LagekarteScreen extends StatefulWidget {
  const LagekarteScreen({super.key});

  @override
  State<LagekarteScreen> createState() => _LagekarteScreenState();
}

class _LagekarteScreenState extends State<LagekarteScreen> {
  static const _troisdorf = LatLng(50.8161, 7.1425);

  bool _showWater = true;
  bool _showTraffic = true;

  @override
  Widget build(BuildContext context) {
    return Consumer<AppState>(
      builder: (context, state, _) {
        final markers = <Marker>[
          // DRK Troisdorf als Referenzpunkt
          Marker(
            point: _troisdorf,
            width: 36,
            height: 36,
            child: Container(
              decoration: BoxDecoration(
                color: AppColors.drkRed,
                shape: BoxShape.circle,
                border: Border.all(color: Colors.white, width: 2),
                boxShadow: const [BoxShadow(color: Colors.black45, blurRadius: 6)],
              ),
              child: const Center(
                child: Text('DRK',
                    style: TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.w800)),
              ),
            ),
          ),
          if (_showWater)
            ...state.waterStations
                .where((s) => s.lat != null && s.lon != null)
                .map((s) => _waterMarker(context, s)),
          if (_showTraffic)
            ...state.trafficEvents
                .where((e) => _lat(e) != null && _lon(e) != null)
                .map((e) => _trafficMarker(context, e)),
        ];

        return Stack(
          children: [
            FlutterMap(
              options: const MapOptions(
                initialCenter: _troisdorf,
                initialZoom: 11,
                minZoom: 8,
                maxZoom: 18,
              ),
              children: [
                TileLayer(
                  urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  userAgentPackageName: 'de.drk.troisdorf.fruewarnsystem',
                ),
                MarkerLayer(markers: markers),
                const SimpleAttributionWidget(
                  source: Text('© OpenStreetMap'),
                  backgroundColor: Colors.black54,
                ),
              ],
            ),
            Positioned(
              top: 12,
              left: 12,
              right: 12,
              child: Row(
                children: [
                  _filterChip('Pegel', Icons.water, _showWater,
                      (v) => setState(() => _showWater = v)),
                  const SizedBox(width: 8),
                  _filterChip('Verkehr', Icons.traffic, _showTraffic,
                      (v) => setState(() => _showTraffic = v)),
                ],
              ),
            ),
          ],
        );
      },
    );
  }

  double? _lat(TrafficEventData e) => e.lat;
  double? _lon(TrafficEventData e) => e.lon;

  Widget _filterChip(String label, IconData icon, bool active, ValueChanged<bool> onChanged) {
    return GestureDetector(
      onTap: () => onChanged(!active),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        decoration: BoxDecoration(
          color: active ? AppColors.drkRed : AppColors.surface.withValues(alpha: 0.92),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: active ? AppColors.drkRed : AppColors.border),
          boxShadow: const [BoxShadow(color: Colors.black26, blurRadius: 4)],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 15, color: active ? Colors.white : AppColors.textSecondary),
            const SizedBox(width: 5),
            Text(label,
                style: TextStyle(
                  color: active ? Colors.white : AppColors.textSecondary,
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                )),
          ],
        ),
      ),
    );
  }

  Marker _waterMarker(BuildContext context, WaterStation s) {
    final color = waterLevelColor(s.warningLevel);
    return Marker(
      point: LatLng(s.lat!, s.lon!),
      width: 30,
      height: 30,
      child: GestureDetector(
        onTap: () => _showStationSheet(context, s),
        child: Container(
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
            border: Border.all(color: Colors.white, width: 2),
            boxShadow: const [BoxShadow(color: Colors.black45, blurRadius: 4)],
          ),
          child: const Icon(Icons.water, size: 15, color: Colors.white),
        ),
      ),
    );
  }

  Marker _trafficMarker(BuildContext context, TrafficEventData e) {
    final color = e.severity >= 50 ? AppColors.red : AppColors.yellow;
    return Marker(
      point: LatLng(e.lat!, e.lon!),
      width: 28,
      height: 28,
      child: GestureDetector(
        onTap: () => _showTrafficSheet(context, e),
        child: Container(
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
            border: Border.all(color: Colors.white, width: 2),
            boxShadow: const [BoxShadow(color: Colors.black45, blurRadius: 4)],
          ),
          child: Icon(
            e.eventType == 'accident' ? Icons.car_crash : Icons.traffic,
            size: 14,
            color: Colors.white,
          ),
        ),
      ),
    );
  }

  void _showStationSheet(BuildContext context, WaterStation s) {
    _showSheet(
      context,
      icon: Icons.water,
      iconColor: waterLevelColor(s.warningLevel),
      title: s.stationName,
      subtitle: s.river,
      rows: [
        ('Pegelstand', s.currentLevel != null ? '${s.currentLevel!.toStringAsFixed(0)} cm' : '–'),
        ('Zustand', s.condition),
        ('Trend', s.trend == 'rising' ? 'Steigend' : s.trend == 'falling' ? 'Fallend' : 'Stabil'),
      ],
    );
  }

  void _showTrafficSheet(BuildContext context, TrafficEventData e) {
    _showSheet(
      context,
      icon: e.eventType == 'accident' ? Icons.car_crash : Icons.traffic,
      iconColor: e.severity >= 50 ? AppColors.red : AppColors.yellow,
      title: e.title,
      subtitle: '${e.road} · ${e.source}',
      rows: [
        ('Typ', e.eventType),
        ('Schweregrad', '${e.severity}'),
        if (e.description.isNotEmpty) ('Details', e.description),
      ],
    );
  }

  void _showSheet(
    BuildContext context, {
    required IconData icon,
    required Color iconColor,
    required String title,
    required String subtitle,
    required List<(String, String)> rows,
  }) {
    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 40, height: 40,
                  decoration: BoxDecoration(
                    color: iconColor.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(icon, color: iconColor, size: 20),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title,
                          style: const TextStyle(
                              color: AppColors.textPrimary, fontSize: 16, fontWeight: FontWeight.w600),
                          maxLines: 2, overflow: TextOverflow.ellipsis),
                      Text(subtitle,
                          style: const TextStyle(color: AppColors.textMuted, fontSize: 12)),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            ...rows.map((r) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    width: 110,
                    child: Text(r.$1,
                        style: const TextStyle(color: AppColors.textMuted, fontSize: 13)),
                  ),
                  Expanded(
                    child: Text(r.$2,
                        style: const TextStyle(color: AppColors.textPrimary, fontSize: 13)),
                  ),
                ],
              ),
            )),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}
