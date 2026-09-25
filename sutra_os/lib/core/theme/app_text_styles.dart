import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'app_colors.dart';

class AppTextStyles {
  AppTextStyles._();

  // Devanagari Brand Glyph "सूत्र"
  static TextStyle devanagariGlyph({
    double fontSize = 32,
    Color color = AppColors.gold,
    FontWeight fontWeight = FontWeight.w600,
  }) {
    return GoogleFonts.notoSerifDevanagari(
      fontSize: fontSize,
      color: color,
      fontWeight: fontWeight,
      height: 1.0,
    );
  }

  // Small-Caps Wide-Tracked Section / Category Label
  static TextStyle smallCapsLabel({
    double fontSize = 11,
    Color color = AppColors.lightTextSecondary,
    FontWeight fontWeight = FontWeight.w600,
    double letterSpacing = 2.4,
  }) {
    return GoogleFonts.inter(
      fontSize: fontSize,
      color: color,
      fontWeight: fontWeight,
      letterSpacing: letterSpacing,
      height: 1.2,
    );
  }

  // Large Editorial Serif Display (Headings) - elegant weight, not bold-heavy
  static TextStyle serifHeading({
    double fontSize = 28,
    Color color = AppColors.lightTextPrimary,
    FontWeight fontWeight = FontWeight.w500,
    FontStyle fontStyle = FontStyle.normal,
  }) {
    return GoogleFonts.playfairDisplay(
      fontSize: fontSize,
      fontWeight: fontWeight,
      fontStyle: fontStyle,
      color: color,
      letterSpacing: -0.3,
      height: 1.2,
    );
  }

  // Mode A Landing Large Hero Headline
  static TextStyle landingHero({
    double fontSize = 44,
    Color color = AppColors.darkTextPrimary,
    FontWeight fontWeight = FontWeight.w600,
    FontStyle fontStyle = FontStyle.normal,
  }) {
    return GoogleFonts.playfairDisplay(
      fontSize: fontSize,
      fontWeight: fontWeight,
      fontStyle: fontStyle,
      color: color,
      letterSpacing: -0.5,
      height: 1.1,
    );
  }

  // Stat Large Number
  static TextStyle statNumber({
    double fontSize = 36,
    Color color = AppColors.lightTextPrimary,
    FontWeight fontWeight = FontWeight.w500,
  }) {
    return GoogleFonts.playfairDisplay(
      fontSize: fontSize,
      fontWeight: fontWeight,
      color: color,
      height: 1.1,
    );
  }

  // Body Text (Inter)
  static TextStyle bodyLarge({
    double fontSize = 15,
    Color color = AppColors.lightTextPrimary,
    FontWeight fontWeight = FontWeight.w400,
  }) {
    return GoogleFonts.inter(
      fontSize: fontSize,
      color: color,
      fontWeight: fontWeight,
      height: 1.5,
    );
  }

  static TextStyle bodyMedium({
    double fontSize = 13,
    Color color = AppColors.lightTextSecondary,
    FontWeight fontWeight = FontWeight.w400,
  }) {
    return GoogleFonts.inter(
      fontSize: fontSize,
      color: color,
      fontWeight: fontWeight,
      height: 1.45,
    );
  }

  static TextStyle bodySmall({
    double fontSize = 12,
    Color color = AppColors.lightTextSecondary,
    FontWeight fontWeight = FontWeight.w400,
  }) {
    return GoogleFonts.inter(
      fontSize: fontSize,
      color: color,
      fontWeight: fontWeight,
      height: 1.4,
    );
  }

  // Button Labels (Inter)
  static TextStyle buttonLabel({
    double fontSize = 12,
    Color color = Colors.white,
    FontWeight fontWeight = FontWeight.w600,
    double letterSpacing = 1.4,
  }) {
    return GoogleFonts.inter(
      fontSize: fontSize,
      color: color,
      fontWeight: fontWeight,
      letterSpacing: letterSpacing,
    );
  }

  // Monospace (Code, Terminal, Masked Keys)
  static TextStyle mono({
    double fontSize = 12,
    Color color = AppColors.lightTextSecondary,
    FontWeight fontWeight = FontWeight.w400,
  }) {
    return GoogleFonts.jetBrainsMono(
      fontSize: fontSize,
      color: color,
      fontWeight: fontWeight,
      height: 1.45,
    );
  }

  // Compatibility aliases
  static TextStyle eyebrow({
    double fontSize = 10,
    Color color = AppColors.lightTextSecondary,
    FontWeight fontWeight = FontWeight.w600,
    double letterSpacing = 2.0,
  }) => smallCapsLabel(
        fontSize: fontSize,
        color: color,
        fontWeight: fontWeight,
        letterSpacing: letterSpacing,
      );

  static TextStyle displayTitle({
    double fontSize = 24,
    Color color = AppColors.lightTextPrimary,
    FontWeight fontWeight = FontWeight.w500,
  }) => serifHeading(
        fontSize: fontSize,
        color: color,
        fontWeight: fontWeight,
      );

  static TextStyle brandWordmark({
    double fontSize = 14,
    Color color = AppColors.lightTextPrimary,
    FontWeight fontWeight = FontWeight.w700,
    double letterSpacing = 3.0,
  }) => smallCapsLabel(
        fontSize: fontSize,
        color: color,
        fontWeight: fontWeight,
        letterSpacing: letterSpacing,
      );
}
