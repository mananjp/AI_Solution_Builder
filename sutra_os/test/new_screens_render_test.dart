import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:sutra_os/core/network/api_client.dart';
import 'package:sutra_os/core/storage/secure_storage_service.dart';
import 'package:sutra_os/features/auth/domain/auth_state.dart';
import 'package:sutra_os/features/auth/domain/user_model.dart';
import 'package:sutra_os/features/auth/presentation/auth_controller.dart';
import 'package:sutra_os/features/auth/presentation/oauth_callback_screen.dart';
import 'package:sutra_os/features/chat/presentation/chat_screen.dart';
import 'package:sutra_os/features/workspace/presentation/mvp_builds_screen.dart';
import 'package:sutra_os/features/workspace/presentation/sandbox_screen.dart';
import 'package:sutra_os/features/workspace/presentation/solution_detail_screen.dart';
import 'package:sutra_os/features/workspace/presentation/workable_screen.dart';

/// Serves canned JSON per path so screens can be rendered against realistic
/// payloads without a live backend. Anything unmapped returns a 404, which is
/// what the real app would see for a missing resource.
class _StubAdapter implements HttpClientAdapter {
  _StubAdapter(this.routes);

  final Map<String, Object?> routes;

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final path = options.uri.path;
    final body = routes[path];
    if (body == null) {
      return ResponseBody.fromString(
        jsonEncode({'detail': 'Not Found'}),
        404,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      );
    }
    return ResponseBody.fromString(
      jsonEncode(body),
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }
}

class _MemoryStorage extends FlutterSecureStorage {
  final Map<String, String> values = {};

  @override
  Future<void> write({
    required String key,
    required String? value,
    AndroidOptions? aOptions,
    IOSOptions? iOptions,
    LinuxOptions? lOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
    WebOptions? webOptions,
  }) async =>
      values[key] = value ?? '';

  @override
  Future<String?> read({
    required String key,
    AndroidOptions? aOptions,
    IOSOptions? iOptions,
    LinuxOptions? lOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
    WebOptions? webOptions,
  }) async =>
      values[key];
}

const _solutionId = '11111111-1111-1111-1111-111111111111';
const _buildId = '22222222-2222-2222-2222-222222222222';

/// The real payload shapes captured from the live Render backend.
final _routes = <String, Object?>{
  '/api/v1/workspaces/': [
    {
      'id': '33333333-3333-3333-3333-333333333333',
      'org_id': '44444444-4444-4444-4444-444444444444',
      'name': 'Custom App Builder',
      'description': 'Apps built through conversational OpenCode chat',
      'created_at': '2026-09-25T17:48:39.981899Z',
      'updated_at': '2026-09-25T17:48:39.981904Z',
      'solution_count': 1,
    }
  ],
  '/api/v1/solutions/workspace/33333333-3333-3333-3333-333333333333': [
    {
      'id': _solutionId,
      'workspace_id': '33333333-3333-3333-3333-333333333333',
      'title': 'MiniTodo',
      'description': 'App built through conversational OpenCode chat',
      'status': 'discovery',
      'approval_status': null,
      'approved_by': null,
      'approved_at': null,
      'created_at': '2026-09-25T17:50:24.958355Z',
      'updated_at': '2026-09-25T17:50:24.958361Z',
    }
  ],
  '/api/v1/solutions/$_solutionId': {
    'solution': {
      'id': _solutionId,
      'workspace_id': '33333333-3333-3333-3333-333333333333',
      'title': 'MiniTodo',
      'description': 'A tiny todo app',
      'status': 'discovery',
      'approval_status': null,
      'approved_by': null,
      'approved_at': null,
      'created_at': '2026-09-25T17:50:24.958355Z',
      'updated_at': '2026-09-25T17:50:24.958361Z',
    },
    'artifacts': [
      {
        'id': 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        'solution_id': _solutionId,
        'artifact_type': 'architecture',
        'title': 'High-Level Architecture',
        'version': 2,
        'content': {'layers': ['api', 'web'], 'pattern': 'modular monolith'},
        'content_text': 'FastAPI + Next.js modular monolith.',
        'created_at': '2026-09-25T17:51:00Z',
      },
      {
        'id': 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        'solution_id': _solutionId,
        'artifact_type': 'database_schema',
        'title': 'Database Schema',
        'version': 1,
        'content': {'tables': ['todos']},
        'content_text': null,
        'created_at': '2026-09-25T17:51:00Z',
      },
      {
        'id': 'cccccccc-cccc-cccc-cccc-cccccccccccc',
        'solution_id': _solutionId,
        'artifact_type': 'bpmn_flows',
        'title': 'Process Flows',
        'version': 1,
        'content': {},
        'content_text': null,
        'created_at': '2026-09-25T17:51:00Z',
      },
    ],
  },
  '/api/v1/mvp/$_solutionId/builds': [
    {
      'build_id': _buildId,
      'solution_id': _solutionId,
      'build_number': 3,
      'status': 'complete',
      'workspace_path': 'workspaces/minitodo',
      'file_count': 42,
      'frontend_url': 'https://minitodo.onrender.com',
      'render_service_url': null,
      'render_deploy_status': 'live',
      'files': [
        {'path': 'app/page.tsx', 'size': 2048, 'is_dir': false},
        {'path': 'lib', 'size': 0, 'is_dir': true},
      ],
    }
  ],
  '/api/v1/mvp/builds/$_buildId/status': {
    'build_id': _buildId,
    'solution_id': _solutionId,
    'build_number': 3,
    'status': 'complete',
    'workspace_path': 'workspaces/minitodo',
    'file_count': 42,
    'frontend_url': 'https://minitodo.onrender.com',
    'render_deploy_status': 'live',
    'files': [
      {'path': 'app/page.tsx', 'size': 2048, 'is_dir': false},
    ],
  },
  '/api/v1/workable/$_solutionId/modules': {
    'todos': ['items'],
  },
  '/api/v1/workable/$_solutionId/todos/items': [
    {'id': '1', 'title': 'Buy milk', 'done': false},
  ],
  '/api/v1/auth/providers': {
    'providers': <String>[],
    'allow_anonymous': true,
  },
  '/api/v1/mvp/templates': <Map<String, dynamic>>[],
};

