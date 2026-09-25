import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sutra_os/features/admin/presentation/admin_screen.dart';
import 'package:sutra_os/features/auth/presentation/login_screen.dart';
import 'package:sutra_os/features/auth/presentation/register_screen.dart';
import 'package:sutra_os/features/billing/presentation/billing_screen.dart';
import 'package:sutra_os/features/dashboard/presentation/dashboard_screen.dart';
import 'package:sutra_os/features/landing/presentation/landing_screen.dart';
import 'package:sutra_os/features/settings/presentation/settings_screen.dart';
import 'package:sutra_os/features/workspace/presentation/workspace_screen.dart';

void main() {
  testWidgets('LandingScreen renders with zero overflow on 360dp width', (tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: LandingScreen()),
      ),
    );
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.byType(LandingScreen), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('LoginScreen renders with zero overflow on 360dp width', (tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: LoginScreen()),
      ),
    );
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.byType(LoginScreen), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('RegisterScreen renders with zero overflow on 360dp width', (tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: RegisterScreen()),
      ),
    );
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.byType(RegisterScreen), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('DashboardScreen renders with zero overflow on 360dp width', (tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: DashboardScreen()),
      ),
    );
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.byType(DashboardScreen), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('WorkspaceScreen renders with zero overflow on 360dp width', (tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: WorkspaceScreen()),
      ),
    );
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.byType(WorkspaceScreen), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('BillingScreen renders with zero overflow on 360dp width', (tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: BillingScreen()),
      ),
    );
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.byType(BillingScreen), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('SettingsScreen renders with zero overflow on 360dp width', (tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: SettingsScreen()),
      ),
    );
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.byType(SettingsScreen), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('AdminScreen renders with zero overflow on 360dp width', (tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: AdminScreen()),
      ),
    );
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.byType(AdminScreen), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
