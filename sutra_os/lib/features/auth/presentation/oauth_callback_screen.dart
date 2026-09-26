import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/widgets/sutra_button.dart';
import '../application/oauth_controller.dart';

/// OAuth landing route (`/callback`), mirroring the web app's `/callback`.
///
/// The backend is the source of truth for which providers exist: it returns
/// `{"providers": [...], "allow_anonymous": true}`. On a deployment with no
/// providers configured this screen says so plainly instead of rendering
/// buttons that cannot work.
class OAuthCallbackScreen extends ConsumerStatefulWidget {
  const OAuthCallbackScreen({super.key});

  @override
  ConsumerState<OAuthCallbackScreen> createState() =>
      _OAuthCallbackScreenState();
}

class _OAuthCallbackScreenState extends ConsumerState<OAuthCallbackScreen> {
  bool _exchangeStarted = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // A provider redirect lands here with `?provider=...&code=...&state=...`.
    // This has to be `didChangeDependencies`, not `initState`: GoRouterState is
    // an inherited widget and cannot be depended on before initState completes.
    if (_exchangeStarted) return;
    final query = GoRouterState.of(context).uri.queryParameters;
    final code = query['code'];
    if (code == null || code.isEmpty) return;
    _exchangeStarted = true;
    final provider = query['provider'] ?? 'github';
    final state = query['state'];
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      ref.read(oauthCallbackProvider.notifier).complete(provider, code, state);
    });
  }


  @override
  Widget build(BuildContext context) {
    final providersAsync = ref.watch(oauthProvidersProvider);
    final callback = ref.watch(oauthCallbackProvider);

    // A completed exchange means we have a real session; go to the app. The
    // controller re-runs `checkAuthStatus`, so AuthState is already hydrated by
    // the time this redirect happens and the router will not bounce us back.
    if (callback.succeeded) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) context.go('/dashboard');
      });
    }

    return Scaffold(

      backgroundColor: AppColors.lightBackground,
      appBar: AppBar(
        backgroundColor: AppColors.lightSurface,
        surfaceTintColor: Colors.transparent,
        title: Text('Sign in',
            style: AppTextStyles.serifHeading(fontSize: 20)),
      ),
      body: providersAsync.when(
        loading: () =>
            const Center(child: CircularProgressIndicator(color: AppColors.gold)),
        error: (e, _) => _message(
          icon: Icons.cloud_off_outlined,
          color: AppColors.statusErrorRed,
          title: 'Could not load sign-in options',
          body: '$e',
          actionLabel: 'Retry',
          onAction: () => ref.invalidate(oauthProvidersProvider),
        ),
        data: (info) {
          if (callback.isCompleting) {
            return const Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  CircularProgressIndicator(color: AppColors.gold),
                  SizedBox(height: AppSpacing.md),
                  Text('Completing sign-in...'),
                ],
              ),
            );
          }
          if (callback.error != null) {
            return _message(
              icon: Icons.error_outline,
              color: AppColors.statusErrorRed,
              title: 'Sign-in failed',
              body: callback.error!,
              actionLabel: 'Back to sign in',
              onAction: () => context.go('/login'),
            );
          }
          if (info.providers.isEmpty) {
            return _message(
              icon: Icons.info_outline,
              color: AppColors.goldDark,
              title: 'No social sign-in configured',
              body: 'This deployment has no OAuth providers enabled. '
                  'Use email and password, or continue as a guest.',
              actionLabel: 'Back to sign in',
              onAction: () => context.go('/login'),
            );
          }
          return ListView(
            padding: const EdgeInsets.all(AppSpacing.lg),
            children: [
              const SizedBox(height: AppSpacing.lg),
              Center(
                child: Text(
                  'Continue with',
                  style: AppTextStyles.serifHeading(fontSize: 22),
                ),
              ),
              const SizedBox(height: AppSpacing.lg),
              for (final provider in info.providers) ...[
                SutraButton.outline(
                  label: _label(provider),
                  width: double.infinity,
                  height: 44,
                  onPressed: () => ref
                      .read(oauthCallbackProvider.notifier)
                      .authorize(provider),
                ),
                const SizedBox(height: AppSpacing.sm),
              ],
              if (info.allowAnonymous) ...[
                const Divider(color: AppColors.lightBorder, height: AppSpacing.xl),
                SutraButton(
                  label: 'Continue as guest',
                  width: double.infinity,
                  height: 44,
                  onPressed: () => context.go('/login'),
                ),
              ],
            ],
          );
        },
      ),
    );
  }

  static String _label(String provider) {
    switch (provider.toLowerCase()) {
      case 'github':
        return 'GITHUB';
      case 'google':
        return 'GOOGLE';
      default:
        return provider.toUpperCase();
    }
  }

  Widget _message({
    required IconData icon,
    required Color color,
    required String title,
    required String body,
    required String actionLabel,
    required VoidCallback onAction,
  }) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 40, color: color),
            const SizedBox(height: AppSpacing.md),
            Text(title, style: AppTextStyles.serifHeading(fontSize: 19)),
            const SizedBox(height: AppSpacing.xs),
            Text(
              body,
              textAlign: TextAlign.center,
              style: AppTextStyles.bodySmall(
                color: AppColors.lightTextSecondary,
              ),
            ),
            const SizedBox(height: AppSpacing.lg),
            SutraButton(label: actionLabel, onPressed: onAction),
          ],
        ),
      ),
    );
  }
}

