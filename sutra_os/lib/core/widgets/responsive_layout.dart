import 'package:flutter/material.dart';

/// Clean responsive breakpoints for mobile (360dp baseline) through tablet/desktop
class ResponsiveLayout {
  static const double narrowPhoneBreakpoint = 380.0;
  static const double tabletBreakpoint = 600.0;
  static const double desktopBreakpoint = 1024.0;

  static bool isNarrow(BuildContext context) {
    return MediaQuery.sizeOf(context).width <= narrowPhoneBreakpoint;
  }

  static bool isTablet(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    return width > tabletBreakpoint && width <= desktopBreakpoint;
  }

  static bool isDesktop(BuildContext context) {
    return MediaQuery.sizeOf(context).width > desktopBreakpoint;
  }

  /// Calculates responsive horizontal padding (e.g. 12 on narrow 360dp, 16 on standard, 24 on desktop)
  static double horizontalPadding(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    if (width <= narrowPhoneBreakpoint) return 12.0;
    if (width <= tabletBreakpoint) return 16.0;
    return 24.0;
  }
}
