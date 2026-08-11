import 'package:flutter/material.dart';

class AppColors {
  static const background = Color(0xFF121212);
  static const surface = Color(0xFF1E1E1E);
  static const surfaceLight = Color(0xFF252525);
  static const border = Color(0xFF333333);
  static const borderLight = Color(0xFF4F4F4F);

  static const drkRed = Color(0xFFCC1A1A);
  static const drkRedLight = Color(0xFFE81E1E);
  static const drkRedAccent = Color(0xFFFF6B6B);

  static const textPrimary = Color(0xFFE7E7E7);
  static const textSecondary = Color(0xFFB0B0B0);
  static const textMuted = Color(0xFF888888);
  static const textDim = Color(0xFF6D6D6D);

  static const green = Color(0xFF22C55E);
  static const greenLight = Color(0xFF4ADE80);
  static const yellow = Color(0xFFEAB308);
  static const yellowLight = Color(0xFFFACC15);
  static const orange = Color(0xFFF97316);
  static const orangeLight = Color(0xFFFB923C);
  static const red = Color(0xFFEF4444);
  static const redLight = Color(0xFFF87171);
  static const purple = Color(0xFFA855F7);
  static const purpleLight = Color(0xFFC084FC);
}

Color scoreColor(int score) {
  if (score < 20) return AppColors.green;
  if (score < 40) return AppColors.yellow;
  if (score < 60) return AppColors.orange;
  if (score < 80) return AppColors.red;
  return AppColors.purple;
}

String scoreLabel(int score) {
  if (score < 20) return 'Normal';
  if (score < 40) return 'Erhöht';
  if (score < 60) return 'Hoch';
  if (score < 80) return 'Sehr hoch';
  return 'Extrem';
}

ThemeData appTheme() {
  return ThemeData(
    brightness: Brightness.dark,
    scaffoldBackgroundColor: AppColors.background,
    colorScheme: const ColorScheme.dark(
      primary: AppColors.drkRed,
      surface: AppColors.surface,
      onSurface: AppColors.textPrimary,
    ),
    cardTheme: CardThemeData(
      color: AppColors.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: AppColors.border),
      ),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.surface,
      foregroundColor: AppColors.textPrimary,
      elevation: 0,
    ),
    fontFamily: 'Roboto',
  );
}
