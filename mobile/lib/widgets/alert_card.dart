import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../models/api_models.dart';

class AlertCard extends StatelessWidget {
  final AlertData alert;
  final VoidCallback? onAcknowledge;

  const AlertCard({super.key, required this.alert, this.onAcknowledge});

  IconData get _icon {
    switch (alert.category) {
      case 'hochwasser':
        return Icons.water;
      case 'wetter':
        return Icons.thunderstorm;
      case 'waldbrand':
        return Icons.local_fire_department;
      case 'luftqualitaet':
        return Icons.air;
      case 'verkehr':
        return Icons.traffic;
      default:
        return Icons.warning_amber;
    }
  }

  String get _timeAgo {
    if (alert.triggeredAt == null) return '';
    try {
      final dt = DateTime.parse(alert.triggeredAt!);
      final diff = DateTime.now().difference(dt);
      if (diff.inMinutes < 60) return 'vor ${diff.inMinutes} Min.';
      if (diff.inHours < 24) return 'vor ${diff.inHours} Std.';
      return 'vor ${diff.inDays} Tagen';
    } catch (_) {
      return '';
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = scoreColor(alert.score.round());
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: alert.acknowledged ? AppColors.border : color.withValues(alpha: 0.4),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(_icon, color: color, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  alert.title,
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  alert.score.round().toString(),
                  style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            alert.description,
            style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              if (alert.escalationLevel > 0) ...[
                Icon(Icons.priority_high, size: 14, color: AppColors.orange),
                Text(
                  'Stufe ${alert.escalationLevel}',
                  style: const TextStyle(color: AppColors.orange, fontSize: 11),
                ),
                const SizedBox(width: 12),
              ],
              Text(
                _timeAgo,
                style: const TextStyle(color: AppColors.textMuted, fontSize: 11),
              ),
              const Spacer(),
              if (!alert.acknowledged && onAcknowledge != null)
                GestureDetector(
                  onTap: onAcknowledge,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: AppColors.drkRed,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Text(
                      'Quittieren',
                      style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600),
                    ),
                  ),
                ),
              if (alert.acknowledged)
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.check_circle, size: 14, color: AppColors.green),
                    const SizedBox(width: 4),
                    const Text(
                      'Quittiert',
                      style: TextStyle(color: AppColors.green, fontSize: 11),
                    ),
                  ],
                ),
            ],
          ),
        ],
      ),
    );
  }
}
