import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';

class SutraCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry? padding;
  final VoidCallback? onTap;
  final bool isHighlighted;
  final bool isDark;
  final Color? backgroundColor;
  final Color? borderColor;
  final BorderSide? borderSide;

  const SutraCard({
    super.key,
    required this.child,
    this.padding,
    this.onTap,
    this.isHighlighted = false,
    this.isDark = false,
    this.backgroundColor,
    this.borderColor,
    this.borderSide,
  });

  @override
  Widget build(BuildContext context) {
    final bg = backgroundColor ??
        (isDark ? AppColors.darkSurface : AppColors.lightSurface);

    final resolvedBorderColor = borderColor ??
        (isHighlighted
            ? AppColors.gold
            : (isDark ? AppColors.darkBorder : AppColors.lightBorder));

    final effectiveBorder = borderSide ??
        BorderSide(
          color: resolvedBorderColor,
          width: isHighlighted ? 1.5 : 1.0,
        );

    final cardWidget = Container(
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(AppSpacing.radiusXs), // Sharp/minimal corners
        border: Border.fromBorderSide(effectiveBorder),
      ),
      padding: padding ?? const EdgeInsets.all(AppSpacing.lg),
      child: child,
    );

    if (onTap != null) {
      return Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
          onTap: onTap,
          child: cardWidget,
        ),
      );
    }

    return cardWidget;
  }
}
