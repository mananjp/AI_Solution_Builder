import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sutra_os/core/network/api_client.dart';
import 'package:sutra_os/core/storage/secure_storage_service.dart';
import 'package:sutra_os/core/widgets/voice_input_button.dart';
import 'package:sutra_os/features/auth/domain/auth_state.dart';
import 'package:sutra_os/features/auth/domain/user_model.dart';
import 'package:sutra_os/features/auth/presentation/auth_controller.dart';
import 'package:sutra_os/features/dashboard/presentation/dashboard_screen.dart';

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
    MacOsOptions? macOSOptions,
  }) async {
    if (value == null) {
      values.remove(key);
    } else {
      values[key] = value;
    }
  }

  @override
  Future<String?> read({
    required String key,
    AndroidOptions? aOptions,
    IOSOptions? iOptions,
    LinuxOptions? lOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
    WebOptions? webOptions,
    MacOsOptions? macOSOptions,
  }) async =>
      values[key];
}

class _AuthenticatedAuth extends AuthController {
  @override
  AuthState build() => AuthState(
        status: AuthStatus.authenticated,
        token: 'test-token',
        user: UserModel(
          id: 'test-user',
          email: 'test@sutra.dev',
          fullName: 'Test User',
          orgId: 'test-org',
          role: 'owner',
        ),
      );
}

final _testRoutes = <String, Object?>{
  '/api/v1/workspaces/': [
    {
      'id': 'ws-1',
      'name': 'Primary Workspace',
      'solution_count': 1,
    }
  ],
  '/api/v1/solutions/workspace/ws-1': [
    {
      'id': 'sol-1',
      'title': 'Test Solution',
      'status': 'discovery',
    }
  ],
  '/api/v1/mvp/templates': <Map<String, dynamic>>[],
  '/api/v1/billing/usage': {
    'plan': 'pro',
    'credits_remaining': 1200,
    'is_unlimited': false,
  },
  '/api/v1/opencode/health': {
    'healthy': true,
    'sidecar_healthy': true,
    'mode': 'sidecar',
    'model': 'llama-3.3-70b',
    'latency_ms': 120,
  },
  '/api/v1/system/resources': {
    'cpu_percent': 35.5,
    'cpu_count': 8,
    'memory': {
      'percent': 58.2,
      'used_mb': 8192.0,
      'total_mb': 16384.0,
    },
    'disk_percent': 42.0,
    'disk_total_bytes': 512000000000,
    'disk_free_bytes': 296960000000,
  },
  '/api/v1/opencode/diagnose': {
    'ok': true,
    'model': 'llama-3.3-70b',
    'version': '1.4.2',
    'checks': [
      {
        'name': 'Sidecar reachability',
        'status': 'ok',
        'detail': 'HTTP /health responded 200 within 45ms',
        'fix': null,
      },
      {
        'name': 'Model latency check',
        'status': 'ok',
        'detail': 'Round-trip token stream completed in 312ms',
        'fix': null,
      },
      {
        'name': 'Docker workspace mount',
        'status': 'warn',
        'detail': 'Sandbox container has 4.2GB headroom remaining',
        'fix': 'docker system prune -f to reclaim inactive caches',
      },
    ],
  },
};

ProviderContainer _makeContainer([Map<String, Object?>? routes]) {
  final dio = Dio(BaseOptions(baseUrl: 'https://test.local'))
    ..httpClientAdapter = _StubAdapter(routes ?? _testRoutes);
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

void main() {
  group('VoiceInputButton', () {
    testWidgets('renders idle microphone icon', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: VoiceInputButton(
              onTranscribed: (_, __) {},
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.mic), findsOneWidget);
    });

    testWidgets('respects disabled property', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: VoiceInputButton(
              disabled: true,
              onTranscribed: (_, __) {},
            ),
          ),
        ),
      );

      final iconBtn = tester.widget<IconButton>(find.byType(IconButton));
      expect(iconBtn.onPressed, isNull);
    });
  });

  group('Engine Diagnosis & Live Resources Panel', () {
    testWidgets('Dashboard renders Live Runtime Resources and Diagnostic panel',
        (tester) async {
      tester.view.physicalSize = const Size(360, 1000);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final container = _makeContainer();

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(home: DashboardScreen()),
        ),
      );

      for (var i = 0; i < 6; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }

      expect(tester.takeException(), isNull);
      expect(find.text('LIVE RUNTIME RESOURCES'), findsOneWidget);
      expect(find.text('CPU • RAM • DISK'), findsOneWidget);
      expect(find.text('OPENCODE SIDECAR DIAGNOSTIC'), findsOneWidget);
      expect(find.text('RUN CHECK'), findsOneWidget);

      // Tap RUN CHECK to expand diagnostic report
      await tester.ensureVisible(find.text('RUN CHECK'));
      await tester.tap(find.text('RUN CHECK'));
      for (var i = 0; i < 15; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }

      expect(find.text('CLOSE'), findsOneWidget);
      expect(find.text('RE-RUN'), findsOneWidget);
      expect(find.text('ALL CHECKS PASSED'), findsOneWidget);
      expect(find.text('Sidecar reachability'), findsOneWidget);
      expect(find.text('Model latency check'), findsOneWidget);
      expect(find.text('Docker workspace mount'), findsOneWidget);
      expect(find.text('docker system prune -f to reclaim inactive caches'),
          findsOneWidget);

      await tester.pumpWidget(const SizedBox.shrink());
      container.dispose();
    });
  });
}
