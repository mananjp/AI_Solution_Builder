import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import '../theme/app_text_styles.dart';

class StatusPill extends StatefulWidget {
  final String label;
  final Color dotColor;
  final Color? backgroundColor;
  final bool animatePulse;

  const StatusPill({
    super.key,
    this.label = 'LIVE SYNC',
    this.dotColor = AppColors.statusLiveGreen,
    this.backgroundColor,
    this.animatePulse = true,
  });

  @override
  State<StatusPill> createState() => _StatusPillState();
}

class _StatusPillState extends State<StatusPill>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _scaleAnimation;
  late Animation<double> _opacityAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1600),
    );

    if (widget.animatePulse) {
      _controller.repeat();
    }

    _scaleAnimation = Tween<double>(begin: 1.0, end: 2.2).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeOut),
    );
    _opacityAnimation = Tween<double>(begin: 0.7, end: 0.0).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeOut),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bg = widget.backgroundColor ?? widget.dotColor.withValues(alpha: 0.12);
    final border = widget.dotColor.withValues(alpha: 0.3);

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm + 2,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
        border: Border.all(color: border, width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Glowing pulsing dot
          SizedBox(
            width: 10,
            height: 10,
            child: Stack(
              alignment: Alignment.center,
              children: [
                if (widget.animatePulse)
                  AnimatedBuilder(
                    animation: _controller,
                    builder: (context, child) {
                      return Transform.scale(
                        scale: _scaleAnimation.value,
                        child: Container(
                          width: 6,
                          height: 6,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: widget.dotColor.withValues(alpha: _opacityAnimation.value),
                          ),
                        ),
                      );
                    },
                  ),
                Container(
                  width: 6,
                  height: 6,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: widget.dotColor,
                    boxShadow: [
                      BoxShadow(
                        color: widget.dotColor.withValues(alpha: 0.8),
                        blurRadius: 6,
                        spreadRadius: 1,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: AppSpacing.xs + 2),
          Text(
            widget.label.toUpperCase(),
            style: AppTextStyles.mono(
              fontSize: 10,
              color: widget.dotColor,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
