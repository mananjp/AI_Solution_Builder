import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import '../theme/app_text_styles.dart';

class SutraWordmark extends StatelessWidget {
  final double glyphSize;
  final double wordmarkSize;
  final bool showTagline;
  final bool center;

  const SutraWordmark({
    super.key,
    this.glyphSize = 56,
    this.wordmarkSize = 13,
    this.showTagline = true,
    this.center = true,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment:
          center ? CrossAxisAlignment.center : CrossAxisAlignment.start,
      children: [
        // Devanagari Glyph
        Text(
          'सूत्र',
          style: AppTextStyles.devanagariGlyph(
            fontSize: glyphSize,
            color: AppColors.gold,
          ),
        ),
        const SizedBox(height: AppSpacing.xs),
        // Sutra OS Tracked Sans
        Text(
          'SUTRA OS',
          style: AppTextStyles.brandWordmark(
            fontSize: wordmarkSize,
            color: AppColors.textPrimary,
          ),
        ),
        if (showTagline) ...[
          const SizedBox(height: AppSpacing.sm),
          Row(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment:
                center ? MainAxisAlignment.center : MainAxisAlignment.start,
            children: [
              Container(
                width: 20,
                height: 1,
                color: AppColors.goldDark.withValues(alpha: 0.5),
              ),
              const SizedBox(width: AppSpacing.sm),
              Text(
                'Ancient precision. Modern intelligence.',
                style: AppTextStyles.eyebrow(
                  fontSize: 10,
                  color: AppColors.goldDark,
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Container(
                width: 20,
                height: 1,
                color: AppColors.goldDark.withValues(alpha: 0.5),
              ),
            ],
          ),
        ],
      ],
    );
  }
}
