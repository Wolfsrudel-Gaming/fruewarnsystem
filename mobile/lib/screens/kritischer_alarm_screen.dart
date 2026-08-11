import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../theme/app_theme.dart';
import '../models/api_models.dart';

class KritischerAlarmScreen extends StatefulWidget {
  final AlertData alert;
  final VoidCallback? onAcknowledge;

  const KritischerAlarmScreen({super.key, required this.alert, this.onAcknowledge});

  @override
  State<KritischerAlarmScreen> createState() => _KritischerAlarmScreenState();
}

class _KritischerAlarmScreenState extends State<KritischerAlarmScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
    HapticFeedback.heavyImpact();
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: AnimatedBuilder(
        animation: _pulseController,
        builder: (context, child) {
          final pulse = _pulseController.value * 0.3;
          return Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Color.lerp(const Color(0xFF3D0000), const Color(0xFF5A0000), pulse)!,
                  Color.lerp(const Color(0xFF1A0000), const Color(0xFF2D0000), pulse)!,
                ],
              ),
            ),
            child: child,
          );
        },
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Spacer(flex: 2),
                Container(
                  width: 100,
                  height: 100,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: AppColors.drkRed.withValues(alpha: 0.3),
                  ),
                  child: const Icon(
                    Icons.warning_rounded,
                    size: 56,
                    color: AppColors.drkRedAccent,
                  ),
                ),
                const SizedBox(height: 24),
                Text(
                  'KRITISCHER ALARM',
                  style: TextStyle(
                    color: AppColors.drkRedAccent,
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 2,
                  ),
                ),
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                  decoration: BoxDecoration(
                    color: AppColors.drkRed.withValues(alpha: 0.3),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    'Score: ${widget.alert.score.round()}',
                    style: const TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.bold),
                  ),
                ),
                const SizedBox(height: 24),
                Text(
                  widget.alert.title,
                  style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w600),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 12),
                Text(
                  widget.alert.description,
                  style: TextStyle(color: Colors.white.withValues(alpha: 0.8), fontSize: 15, height: 1.5),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                if (widget.alert.escalationLevel > 0)
                  Text(
                    'Eskalationsstufe ${widget.alert.escalationLevel}',
                    style: TextStyle(color: AppColors.orange, fontSize: 14, fontWeight: FontWeight.w500),
                  ),
                const Spacer(flex: 3),
                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: ElevatedButton(
                    onPressed: () {
                      widget.onAcknowledge?.call();
                      Navigator.of(context).pop();
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.drkRed,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                    ),
                    child: const Text(
                      'Quittieren',
                      style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w700),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text(
                    'Zum Lagebild',
                    style: TextStyle(color: AppColors.textSecondary, fontSize: 14),
                  ),
                ),
                const Spacer(),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
