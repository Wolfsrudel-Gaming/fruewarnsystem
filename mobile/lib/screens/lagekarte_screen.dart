import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class LagekarteScreen extends StatelessWidget {
  const LagekarteScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppColors.background,
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.map_outlined, size: 64, color: AppColors.textMuted),
            const SizedBox(height: 16),
            const Text(
              'Lagekarte',
              style: TextStyle(color: AppColors.textPrimary, fontSize: 18, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 40),
              child: Text(
                'Die interaktive Karte mit Warnungen, Pegelständen, Radar und Hotspots wird in einer kommenden Version verfügbar sein.',
                style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
                textAlign: TextAlign.center,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
