import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import '../theme/app_text_styles.dart';

class MaskedSecretField extends StatefulWidget {
  final String label;
  final TextEditingController controller;
  final String hintText;
  final String? prefixText;
  final ValueChanged<String>? onChanged;

  const MaskedSecretField({
    super.key,
    required this.label,
    required this.controller,
    required this.hintText,
    this.prefixText,
    this.onChanged,
  });

  @override
  State<MaskedSecretField> createState() => _MaskedSecretFieldState();
}

class _MaskedSecretFieldState extends State<MaskedSecretField> {
  bool _isObscured = true;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          widget.label.toUpperCase(),
          style: AppTextStyles.smallCapsLabel(
            fontSize: 10,
            color: AppColors.lightTextSecondary,
            letterSpacing: 2.0,
          ),
        ),
        const SizedBox(height: AppSpacing.xs),
        Container(
          decoration: BoxDecoration(
            color: AppColors.lightSurface,
            borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
            border: Border.all(color: AppColors.lightBorder, width: 1),
          ),
          child: TextFormField(
            controller: widget.controller,
            obscureText: _isObscured,
            onChanged: widget.onChanged,
            style: AppTextStyles.mono(
              fontSize: 13,
              color: AppColors.lightTextPrimary,
            ),
            decoration: InputDecoration(
              hintText: widget.hintText,
              hintStyle: AppTextStyles.mono(
                fontSize: 13,
                color: AppColors.lightTextMuted,
              ),
              border: InputBorder.none,
              enabledBorder: InputBorder.none,
              focusedBorder: InputBorder.none,
              contentPadding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.md,
                vertical: AppSpacing.md,
              ),
              prefixIcon: const Icon(
                Icons.lock_outline,
                size: 16,
                color: AppColors.lightTextSecondary,
              ),
              suffixIcon: IconButton(
                icon: Icon(
                  _isObscured ? Icons.visibility_off_outlined : Icons.visibility_outlined,
                  size: 16,
                  color: AppColors.lightTextSecondary,
                ),
                onPressed: () {
                  setState(() {
                    _isObscured = !_isObscured;
                  });
                },
              ),
            ),
          ),
        ),
      ],
    );
  }
}
