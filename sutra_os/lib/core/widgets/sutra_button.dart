import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import '../theme/app_text_styles.dart';

enum SutraButtonVariant {
  primaryBlack, // Solid black background, white text, sharp corners (Mode B)
  secondaryOutline, // White bg, thin 1px border, black text (Mode B)
  outline, // Alias for secondaryOutline
  landingPill, // Solid black/white pill button with subtle glow (Mode A)
  goldAccent, // Gold button
  ghostText, // Plain text, muted, no border
}

class SutraButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final SutraButtonVariant variant;
  final bool isLoading;
  final Widget? icon;
  final double? width;
  final double height;

  const SutraButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.variant = SutraButtonVariant.primaryBlack,
    this.isLoading = false,
    this.icon,
    this.width,
    this.height = 44,
  });

  const SutraButton.outline({
    super.key,
    required this.label,
    required this.onPressed,
    this.isLoading = false,
    this.icon,
    this.width,
    this.height = 44,
  }) : variant = SutraButtonVariant.secondaryOutline;

  const SutraButton.landingPill({
    super.key,
    required this.label,
    required this.onPressed,
    this.isLoading = false,
    this.icon,
    this.width,
    this.height = 48,
  }) : variant = SutraButtonVariant.landingPill;

  const SutraButton.ghost({
    super.key,
    required this.label,
    required this.onPressed,
    this.isLoading = false,
    this.icon,
    this.width,
    this.height = 44,
  }) : variant = SutraButtonVariant.ghostText;

  @override
  Widget build(BuildContext context) {
    Color bg;
    BorderSide border = BorderSide.none;
    TextStyle textStyle;
    BorderRadius borderRadius;
    List<BoxShadow> shadows = [];

    switch (variant) {
      case SutraButtonVariant.primaryBlack:
        bg = onPressed != null ? AppColors.blackButton : AppColors.blackButton.withValues(alpha: 0.4);
        borderRadius = BorderRadius.circular(AppSpacing.radiusXs); // Sharp corners
        textStyle = AppTextStyles.buttonLabel(
          color: AppColors.blackButtonText,
          fontSize: 12,
          letterSpacing: 1.6,
        );
        break;

      case SutraButtonVariant.secondaryOutline:
      case SutraButtonVariant.outline:
        bg = AppColors.lightSurface;
        border = const BorderSide(color: AppColors.lightBorder, width: 1);
        borderRadius = BorderRadius.circular(AppSpacing.radiusXs);
        textStyle = AppTextStyles.buttonLabel(
          color: AppColors.lightTextPrimary,
          fontSize: 12,
          letterSpacing: 1.4,
        );
        break;

      case SutraButtonVariant.landingPill:
        bg = Colors.white;
        borderRadius = BorderRadius.circular(AppSpacing.radiusFull);
        textStyle = AppTextStyles.buttonLabel(
          color: AppColors.darkBackground,
          fontSize: 13,
          letterSpacing: 2.0,
          fontWeight: FontWeight.w700,
        );
        if (onPressed != null) {
          shadows = [
            BoxShadow(
              color: Colors.white.withValues(alpha: 0.25),
              blurRadius: 18,
              spreadRadius: 1,
            ),
          ];
        }
        break;

      case SutraButtonVariant.goldAccent:
        bg = AppColors.gold;
        borderRadius = BorderRadius.circular(AppSpacing.radiusXs);
        textStyle = AppTextStyles.buttonLabel(
          color: Colors.white,
          fontSize: 12,
          letterSpacing: 1.5,
        );
        break;

      case SutraButtonVariant.ghostText:
        bg = Colors.transparent;
        borderRadius = BorderRadius.zero;
        textStyle = AppTextStyles.buttonLabel(
          color: AppColors.darkTextSecondary,
          fontSize: 12,
          letterSpacing: 1.8,
        );
        break;
    }

    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: bg,
        borderRadius: borderRadius,
        border: border != BorderSide.none ? Border.fromBorderSide(border) : null,
        boxShadow: shadows,
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: borderRadius,
          onTap: isLoading ? null : onPressed,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
            child: Center(
              child: isLoading
                  ? SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: variant == SutraButtonVariant.landingPill
                            ? AppColors.darkBackground
                            : Colors.white,
                      ),
                    )
                  : FittedBox(
                      fit: BoxFit.scaleDown,
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          if (icon != null) ...[
                            icon!,
                            const SizedBox(width: AppSpacing.sm),
                          ],
                          Text(
                            label.toUpperCase(),
                            style: textStyle,
                            maxLines: 1,
                          ),
                        ],
                      ),
                    ),
            ),
          ),
        ),
      ),
    );
  }
}
