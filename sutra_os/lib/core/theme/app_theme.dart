import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'app_colors.dart';
import 'app_spacing.dart';
import 'app_text_styles.dart';

class AppTheme {
  AppTheme._();

  // Mode B: Interior Light Theme (Warm Cream #F7F5EF, White Cards #FFFFFF, 1px #E5E1D8)
  static ThemeData get lightTheme => lightInteriorTheme;
  static ThemeData get darkTheme => darkLandingTheme;

  static ThemeData get lightInteriorTheme {
    final base = ThemeData.light(useMaterial3: true);

    return base.copyWith(
      scaffoldBackgroundColor: AppColors.lightBackground,
      colorScheme: const ColorScheme.light(
        primary: AppColors.blackButton,
        onPrimary: AppColors.blackButtonText,
        secondary: AppColors.gold,
        onSecondary: Colors.white,
        surface: AppColors.lightSurface,
        onSurface: AppColors.lightTextPrimary,
        error: AppColors.statusErrorRed,
        onError: Colors.white,
        outline: AppColors.lightBorder,
      ),
      textTheme: GoogleFonts.interTextTheme(base.textTheme).copyWith(
        displayLarge: AppTextStyles.serifHeading(fontSize: 32),
        displayMedium: AppTextStyles.serifHeading(fontSize: 26),
        titleLarge: AppTextStyles.serifHeading(fontSize: 20),
        bodyLarge: AppTextStyles.bodyLarge(),
        bodyMedium: AppTextStyles.bodyMedium(),
        bodySmall: AppTextStyles.bodySmall(),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.lightBackground,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        iconTheme: IconThemeData(color: AppColors.lightTextPrimary),
      ),
      cardTheme: CardThemeData(
        color: AppColors.lightSurface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
          side: const BorderSide(color: AppColors.lightBorder, width: 1),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.lightSurface,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.md,
        ),
        hintStyle: AppTextStyles.bodySmall(color: AppColors.lightTextMuted),
        labelStyle: AppTextStyles.bodySmall(color: AppColors.lightTextSecondary),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
          borderSide: const BorderSide(color: AppColors.lightBorder, width: 1),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
          borderSide: const BorderSide(color: AppColors.blackButton, width: 1.5),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
          borderSide: const BorderSide(color: AppColors.statusErrorRed, width: 1),
        ),
      ),
      dividerTheme: const DividerThemeData(
        color: AppColors.lightBorder,
        thickness: 1,
        space: 1,
      ),
    );
  }

  // Mode A: Landing / Marketing Dark Theme (#070A13, Near-Black Navy)
  static ThemeData get darkLandingTheme {
    final base = ThemeData.dark(useMaterial3: true);

    return base.copyWith(
      scaffoldBackgroundColor: AppColors.darkBackground,
      colorScheme: const ColorScheme.dark(
        primary: AppColors.gold,
        onPrimary: AppColors.darkBackground,
        secondary: AppColors.goldLight,
        surface: AppColors.darkSurface,
        onSurface: AppColors.darkTextPrimary,
        outline: AppColors.darkBorder,
      ),
      textTheme: GoogleFonts.interTextTheme(base.textTheme),
    );
  }
}
