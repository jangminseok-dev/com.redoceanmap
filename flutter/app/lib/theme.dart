// www/app/globals.css의 디자인 토큰을 그대로 옮긴 것. 값이 갈리면 www가 정본이다.

import 'package:flutter/material.dart';

class AppColors {
  const AppColors._();

  static const background = Color(0xFFFDFAF2);
  static const surface = Color(0xFFFFFFFF);
  static const foreground = Color(0xFF1A1A1A);
  static const foregroundMuted = Color(0xFF6B7280);
  static const border = Color(0xFFEBE8DF);
  static const brand = Color(0xFF991B1B);
  static const brandDeep = Color(0xFF7A1515);
}

/// www의 `rounded-xl`(12) · `rounded-lg`(8) · `rounded-full`
class AppRadius {
  const AppRadius._();

  static const card = 12.0;
  static const icon = 8.0;
}

ThemeData buildAppTheme() {
  const textColor = AppColors.foreground;

  return ThemeData(
    fontFamily: 'Pretendard',
    scaffoldBackgroundColor: AppColors.background,
    colorScheme: const ColorScheme.light(
      primary: AppColors.brand,
      surface: AppColors.surface,
      onSurface: AppColors.foreground,
    ),
    dividerColor: AppColors.border,
    textTheme: const TextTheme(
      // 홈 헤드라인 — www의 text-4xl/semibold/tracking-tight
      displaySmall: TextStyle(
        fontSize: 32,
        height: 1.35,
        fontWeight: FontWeight.w600,
        letterSpacing: -0.6,
        color: textColor,
      ),
      titleMedium: TextStyle(
        fontSize: 15,
        fontWeight: FontWeight.w600,
        color: textColor,
      ),
      bodyMedium: TextStyle(fontSize: 14, color: textColor),
      // www의 text-sm text-foreground-muted
      bodySmall: TextStyle(fontSize: 13, color: AppColors.foregroundMuted),
    ),
  );
}

/// www의 `bg-surface border border-border rounded-xl` 카드
BoxDecoration get cardDecoration => BoxDecoration(
      color: AppColors.surface,
      border: Border.all(color: AppColors.border),
      borderRadius: BorderRadius.circular(AppRadius.card),
    );
