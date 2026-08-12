import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../services/app_state.dart';
import 'verlauf_screen.dart';
import 'eskalation_screen.dart';
import 'einstellungen_screen.dart';
import 'schwellenwerte_screen.dart';
import 'warnungen_screen.dart';
import 'news_screen.dart';

class MehrScreen extends StatelessWidget {
  const MehrScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final api = context.read<AppState>().api;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const SizedBox(height: 8),
        _menuItem(
          context,
          icon: Icons.campaign,
          label: 'Behördliche Warnungen',
          subtitle: 'NINA, Katwarn, MoWaS, GDACS',
          onTap: () => Navigator.push(context, MaterialPageRoute(
            builder: (_) => const WarnungenScreen(),
          )),
        ),
        _menuItem(
          context,
          icon: Icons.newspaper,
          label: 'Nachrichten',
          subtitle: 'Relevante Lokalmeldungen mit KI-Bewertung',
          onTap: () => Navigator.push(context, MaterialPageRoute(
            builder: (_) => const NewsScreen(),
          )),
        ),
        _menuItem(
          context,
          icon: Icons.timeline,
          label: 'Verlauf',
          subtitle: 'Risikoscore-Entwicklung',
          onTap: () => Navigator.push(context, MaterialPageRoute(
            builder: (_) => VerlaufScreen(api: api),
          )),
        ),
        _menuItem(
          context,
          icon: Icons.notifications_active,
          label: 'Eskalation & Push',
          subtitle: 'Eskalationspfad und Verlauf',
          onTap: () => Navigator.push(context, MaterialPageRoute(
            builder: (_) => const EskalationScreen(),
          )),
        ),
        _menuItem(
          context,
          icon: Icons.tune,
          label: 'Schwellenwerte',
          subtitle: 'Alarm-Schwellenwerte konfigurieren',
          onTap: () => Navigator.push(context, MaterialPageRoute(
            builder: (_) => const SchwellenwerteScreen(),
          )),
        ),
        _menuItem(
          context,
          icon: Icons.settings,
          label: 'Einstellungen',
          subtitle: 'Server, Benachrichtigungen, System',
          onTap: () => Navigator.push(context, MaterialPageRoute(
            builder: (_) => EinstellungenScreen(api: api),
          )),
        ),
        const SizedBox(height: 24),
        Center(
          child: Column(
            children: [
              Text(
                'DRK Troisdorf',
                style: TextStyle(color: AppColors.drkRedLight, fontSize: 14, fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 4),
              Text(
                'Frühwarnsystem v1.0.0',
                style: TextStyle(color: AppColors.textDim, fontSize: 12),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _menuItem(
    BuildContext context, {
    required IconData icon,
    required String label,
    required String subtitle,
    required VoidCallback onTap,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      child: Material(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(14),
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppColors.border),
            ),
            child: Row(
              children: [
                Container(
                  width: 40, height: 40,
                  decoration: BoxDecoration(
                    color: AppColors.drkRed.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(icon, size: 20, color: AppColors.drkRedLight),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(label, style: const TextStyle(color: AppColors.textPrimary, fontSize: 15, fontWeight: FontWeight.w500)),
                      Text(subtitle, style: const TextStyle(color: AppColors.textMuted, fontSize: 12)),
                    ],
                  ),
                ),
                const Icon(Icons.chevron_right, color: AppColors.textMuted, size: 20),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
