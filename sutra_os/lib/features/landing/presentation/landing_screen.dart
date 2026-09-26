import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../core/network/json_utils.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/widgets/cinematic_background.dart';
import '../../../core/widgets/responsive_layout.dart';
import '../../../core/widgets/status_chip.dart';
import '../../../core/widgets/sutra_button.dart';
import '../../../core/widgets/sutra_card.dart';
import '../../auth/presentation/auth_controller.dart';

/// Liveness probe for the marketing page.
///
/// This used to swallow every failure and return a `warming_up` payload, so the
/// provider never entered its `error:` branch and the UI always rendered a hard
/// "ONLINE" chip no matter what the backend was doing. Failures now propagate.
final backendHealthProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final client = ref.watch(apiClientProvider);
  final res = await client.get(ApiEndpoints.health);
  return asMap(res.data);
});

class LandingScreen extends ConsumerWidget {
  const LandingScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authControllerProvider);
    final healthAsync = ref.watch(backendHealthProvider);

    return Scaffold(
      backgroundColor: AppColors.darkBackground,
      body: CinematicBackground(
        child: SafeArea(
          child: CustomScrollView(
            physics: const BouncingScrollPhysics(),
            slivers: [
              // Top Nav Bar
              SliverToBoxAdapter(
                child: Padding(
                  padding: EdgeInsets.symmetric(
                    horizontal: ResponsiveLayout.horizontalPadding(context),
                    vertical: AppSpacing.md,
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      // Top Left: "सूत्र" wordmark in gold serif
                      Flexible(
                        child: FittedBox(
                          fit: BoxFit.scaleDown,
                          alignment: Alignment.centerLeft,
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(
                                'सूत्र',
                                style: AppTextStyles.devanagariGlyph(
                                  fontSize: 28,
                                  color: AppColors.gold,
                                ),
                              ),
                              const SizedBox(width: AppSpacing.xs),
                              Text(
                                'SUTRA OS',
                                style: AppTextStyles.smallCapsLabel(
                                  fontSize: 11,
                                  color: AppColors.darkTextPrimary,
                                  letterSpacing: 2.5,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(width: AppSpacing.sm),

                      // Top Right: "SIGN IN" plain text + "WORKSPACE →" solid black button
                      FittedBox(
                        fit: BoxFit.scaleDown,
                        alignment: Alignment.centerRight,
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            if (authState.isAuthenticated) ...[
                              Text(
                                authState.user?.roleDisplayName ?? 'ACTIVE',
                                style: AppTextStyles.smallCapsLabel(
                                  fontSize: 10,
                                  color: AppColors.gold,
                                ),
                              ),
                              const SizedBox(width: AppSpacing.sm),
                              SutraButton(
                                label: 'WORKSPACE →',
                                height: 36,
                                variant: SutraButtonVariant.primaryBlack,
                                onPressed: () => context.go('/dashboard'),
                              ),
                            ] else ...[
                              GestureDetector(
                                onTap: () => context.go('/login'),
                                child: Text(
                                  'SIGN IN',
                                  style: AppTextStyles.smallCapsLabel(
                                    fontSize: 10,
                                    color: AppColors.darkTextSecondary,
                                    letterSpacing: 1.8,
                                  ),
                                ),
                              ),
                              const SizedBox(width: AppSpacing.sm),
                              Container(
                                decoration: BoxDecoration(
                                  color: const Color(0xFF0D111C),
                                  borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                                  border: Border.all(color: AppColors.darkBorder),
                                ),
                                child: Material(
                                  color: Colors.transparent,
                                  child: InkWell(
                                    onTap: () => context.go('/login'),
                                    borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                                    child: Padding(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: AppSpacing.md,
                                        vertical: 8,
                                      ),
                                      child: Row(
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          Text(
                                            'WORKSPACE',
                                            style: AppTextStyles.buttonLabel(
                                              color: Colors.white,
                                              fontSize: 10,
                                              letterSpacing: 1.2,
                                            ),
                                          ),
                                          const SizedBox(width: 4),
                                          const Icon(
                                            Icons.arrow_forward,
                                            size: 12,
                                            color: Colors.white,
                                          ),
                                        ],
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              // Hero Section (Mode A Dark)
              SliverToBoxAdapter(
                child: Padding(
                  padding: EdgeInsets.symmetric(
                    horizontal: ResponsiveLayout.horizontalPadding(context),
                    vertical: AppSpacing.xl,
                  ),
                  child: Column(
                    children: [
                      const SizedBox(height: AppSpacing.md),

                      // Eyebrow label, small-caps, wide letter-spacing, gold:
                      // "ANCIENT PRECISION. MODERN INTELLIGENCE." with thin horizontal rules
                      FittedBox(
                        fit: BoxFit.scaleDown,
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Container(
                              width: 24,
                              height: 1,
                              color: AppColors.gold.withValues(alpha: 0.5),
                            ),
                            const SizedBox(width: AppSpacing.sm),
                            Text(
                              'ANCIENT PRECISION. MODERN INTELLIGENCE.',
                              style: AppTextStyles.smallCapsLabel(
                                fontSize: 10,
                                color: AppColors.gold,
                                letterSpacing: 2.2,
                              ),
                            ),
                            const SizedBox(width: AppSpacing.sm),
                            Container(
                              width: 24,
                              height: 1,
                              color: AppColors.gold.withValues(alpha: 0.5),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: AppSpacing.xl),

                      // Signature Visual Moment:
                      // Two lines: "Structure your" (white serif) / "intelligence." (gold, italic serif)
                      Column(
                        children: [
                          Text(
                            'Structure your',
                            textAlign: TextAlign.center,
                            style: AppTextStyles.landingHero(
                              color: AppColors.darkTextPrimary,
                            ),
                          ),
                          Text(
                            'intelligence.',
                            textAlign: TextAlign.center,
                            style: AppTextStyles.landingHero(
                              color: AppColors.gold,
                              fontStyle: FontStyle.italic,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.xl),

                      // Subcopy: centered, muted gray, max ~500px width
                      ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 500),
                        child: Text(
                          'The autonomous architecture platform that dissects business requirements, performs rigorous multi-agent reasoning, and synthesizes production software blueprints.',
                          textAlign: TextAlign.center,
                          style: AppTextStyles.bodyMedium(
                            color: AppColors.darkTextSecondary,
                          ).copyWith(height: 1.6),
                        ),
                      ),
                      const SizedBox(height: AppSpacing.xxl),

                      // Two CTAs, centered:
                      // "BUILD WITH SUTRA" (solid pill button with subtle glow)
                      // "EXPLORE WORKSPACES" (plain text, muted, no border)
                      Column(
                        children: [
                          SutraButton.landingPill(
                            label: 'BUILD WITH SUTRA',
                            width: 260,
                            onPressed: () {
                              if (authState.isAuthenticated) {
                                context.go('/dashboard');
                              } else {
                                context.go('/login');
                              }
                            },
                          ),
                          const SizedBox(height: AppSpacing.lg),
                          GestureDetector(
                            onTap: () {
                              if (authState.isAuthenticated) {
                                context.go('/dashboard');
                              } else {
                                ref.read(authControllerProvider.notifier).loginAsGuest().then((ok) {
                                  if (ok && context.mounted) {
                                    context.go('/dashboard');
                                  }
                                });
                              }
                            },
                            child: Text(
                              'EXPLORE WORKSPACES',
                              style: AppTextStyles.smallCapsLabel(
                                fontSize: 11,
                                color: AppColors.darkTextSecondary,
                                letterSpacing: 2.2,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.hero),

                      // Live Backend Pulse Status Card
                      healthAsync.when(
                        data: (health) {
                          // Reflect the payload rather than asserting ONLINE.
                          final status = asString(health['status'], fallback: 'unknown');
                          final isUp = status == 'ok' || status == 'ready';
                          return SutraCard(
                            isDark: true,
                            padding: const EdgeInsets.symmetric(
                              horizontal: AppSpacing.md,
                              vertical: AppSpacing.sm,
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                StatusChip(
                                  label: 'LIVE ENGINE',
                                  statusText: isUp ? 'ONLINE' : status.toUpperCase(),
                                  isDark: true,
                                ),
                                const SizedBox(width: AppSpacing.md),
                                Text(
                                  'ai-solution-builder.onrender.com',
                                  style: AppTextStyles.mono(
                                    fontSize: 10,
                                    color: AppColors.darkTextMuted,
                                  ),
                                ),
                              ],
                            ),
                          );
                        },
                        loading: () => Text(
                          'Probing live cluster...',
                          style: AppTextStyles.mono(
                            fontSize: 10,
                            color: AppColors.darkTextMuted,
                          ),
                        ),
                        error: (_, __) => Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const StatusChip(
                              label: 'LIVE ENGINE',
                              statusText: 'UNREACHABLE',
                              isDark: true,
                            ),
                            const SizedBox(width: AppSpacing.md),
                            Text(
                              'Backend unreachable — it may be waking from cold sleep.',
                              style: AppTextStyles.mono(
                                fontSize: 10,
                                color: AppColors.statusWarningAmber,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
