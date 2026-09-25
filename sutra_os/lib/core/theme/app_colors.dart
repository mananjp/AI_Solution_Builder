import 'package:flutter/material.dart';

class AppColors {
  AppColors._();

  // ==========================================
  // MODE A — Landing / Marketing (Dark, Cinematic)
  // ==========================================
  static const Color darkBackground = Color(0xFF070A13); // Near-black navy
  static const Color darkSurface = Color(0xFF0D111C);
  static const Color darkSurfaceElevated = Color(0xFF131826);
  static const Color darkBorder = Color(0xFF1E2433); // Hairline slate border
  static const Color darkBorderMuted = Color(0x331E2433);
  static const Color darkTextPrimary = Color(0xFFFAF8F3);
  static const Color darkTextSecondary = Color(0xFF8B93A7);
  static const Color darkTextMuted = Color(0xFF5A6376);

  // ==========================================
  // MODE B — App Interior (Warm Cream Light Theme)
  // ==========================================
  static const Color lightBackground = Color(0xFFF7F5EF); // Warm off-white/cream
  static const Color lightSurface = Color(0xFFFFFFFF); // Pure white cards
  static const Color lightSurfaceSubtle = Color(0xFFF0EDE4); // Slightly deeper cream
  static const Color lightBorder = Color(0xFFE5E1D8); // 1px gray-beige border
  static const Color lightBorderSubtle = Color(0xFFEEEBE3);
  static const Color lightTextPrimary = Color(0xFF14171A); // Crisp editorial black
  static const Color lightTextSecondary = Color(0xFF78746D); // Muted warm gray
  static const Color lightTextMuted = Color(0xFFA09B92);

  // ==========================================
  // BRAND ACCENT — Warm Gold / Amber (#B8935A range)
  // ==========================================
  static const Color gold = Color(0xFFB8935A);
  static const Color goldLight = Color(0xFFC9A24B);
  static const Color goldLighter = Color(0xFFD4AF6A);
  static const Color goldDark = Color(0xFF9E7A43);
  static const Color goldSubtle = Color(0x1FB8935A); // Soft gold tint for active items
  static const Color goldBadgeBg = Color(0x26B8935A);

  // Solid Black / White Primary Buttons
  static const Color blackButton = Color(0xFF0A0C0E);
  static const Color blackButtonText = Color(0xFFFFFFFF);
  static const Color whiteButton = Color(0xFFFFFFFF);
  static const Color whiteButtonText = Color(0xFF0A0C0E);

  // Status Colors
  static const Color statusLiveGreen = Color(0xFF22C55E);
  static const Color statusLiveGreenBg = Color(0x2622C55E);
  static const Color statusErrorRed = Color(0xFFDC2626);
  static const Color statusErrorBg = Color(0x20DC2626);
  static const Color statusWarningAmber = Color(0xFFD97706);
  static const Color statusBlue = Color(0xFF2563EB);
  static const Color statusBlueBg = Color(0x202563EB);

  // Backward-compatibility & default aliases
  static const Color background = lightBackground;
  static const Color surface = lightSurface;
  static const Color surfaceElevated = lightSurface;
  static const Color surfaceSubtle = lightSurfaceSubtle;
  static const Color border = lightBorder;
  static const Color borderMuted = lightBorderSubtle;
  static const Color borderGold = gold;
  static const Color textPrimary = lightTextPrimary;
  static const Color textSecondary = lightTextSecondary;
  static const Color textMuted = lightTextMuted;
}
