import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import '../theme/app_text_styles.dart';

/// Shows an AlertDialog with a text input whose controller lifecycle is safely
/// managed inside the dialog widget's state, preventing "A TextEditingController
/// was used after being disposed" and subsequent InheritedElement assertion failures.
Future<String?> showPromptDialog({
  required BuildContext context,
  required String title,
  String initialValue = '',
  String? labelText,
  String? hintText,
  String confirmLabel = 'CONFIRM',
  String cancelLabel = 'CANCEL',
  int maxLines = 1,
  bool autofocus = true,
}) {
  return showDialog<String>(
    context: context,
    builder: (dialogCtx) => _PromptDialogWidget(
      title: title,
      initialValue: initialValue,
      labelText: labelText,
      hintText: hintText,
      confirmLabel: confirmLabel,
      cancelLabel: cancelLabel,
      maxLines: maxLines,
      autofocus: autofocus,
    ),
  );
}

class _PromptDialogWidget extends StatefulWidget {
  const _PromptDialogWidget({
    required this.title,
    required this.initialValue,
    this.labelText,
    this.hintText,
    required this.confirmLabel,
    required this.cancelLabel,
    required this.maxLines,
    required this.autofocus,
  });

  final String title;
  final String initialValue;
  final String? labelText;
  final String? hintText;
  final String confirmLabel;
  final String cancelLabel;
  final int maxLines;
  final bool autofocus;

  @override
  State<_PromptDialogWidget> createState() => _PromptDialogWidgetState();
}

class _PromptDialogWidgetState extends State<_PromptDialogWidget> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.initialValue);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      backgroundColor: AppColors.lightSurface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
        side: const BorderSide(color: AppColors.lightBorder),
      ),
      title: Text(
        widget.title,
        style: AppTextStyles.serifHeading(fontSize: 18),
      ),
      content: TextField(
        controller: _controller,
        autofocus: widget.autofocus,
        maxLines: widget.maxLines,
        decoration: InputDecoration(
          labelText: widget.labelText,
          hintText: widget.hintText,
          border: const OutlineInputBorder(),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(
            widget.cancelLabel,
            style: AppTextStyles.smallCapsLabel(
              color: AppColors.lightTextSecondary,
            ),
          ),
        ),
        TextButton(
          onPressed: () => Navigator.of(context).pop(_controller.text.trim()),
          child: Text(
            widget.confirmLabel,
            style: AppTextStyles.smallCapsLabel(
              color: AppColors.goldDark,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ],
    );
  }
}
