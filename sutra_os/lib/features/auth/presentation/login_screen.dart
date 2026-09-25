import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/widgets/cinematic_background.dart';
import '../../../core/widgets/responsive_layout.dart';
import '../../../core/widgets/sutra_button.dart';
import '../../landing/presentation/landing_screen.dart';
import 'auth_controller.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscurePassword = true;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submitLogin() async {
    if (!_formKey.currentState!.validate()) return;

    final success = await ref.read(authControllerProvider.notifier).login(
          _emailController.text.trim(),
          _passwordController.text,
        );

    if (success && mounted) {
      context.go('/dashboard');
    }
  }

  Future<void> _continueAsGuest() async {
    final success =
        await ref.read(authControllerProvider.notifier).loginAsGuest();
    if (success && mounted) {
      context.go('/dashboard');
    }
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authControllerProvider);
    final healthAsync = ref.watch(backendHealthProvider);
    final isBackendOnline = healthAsync.maybeWhen(
      data: (data) => data['status'] == 'ok' || data['status'] == 'healthy' || data['status'] == null,
      orElse: () => false,
    );

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
                constraints: const BoxConstraints(maxWidth: 400),
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
                                fontSize: 42,
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

                      // Cold Start / Warming Warning banner
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
                                  'Waking up the live server (Render cold start: ~20-50s)...',
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
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  'Sign In',
                                  style: AppTextStyles.serifHeading(
                                    fontSize: 24,
                                    color: AppColors.lightTextPrimary,
                                  ),
                                ),
                                if (isBackendOnline)
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                                    decoration: BoxDecoration(
                                      color: const Color(0xFFEAF4EC),
                                      borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                                      border: Border.all(color: const Color(0xFF2E7D32).withValues(alpha: 0.3)),
                                    ),
                                    child: Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Container(
                                          width: 5,
                                          height: 5,
                                          decoration: const BoxDecoration(
                                            color: Color(0xFF2E7D32),
                                            shape: BoxShape.circle,
                                          ),
                                        ),
                                        const SizedBox(width: 4),
                                        Text(
                                          'LIVE AUTH',
                                          style: AppTextStyles.smallCapsLabel(
                                            fontSize: 8.5,
                                            color: const Color(0xFF2E7D32),
                                            fontWeight: FontWeight.w700,
                                            letterSpacing: 1.0,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                              ],
                            ),
                            const SizedBox(height: AppSpacing.xs),
                            Text(
                              'Connect to your organization architecture workspace',
                              style: AppTextStyles.bodySmall(
                                color: AppColors.lightTextSecondary,
                              ),
                            ),
                            const SizedBox(height: AppSpacing.lg),

                            // Email Field
                            Text(
                              'EMAIL ADDRESS',
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
                                hintText: 'architect@sutraos.io',
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
                                if (val == null || val.trim().isEmpty) return 'Email is required';
                                if (!val.contains('@')) return 'Enter a valid email';
                                return null;
                              },
                            ),
                            const SizedBox(height: AppSpacing.md),

                            // Password Field
                            Text(
                              'PASSWORD',
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
                                if (val == null || val.isEmpty) return 'Password is required';
                                return null;
                              },
                            ),
                            const SizedBox(height: AppSpacing.xl),

                            // Authenticate Black Button
                            SutraButton(
                              label: 'AUTHENTICATE',
                              height: 46,
                              isLoading: authState.isLoading,
                              variant: SutraButtonVariant.primaryBlack,
                              onPressed: _submitLogin,
                              icon: const Icon(
                                Icons.arrow_forward,
                                size: 16,
                                color: Colors.white,
                              ),
                            ),
                            const SizedBox(height: AppSpacing.md),

                            // Explore as Guest Anonymous Link
                            GestureDetector(
                              onTap: authState.isLoading ? null : _continueAsGuest,
                              child: Padding(
                                padding: const EdgeInsets.symmetric(vertical: 4),
                                child: Text(
                                  'EXPLORE AS GUEST (ANONYMOUS)',
                                  textAlign: TextAlign.center,
                                  style: AppTextStyles.smallCapsLabel(
                                    fontSize: 10,
                                    color: AppColors.lightTextSecondary,
                                    letterSpacing: 1.5,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),

                      const SizedBox(height: AppSpacing.lg),

                      // Links Below Card
                      Column(
                        children: [
                          Wrap(
                            alignment: WrapAlignment.center,
                            crossAxisAlignment: WrapCrossAlignment.center,
                            children: [
                              Text(
                                "Don't have an account? ",
                                style: AppTextStyles.bodySmall(
                                  color: AppColors.darkTextSecondary,
                                ),
                              ),
                              GestureDetector(
                                onTap: () => context.go('/register'),
                                child: Text(
                                  'Register',
                                  style: AppTextStyles.bodySmall(
                                    color: AppColors.gold,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: AppSpacing.sm),
                          GestureDetector(
                            onTap: () => context.go('/'),
                            child: Text(
                              '← Return to Overview',
                              style: AppTextStyles.bodySmall(
                                color: AppColors.darkTextMuted,
                              ),
                            ),
                          ),
                        ],
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
