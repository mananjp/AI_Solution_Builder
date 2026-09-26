import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/network/api_client.dart';
import 'core/router/app_router.dart';
import 'core/theme/app_colors.dart';
import 'core/theme/app_theme.dart';
import 'features/auth/presentation/auth_controller.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // System UI overlay
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.dark,
      statusBarBrightness: Brightness.light,
      systemNavigationBarColor: AppColors.lightBackground,
      systemNavigationBarIconBrightness: Brightness.dark,
      systemNavigationBarDividerColor: AppColors.lightBorder,
    ),
  );

  runApp(
    const ProviderScope(
      child: SutraApp(),
    ),
  );
}

class SutraApp extends ConsumerStatefulWidget {
  const SutraApp({super.key});

  @override
  ConsumerState<SutraApp> createState() => _SutraAppState();
}

class _SutraAppState extends ConsumerState<SutraApp> {
  @override
  Widget build(BuildContext context) {
    final router = ref.watch(routerProvider);

    // A 401 anywhere in the app tears down the session; the router redirect
    // then sends the user back to sign-in instead of leaving protected screens
    // rendering stale, empty data.
    ref.listen(sessionExpiredProvider, (_, __) {
      ref.read(authControllerProvider.notifier).handleSessionExpired();
    });

    return MaterialApp.router(
      title: 'Sutra OS',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightInteriorTheme,
      darkTheme: AppTheme.darkLandingTheme,
      themeMode: ThemeMode.light,
      routerConfig: router,
    );
  }
}
