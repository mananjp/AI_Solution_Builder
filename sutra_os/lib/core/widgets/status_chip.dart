import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import '../theme/app_text_styles.dart';

class StatusChip extends StatelessWidget {
  final String label;
  final String statusText;
  final Color dotColor;
  final bool isDark;

  const StatusChip({
    super.key,
    this.label = 'INTELLIGENCE LAYER',
    this.statusText = 'ACTIVE',
    this.dotColor = AppColors.statusLiveGreen,
    this.isDark = false,
  });

  @override
  Widget build(BuildContext context) {
    final bg = isDark ? AppColors.darkSurface : AppColors.lightSurface;
    final border = isDark ? AppColors.darkBorder : AppColors.lightBorder;
    final textColor = isDark ? AppColors.darkTextSecondary : AppColors.lightTextSecondary;

    final isNarrow = MediaQuery.sizeOf(context).width <= 380;

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: isNarrow ? AppSpacing.sm : AppSpacing.md,
        vertical: AppSpacing.xs + 2,
      ),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
        border: Border.all(color: border, width: 1),
      ),
      child: FittedBox(
        fit: BoxFit.scaleDown,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (!isNarrow) ...[
              Text(
                label.toUpperCase(),
                style: AppTextStyles.smallCapsLabel(
                  fontSize: 9,
                  color: textColor,
                  letterSpacing: 1.2,
                ),
              ),
              const SizedBox(width: AppSpacing.xs),
              Text(
                '—',
                style: AppTextStyles.smallCapsLabel(
                  fontSize: 9,
                  color: textColor,
                ),
              ),
              const SizedBox(width: AppSpacing.xs),
            ],
            Container(
              width: 6,
              height: 6,
              decoration: BoxDecoration(
                color: dotColor,
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: dotColor.withValues(alpha: 0.6),
                    blurRadius: 4,
                    spreadRadius: 1,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 5),
            Text(
              statusText.toUpperCase(),
              style: AppTextStyles.smallCapsLabel(
                fontSize: 9,
                color: isDark ? AppColors.darkTextPrimary : AppColors.lightTextPrimary,
                fontWeight: FontWeight.w700,
                letterSpacing: 1.2,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
