import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class ScoreBar extends StatelessWidget {
  final double score;
  final double height;

  const ScoreBar({super.key, required this.score, this.height = 6});

  @override
  Widget build(BuildContext context) {
    return Container(
      height: height,
      decoration: BoxDecoration(
        color: AppColors.border,
        borderRadius: BorderRadius.circular(height / 2),
      ),
      child: FractionallySizedBox(
        alignment: Alignment.centerLeft,
        widthFactor: (score / 100).clamp(0, 1),
        child: Container(
          decoration: BoxDecoration(
            color: scoreColor(score.round()),
            borderRadius: BorderRadius.circular(height / 2),
          ),
        ),
      ),
    );
  }
}