/// Workspaces and solutions are only fetched for an authenticated user, so the
/// container reports a signed-in session. Without this every screen correctly
/// renders its empty state and the test proves nothing.
class _AuthenticatedAuth extends AuthController {
  @override
  AuthState build() => AuthState(
        status: AuthStatus.authenticated,
        token: 'test-token',
        user: UserModel(
          id: '44444444-4444-4444-4444-444444444444',
          email: 'qa@example.com',
          fullName: 'QA Engineer',
          orgId: '44444444-4444-4444-4444-444444444444',
          role: 'owner',
        ),
      );
}

ProviderContainer _container([Map<String, Object?>? routes]) {
  final dio = Dio(BaseOptions(baseUrl: 'https://test.local'))
    ..httpClientAdapter = _StubAdapter(routes ?? _routes);
  return ProviderContainer(
    overrides: [
      authControllerProvider.overrideWith(_AuthenticatedAuth.new),
      apiClientProvider.overrideWithValue(
        ApiClient(
          storageService: SecureStorageService(storage: _MemoryStorage()),
          dio: dio,
        ),
      ),
    ],
  );
}

Future<void> _pumpAt(
  WidgetTester tester,
  Widget child, {
  Map<String, Object?>? routes,
}) async {
  tester.view.physicalSize = const Size(360, 800);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(() {
    tester.view.resetPhysicalSize();
    tester.view.resetDevicePixelRatio();
  });

  final container = _container(routes ?? _routes);
  addTearDown(container.dispose);

  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(home: child),
    ),
  );
  // The selection chain is several awaited fetches deep
  // (workspaces -> workspace id -> solutions -> solution id -> screen data), and
  // `pumpAndSettle` is unusable here because the build screen polls on a timer.
  for (var i = 0; i < 12; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}


