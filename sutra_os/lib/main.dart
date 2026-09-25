import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/router/app_router.dart';
import 'core/theme/app_colors.dart';
import 'core/theme/app_theme.dart';

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

class SutraApp extends ConsumerWidget {
  const SutraApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);

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
