import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme/app_colors.dart';

class CinematicBackground extends StatelessWidget {
  final Widget child;

  const CinematicBackground({
    super.key,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        // Solid base background
        Positioned.fill(
          child: Container(
            color: AppColors.darkBackground,
          ),
        ),

        // Radial gold ambient glow
        Positioned.fill(
          child: Container(
            decoration: BoxDecoration(
              gradient: RadialGradient(
                center: const Alignment(0, -0.2),
                radius: 1.1,
                colors: [
                  AppColors.goldDark.withValues(alpha: 0.12),
                  AppColors.darkBackground.withValues(alpha: 0.8),
                  AppColors.darkBackground,
                ],
                stops: const [0.0, 0.6, 1.0],
              ),
            ),
          ),
        ),

        // Subtle geometric lines
        Positioned.fill(
          child: CustomPaint(
            painter: _SutraGeometryPainter(),
          ),
        ),

        // Content
        Positioned.fill(
          child: child,
        ),
      ],
    );
  }
}

class _SutraGeometryPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final goldPaint = Paint()
      ..color = AppColors.goldDark.withValues(alpha: 0.12)
      ..strokeWidth = 1.0
      ..style = PaintingStyle.stroke;

    final faintPaint = Paint()
      ..color = AppColors.darkTextPrimary.withValues(alpha: 0.03)
      ..strokeWidth = 1.0
      ..style = PaintingStyle.stroke;

    final center = Offset(size.width / 2, size.height * 0.38);

    // Subtle concentric orbits
    canvas.drawCircle(center, size.width * 0.45, faintPaint);
    canvas.drawCircle(center, size.width * 0.65, faintPaint);

    // Subtle central axis
    canvas.drawLine(
      Offset(center.dx, 40),
      Offset(center.dx, size.height - 80),
      goldPaint,
    );

    // Subtle diamond accent along axis
    final path = Path()
      ..moveTo(center.dx, 100)
      ..lineTo(center.dx + 8, 115)
      ..lineTo(center.dx, 130)
      ..lineTo(center.dx - 8, 115)
      ..close();
    canvas.drawPath(path, goldPaint);

    // Subtle 45-deg angled tick marks
    final crossPaint = Paint()
      ..color = AppColors.goldDark.withValues(alpha: 0.08)
      ..strokeWidth = 0.8
      ..style = PaintingStyle.stroke;

    final radius = size.width * 0.35;
    for (int i = 0; i < 8; i++) {
      final angle = (i * math.pi / 4);
      final p1 = Offset(
        center.dx + radius * math.cos(angle),
        center.dy + radius * math.sin(angle),
      );
      final p2 = Offset(
        center.dx + (radius + 12) * math.cos(angle),
        center.dy + (radius + 12) * math.sin(angle),
      );
      canvas.drawLine(p1, p2, crossPaint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