void main() {
  testWidgets('MvpBuildsScreen renders a real build without overflow',
      (tester) async {
    await _pumpAt(tester, const MvpBuildsScreen());
    expect(tester.takeException(), isNull);
    await tester.ensureVisible(find.text('BUILDS'));
    await tester.tap(find.text('BUILDS'));
    for (var i = 0; i < 15; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    expect(find.text('Build #3'), findsOneWidget);
    // Real deploy state, not a fabricated "deployed".
    expect(find.textContaining('live'), findsWidgets);
  });

  testWidgets('SolutionDetailScreen renders every artifact type',
      (tester) async {
    await _pumpAt(tester, const SolutionDetailScreen());
    await tester.pump(const Duration(milliseconds: 400));
    expect(tester.takeException(), isNull);
    expect(find.text('MiniTodo'), findsOneWidget);
    // All three artifact types must be reachable, not just the first.
    expect(find.text('ARCHITECTURE'), findsOneWidget);
    expect(find.text('DB SCHEMA & ERD'), findsOneWidget);
    expect(find.text('BPMN 2.0 PROCESS'), findsOneWidget);
    expect(find.text('APPROVE'), findsOneWidget);
    expect(find.text('REQUEST CHANGES'), findsOneWidget);
    expect(find.text('JSON'), findsOneWidget);
    expect(find.text('MARKDOWN'), findsOneWidget);
    expect(find.text('ZIP'), findsOneWidget);
  });

  testWidgets('ChatScreen renders the empty prompt state', (tester) async {
    await _pumpAt(tester, const ChatScreen());
    expect(tester.takeException(), isNull);
    expect(find.text('Describe the app you want'), findsOneWidget);
  });

  testWidgets('WorkableScreen renders provisioned module records',
      (tester) async {
    await _pumpAt(tester, const WorkableScreen());
    expect(tester.takeException(), isNull);
    expect(find.text('MOUNTED LIVE APP'), findsOneWidget);
    expect(find.textContaining('Buy milk'), findsOneWidget);
  });

  testWidgets('WorkableScreen offers Provision when the live app is absent',
      (tester) async {
    // Workspaces and solutions resolve, but the live-app modules endpoint 404s
    // — exactly what the backend returns before provisioning.
    final routes = Map<String, Object?>.from(_routes)
      ..remove('/api/v1/workable/$_solutionId/modules');
    await _pumpAt(tester, const WorkableScreen(), routes: routes);
    expect(tester.takeException(), isNull);
    expect(find.text('No live app mounted'), findsOneWidget);
    expect(find.text('PROVISION'), findsOneWidget);
  });

  testWidgets('WorkableScreen exposes create and edit on real rows',
      (tester) async {
    await _pumpAt(tester, const WorkableScreen());
    expect(tester.takeException(), isNull);
    // Without these you could only get rows by seeding demo data.
    expect(find.text('NEW ROW'), findsOneWidget);
    expect(find.byTooltip('Edit'), findsOneWidget);
    expect(find.byTooltip('Delete'), findsOneWidget);
  });

  testWidgets('SandboxScreen mounts as a real route without throwing',
      (tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    final container = _container();
    addTearDown(container.dispose);

    // The screen reads GoRouterState for `?build=`, so it has to be pumped as a
    // route. This also guards the didChangeDependencies move: reading
    // GoRouterState from initState throws in a debug build.
    final router = GoRouter(
      initialLocation: '/sandbox',
      routes: [
        GoRoute(
          path: '/sandbox',
          builder: (_, __) => const SandboxScreen(),
        ),
      ],
    );
    addTearDown(router.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    for (var i = 0; i < 12; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }

    // Only the mount is asserted here. `WebViewWidget` is a PlatformView and
    // cannot render under the test binding, so the live preview is verified on
    // a device instead. What matters here is that opening /sandbox does not
    // throw — reading GoRouterState from initState used to crash it outright.
    expect(find.byType(SandboxScreen), findsOneWidget);
    expect(find.byType(Tab), findsNWidgets(3));
  });

  testWidgets('SolutionDetailScreen displays locked snapshot when approved',
      (tester) async {
    final routes = Map<String, Object?>.from(_routes);
    routes['/api/v1/solutions/$_solutionId'] = {
      'solution': {
        'id': _solutionId,
        'workspace_id': '33333333-3333-3333-3333-333333333333',
        'title': 'MiniTodo',
        'description': 'A tiny todo app',
        'status': 'approved',
        'approval_status': 'approved',
        'approved_by': 'lead@company.com',
        'approved_at': '2026-09-25T18:00:00Z',
        'created_at': '2026-09-25T17:50:24.958355Z',
        'updated_at': '2026-09-25T17:50:24.958361Z',
      },
      'artifacts': <Map<String, dynamic>>[],
    };
    await _pumpAt(tester, const SolutionDetailScreen(), routes: routes);
    await tester.pump(const Duration(milliseconds: 400));
    expect(tester.takeException(), isNull);
    expect(find.text('Snapshot Frozen - Ready for Build'), findsOneWidget);
    expect(find.text('SNAPSHOT LOCKED'), findsOneWidget);
  });

  testWidgets('OAuthCallbackScreen states honestly when no providers exist',
      (tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    final container = _container();
    addTearDown(container.dispose);

    // This screen reads GoRouterState, so it must be pumped as a real route
    // rather than a bare `MaterialApp(home:)`.
    final router = GoRouter(
      initialLocation: '/callback',
      routes: [
        GoRoute(
          path: '/callback',
          builder: (_, __) => const OAuthCallbackScreen(),
        ),
      ],
    );
    addTearDown(router.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    for (var i = 0; i < 12; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    expect(tester.takeException(), isNull);
    // Must NOT pretend social login is available on a deployment with none.
    expect(find.text('No social sign-in configured'), findsOneWidget);
    expect(find.text('GITHUB'), findsNothing);
    expect(find.text('GOOGLE'), findsNothing);

  });
}
