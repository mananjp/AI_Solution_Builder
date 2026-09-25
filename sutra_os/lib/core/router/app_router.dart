import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../features/admin/presentation/admin_screen.dart';
import '../../features/auth/presentation/login_screen.dart';
import '../../features/auth/presentation/register_screen.dart';
import '../../features/billing/presentation/billing_screen.dart';
import '../../features/dashboard/presentation/dashboard_screen.dart';
import '../../features/landing/presentation/landing_screen.dart';
import '../../features/settings/presentation/settings_screen.dart';
import '../../features/shell/presentation/navigation_shell.dart';
import '../../features/workspace/presentation/workspace_screen.dart';

final _rootNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'root');

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    navigatorKey: _rootNavigatorKey,
    initialLocation: '/',
    routes: [
      // Landing Screen (Mode A, Dark)
      GoRoute(
        path: '/',
        name: 'landing',
        builder: (context, state) => const LandingScreen(),
      ),

      // Auth Routes
      GoRoute(
        path: '/login',
        name: 'login',
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: '/register',
        name: 'register',
        builder: (context, state) => const RegisterScreen(),
      ),

      // Mode B App Interior StatefulShellRoute
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) {
          return NavigationShell(navigationShell: navigationShell);
        },
        branches: [
          // Branch 0: Dashboard / Overview
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/dashboard',
                name: 'dashboard',
                builder: (context, state) => const DashboardScreen(),
              ),
            ],
          ),

          // Branch 1: AI Architect Workspace
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/workspace',
                name: 'workspace',
                builder: (context, state) => const WorkspaceScreen(),
              ),
            ],
          ),

          // Branch 2: Billing & Plans
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/billing',
                name: 'billing',
                builder: (context, state) => const BillingScreen(),
              ),
            ],
          ),

          // Branch 3: Settings — One-Click Deployer
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/settings',
                name: 'settings',
                builder: (context, state) => const SettingsScreen(),
              ),
            ],
          ),

          // Branch 4: Admin Console (Role-gated)
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/admin',
                name: 'admin',
                builder: (context, state) => const AdminScreen(),
              ),
            ],
          ),
        ],
      ),
    ],
  );
});
