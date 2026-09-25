import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/widgets/cinematic_background.dart';
import '../../../core/widgets/responsive_layout.dart';
import '../../../core/widgets/sutra_button.dart';
import 'auth_controller.dart';

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _orgController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscurePassword = true;

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _orgController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submitRegister() async {
    if (!_formKey.currentState!.validate()) return;

    final success = await ref.read(authControllerProvider.notifier).register(
          email: _emailController.text.trim(),
          fullName: _nameController.text.trim(),
          password: _passwordController.text,
          orgName: _orgController.text.trim(),
        );

    if (success && mounted) {
      context.go('/dashboard');
    }
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authControllerProvider);

    return Scaffold(
      backgroundColor: AppColors.darkBackground,
      body: CinematicBackground(
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: EdgeInsets.symmetric(
                horizontal: ResponsiveLayout.horizontalPadding(context),
                vertical: AppSpacing.lg,
              ),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: Form(
                  key: _formKey,
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // Faded Brand Header above card
                      Opacity(
                        opacity: 0.9,
                        child: Column(
                          children: [
                            Text(
                              'सूत्र',
                              style: AppTextStyles.devanagariGlyph(
                                fontSize: 40,
                                color: AppColors.gold,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              'SUTRA OS',
                              style: AppTextStyles.smallCapsLabel(
                                fontSize: 11,
                                color: AppColors.darkTextPrimary,
                                letterSpacing: 3.5,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              'Ancient precision. Modern intelligence.',
                              style: AppTextStyles.bodySmall(
                                color: AppColors.darkTextSecondary,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: AppSpacing.lg),

                      // Cold Start Warning banner
                      if (authState.isWarmingUp) ...[
                        Container(
                          padding: const EdgeInsets.all(AppSpacing.md),
                          decoration: BoxDecoration(
                            color: AppColors.goldSubtle,
                            borderRadius: BorderRadius.circular(AppSpacing.radiusSm),
                            border: Border.all(color: AppColors.borderGold),
                          ),
                          child: Row(
                            children: [
                              const SizedBox(
                                width: 14,
                                height: 14,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: AppColors.gold,
                                ),
                              ),
                              const SizedBox(width: AppSpacing.sm),
                              Expanded(
                                child: Text(
                                  'Waking up the server (Render free-tier cold start)...',
                                  style: AppTextStyles.mono(
                                    fontSize: 11,
                                    color: AppColors.goldDark,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: AppSpacing.md),
                      ],

                      // Error message banner
                      if (authState.errorMessage != null && !authState.isWarmingUp) ...[
                        Container(
                          padding: const EdgeInsets.all(AppSpacing.md),
                          decoration: BoxDecoration(
                            color: AppColors.statusErrorBg,
                            borderRadius: BorderRadius.circular(AppSpacing.radiusSm),
                            border: Border.all(color: AppColors.statusErrorRed.withValues(alpha: 0.4)),
                          ),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Icon(
                                Icons.error_outline,
                                color: AppColors.statusErrorRed,
                                size: 16,
                              ),
                              const SizedBox(width: AppSpacing.sm),
                              Expanded(
                                child: Text(
                                  authState.errorMessage!,
                                  style: AppTextStyles.bodySmall(
                                    color: AppColors.statusErrorRed,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: AppSpacing.md),
                      ],

                      // Floating White Rounded Card
                      Container(
                        padding: const EdgeInsets.all(AppSpacing.xl),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                          border: Border.all(color: AppColors.lightBorder, width: 1),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withValues(alpha: 0.25),
                              blurRadius: 24,
                              offset: const Offset(0, 10),
                            ),
                          ],
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Text(
                              'Establish Organization',
                              style: AppTextStyles.serifHeading(
                                fontSize: 22,
                                color: AppColors.lightTextPrimary,
                              ),
                            ),
                            const SizedBox(height: AppSpacing.xs),
                            Text(
                              'Create your team tenancy and dedicated multi-agent cluster',
                              style: AppTextStyles.bodySmall(
                                color: AppColors.lightTextSecondary,
                              ),
                            ),
                            const SizedBox(height: AppSpacing.lg),

                            // Full Name
                            Text(
                              'FULL NAME',
                              style: AppTextStyles.smallCapsLabel(
                                fontSize: 9.5,
                                color: AppColors.lightTextSecondary,
                                letterSpacing: 1.5,
                              ),
                            ),
                            const SizedBox(height: AppSpacing.xs),
                            TextFormField(
                              controller: _nameController,
                              style: AppTextStyles.bodyMedium(
                                color: AppColors.lightTextPrimary,
                              ),
                              decoration: InputDecoration(
                                filled: true,
                                fillColor: AppColors.lightSurfaceSubtle,
                                hintText: 'Arya Sharma',
                                hintStyle: AppTextStyles.bodySmall(color: AppColors.lightTextMuted),
                                prefixIcon: const Icon(
                                  Icons.badge_outlined,
                                  size: 18,
                                  color: AppColors.lightTextSecondary,
                                ),
                                contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                                  borderSide: const BorderSide(color: AppColors.lightBorder),
                                ),
                                enabledBorder: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                                  borderSide: const BorderSide(color: AppColors.lightBorder),
                                ),
                              ),
                              validator: (val) {
                                if (val == null || val.trim().length < 2) {
                                  return 'Name must be at least 2 characters';
                                }
                                return null;
                              },
                            ),
                            const SizedBox(height: AppSpacing.md),

                            // Organization Name
                            Text(
                              'ORGANIZATION NAME',
                              style: AppTextStyles.smallCapsLabel(
                                fontSize: 9.5,
                                color: AppColors.lightTextSecondary,
                                letterSpacing: 1.5,
                              ),
                            ),
                            const SizedBox(height: AppSpacing.xs),
                            TextFormField(
                              controller: _orgController,
                              style: AppTextStyles.bodyMedium(
                                color: AppColors.lightTextPrimary,
                              ),
                              decoration: InputDecoration(
                                filled: true,
                                fillColor: AppColors.lightSurfaceSubtle,
                                hintText: 'Sutra Enterprise Labs',
                                hintStyle: AppTextStyles.bodySmall(color: AppColors.lightTextMuted),
                                prefixIcon: const Icon(
                                  Icons.business_outlined,
                                  size: 18,
                                  color: AppColors.lightTextSecondary,
                                ),
                                contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                                  borderSide: const BorderSide(color: AppColors.lightBorder),
                                ),
                                enabledBorder: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                                  borderSide: const BorderSide(color: AppColors.lightBorder),
                                ),
                              ),
                              validator: (val) {
                                if (val == null || val.trim().length < 2) {
                                  return 'Organization name must be at least 2 characters';
                                }
                                return null;
                              },
                            ),
                            const SizedBox(height: AppSpacing.md),

                            // Email
                            Text(
                              'CORPORATE EMAIL',
                              style: AppTextStyles.smallCapsLabel(
                                fontSize: 9.5,
                                color: AppColors.lightTextSecondary,
                                letterSpacing: 1.5,
                              ),
                            ),
                            const SizedBox(height: AppSpacing.xs),
                            TextFormField(
                              controller: _emailController,
                              keyboardType: TextInputType.emailAddress,
                              style: AppTextStyles.bodyMedium(
                                color: AppColors.lightTextPrimary,
                              ),
                              decoration: InputDecoration(
                                filled: true,
                                fillColor: AppColors.lightSurfaceSubtle,
                                hintText: 'arya@enterprise.io',
                                hintStyle: AppTextStyles.bodySmall(color: AppColors.lightTextMuted),
                                prefixIcon: const Icon(
                                  Icons.mail_outline,
                                  size: 18,
                                  color: AppColors.lightTextSecondary,
                                ),
                                contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                                  borderSide: const BorderSide(color: AppColors.lightBorder),
                                ),
                                enabledBorder: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                                  borderSide: const BorderSide(color: AppColors.lightBorder),
                                ),
                              ),
                              validator: (val) {
                                if (val == null || !val.contains('@')) {
                                  return 'Enter a valid email';
                                }
                                return null;
                              },
                            ),
                            const SizedBox(height: AppSpacing.md),

                            // Password
                            Text(
                              'PASSWORD (MIN 8 CHARS)',
                              style: AppTextStyles.smallCapsLabel(
                                fontSize: 9.5,
                                color: AppColors.lightTextSecondary,
                                letterSpacing: 1.5,
                              ),
                            ),
                            const SizedBox(height: AppSpacing.xs),
                            TextFormField(
                              controller: _passwordController,
                              obscureText: _obscurePassword,
                              style: AppTextStyles.bodyMedium(
                                color: AppColors.lightTextPrimary,
                              ),
                              decoration: InputDecoration(
                                filled: true,
                                fillColor: AppColors.lightSurfaceSubtle,
                                hintText: '••••••••',
                                hintStyle: AppTextStyles.bodySmall(color: AppColors.lightTextMuted),
                                prefixIcon: const Icon(
                                  Icons.lock_outline,
                                  size: 18,
                                  color: AppColors.lightTextSecondary,
                                ),
                                suffixIcon: IconButton(
                                  icon: Icon(
                                    _obscurePassword
                                        ? Icons.visibility_off_outlined
                                        : Icons.visibility_outlined,
                                    size: 18,
                                    color: AppColors.lightTextSecondary,
                                  ),
                                  onPressed: () {
                                    setState(() {
                                      _obscurePassword = !_obscurePassword;
                                    });
                                  },
                                ),
                                contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                                  borderSide: const BorderSide(color: AppColors.lightBorder),
                                ),
                                enabledBorder: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                                  borderSide: const BorderSide(color: AppColors.lightBorder),
                                ),
                              ),
                              validator: (val) {
                                if (val == null || val.length < 8) {
                                  return 'Password must be at least 8 characters';
                                }
                                return null;
                              },
                            ),
                            const SizedBox(height: AppSpacing.xl),

                            // Submit Button
                            SutraButton(
                              label: 'Establish Organization',
                              height: 46,
                              isLoading: authState.isLoading,
                              variant: SutraButtonVariant.primaryBlack,
                              onPressed: _submitRegister,
                              icon: const Icon(
                                Icons.rocket_launch_outlined,
                                size: 16,
                                color: Colors.white,
                              ),
                            ),
                          ],
                        ),
                      ),

                      const SizedBox(height: AppSpacing.lg),

                      // Link to Login
                      Wrap(
                        alignment: WrapAlignment.center,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          Text(
                            'Already registered with an organization? ',
                            style: AppTextStyles.bodySmall(color: AppColors.darkTextSecondary),
                          ),
                          GestureDetector(
                            onTap: () => context.go('/login'),
                            child: Text(
                              'Sign in',
                              style: AppTextStyles.bodySmall(
                                color: AppColors.gold,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      Center(
                        child: GestureDetector(
                          onTap: () => context.go('/'),
                          child: Text(
                            '← Return to Overview',
                            style: AppTextStyles.bodySmall(
                              color: AppColors.darkTextMuted,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
