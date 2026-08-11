import 'dart:math';
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class RiskGauge extends StatelessWidget {
  final double score;
  final double size;

  const RiskGauge({super.key, required this.score, this.size = 200});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size * 0.65,
      child: CustomPaint(
        painter: _GaugePainter(score),
        child: Center(
          child: Padding(
            padding: EdgeInsets.only(top: size * 0.15),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  score.round().toString(),
                  style: TextStyle(
                    fontSize: size * 0.22,
                    fontWeight: FontWeight.bold,
                    color: scoreColor(score.round()),
                  ),
                ),
                Text(
                  scoreLabel(score.round()),
                  style: TextStyle(
                    fontSize: size * 0.08,
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _GaugePainter extends CustomPainter {
  final double score;
  _GaugePainter(this.score);

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height * 0.9);
    final radius = size.width * 0.42;
    const strokeWidth = 12.0;
    const startAngle = pi;
    const sweepAngle = pi;

    final bgPaint = Paint()
      ..color = AppColors.border
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      startAngle,
      sweepAngle,
      false,
      bgPaint,
    );

    final valueSweep = sweepAngle * (score / 100).clamp(0, 1);
    final valuePaint = Paint()
      ..color = scoreColor(score.round())
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      startAngle,
      valueSweep,
      false,
      valuePaint,
    );
  }

  @override
  bool shouldRepaint(covariant _GaugePainter old) => old.score != score;
}
