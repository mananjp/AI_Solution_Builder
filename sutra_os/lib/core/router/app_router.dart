import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../features/admin/presentation/admin_screen.dart';
import '../../features/auth/domain/auth_state.dart';
import '../../features/auth/presentation/auth_controller.dart';
import '../../features/auth/presentation/login_screen.dart';
import '../../features/auth/presentation/oauth_callback_screen.dart';
import '../../features/auth/presentation/register_screen.dart';
import '../../features/billing/presentation/billing_screen.dart';
import '../../features/chat/presentation/chat_screen.dart';
import '../../features/dashboard/presentation/dashboard_screen.dart';
import '../../features/landing/presentation/landing_screen.dart';
import '../../features/settings/presentation/settings_screen.dart';
import '../../features/shell/presentation/navigation_shell.dart';
import '../../features/workspace/presentation/mvp_builds_screen.dart';
import '../../features/workspace/presentation/sandbox_screen.dart';
import '../../features/workspace/presentation/solution_detail_screen.dart';
import '../../features/workspace/presentation/workable_screen.dart';
import '../../features/workspace/presentation/workspace_screen.dart';

final _rootNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'root');

/// Re-runs the router's redirect whenever auth state changes, without
/// rebuilding the [GoRouter] itself.
class _AuthRefreshListenable extends ChangeNotifier {
  _AuthRefreshListenable(Ref ref) {
    ref.listen<AuthState>(authControllerProvider, (_, __) => notifyListeners());
  }
}

final routerProvider = Provider<GoRouter>((ref) {
  // Deliberately does NOT watch auth state. Rebuilding a GoRouter on every auth
  // transition throws away the current location and shell branch stack, which
  // made the app jump back to the landing screen mid-session. Auth changes are
  // observed through [refreshListenable] instead, and the redirect reads the
  // latest state on each evaluation.
  final refresh = _AuthRefreshListenable(ref);
  ref.onDispose(refresh.dispose);

  return GoRouter(
    navigatorKey: _rootNavigatorKey,
    initialLocation: '/',
    refreshListenable: refresh,
    redirect: (context, state) {
      final authState = ref.read(authControllerProvider);
      final isAuthenticated = authState.isAuthenticated;
      final isLoading = authState.status == AuthStatus.initial ||
          authState.status == AuthStatus.loading;
      final currentPath = state.matchedLocation;

      // Public routes that don't need auth
      final publicRoutes = ['/', '/login', '/register', '/callback'];
      final isPublicRoute = publicRoutes.contains(currentPath);

      // While loading (checking saved token), don't redirect
      if (isLoading) return null;

      // Allow OAuth callback to execute without interruption
      if (currentPath == '/callback') return null;

      // If authenticated and trying to access login/register, redirect to dashboard
      if (isAuthenticated && (currentPath == '/login' || currentPath == '/register')) {
        return '/dashboard';
      }

      // If authenticated and on landing, redirect to dashboard
      if (isAuthenticated && currentPath == '/') {
        return '/dashboard';
      }

      // If not authenticated and trying to access protected routes, redirect to landing
      if (!isAuthenticated && !isPublicRoute) {
        return '/';
      }

      return null;
    },
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
      // OAuth landing route. Public, because the provider redirects here
      // before a session exists.
      GoRoute(
        path: '/callback',
        name: 'callback',
        builder: (context, state) => const OAuthCallbackScreen(),
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
              // Blueprint review: artifacts, approvals, export, regeneration.
              GoRoute(
                path: '/solution',
                name: 'solution',
                builder: (context, state) => const SolutionDetailScreen(),
              ),
              // MVP build lifecycle.
              GoRoute(
                path: '/builds',
                name: 'builds',
                builder: (context, state) => const MvpBuildsScreen(),
              ),
              // Streaming build chat.
              GoRoute(
                path: '/chat',
                name: 'chat',
                builder: (context, state) => const ChatScreen(),
              ),
              // Build sandbox: file explorer + live preview.
              GoRoute(
                path: '/sandbox',
                name: 'sandbox',
                builder: (context, state) => const SandboxScreen(),
              ),
              // Workable Systems live-app preview.
              GoRoute(
                path: '/live-app',
                name: 'live-app',
                builder: (context, state) => const WorkableScreen(),
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
