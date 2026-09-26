import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sutra_os/core/network/api_client.dart';
import 'package:sutra_os/core/storage/secure_storage_service.dart';
import 'package:sutra_os/features/billing/data/billing_repository.dart';
import 'package:sutra_os/features/billing/domain/billing_models.dart';
import 'package:sutra_os/features/billing/presentation/billing_screen.dart';

/// Serves canned JSON per path so the repository can be exercised without a
/// live backend.
class _FakeAdapter implements HttpClientAdapter {
  _FakeAdapter(this.routes);

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

/// Stands in for the platform keystore, which has no handler under `flutter test`
/// and would leave the request interceptor awaiting forever.
class _InMemorySecureStorage extends FlutterSecureStorage {
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

  @override
  Future<void> delete({
    required String key,
    AndroidOptions? aOptions,
    IOSOptions? iOptions,
    LinuxOptions? lOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
    WebOptions? webOptions,
  }) async =>
      values.remove(key);
}

ApiClient _clientWith(Map<String, Object?> routes) {
  final dio = Dio(BaseOptions(baseUrl: 'https://test.local'))
    ..httpClientAdapter = _FakeAdapter(routes);
  return ApiClient(
    storageService: SecureStorageService(storage: _InMemorySecureStorage()),
    dio: dio,
  );
}

BillingRepository _repositoryWith(Map<String, Object?> routes) {
  return BillingRepository(apiClient: _clientWith(routes));
}

void main() {
  // The payload below is the verbatim shape of `GET /api/v1/billing/usage`.
  // It previously failed to parse, so the UI always rendered the hardcoded
  // "420 credits / Professional Studio" fallback no matter what the server said.
  group('BillingUsageModel', () {
    test('parses the real /billing/usage payload', () {
      final usage = BillingUsageModel.fromJson(const {
        'org_id': '8b1f0f3e-0000-0000-0000-000000000000',
        'plan_name': 'Professional',
        'monthly_limit': 10000,
        'current_balance': 7250,
        'credits_used': 2750,
      });

      expect(usage.planName, 'Professional');
      expect(usage.creditsRemaining, 7250);
      expect(usage.creditsTotal, 10000);
      expect(usage.creditsUsed, 2750);
      expect(usage.isUnlimited, isFalse);
      expect(usage.usageRatio, closeTo(0.275, 0.001));
    });

    test('treats a null balance as unlimited', () {
      final usage = BillingUsageModel.fromJson(const {
        'plan_name': 'Demo Unlimited',
        'monthly_limit': null,
        'current_balance': null,
        'credits_used': null,
      });

      expect(usage.isUnlimited, isTrue);
      expect(usage.creditsRemaining, isNull);
      expect(usage.usageRatio, 0);
    });

    test('unknown placeholder carries no invented figures', () {
      expect(BillingUsageModel.unknown.creditsRemaining, isNull);
      expect(BillingUsageModel.unknown.isUnlimited, isTrue);
    });
  });

  group('BillingRepository', () {
    test('fetchUsage reflects the server balance', () async {
      final repo = _repositoryWith({
        '/api/v1/billing/usage': {
          'plan_name': 'Free Tier',
          'monthly_limit': 1000,
          'current_balance': 640,
          'credits_used': 360,
        },
      });

      final usage = await repo.fetchUsage();
      expect(usage.creditsRemaining, 640);
      expect(usage.planName, 'Free Tier');
    });

    test('fetchInvoices maps the credit ledger, not a hardcoded list', () async {
      final repo = _repositoryWith({
        '/api/v1/billing/transactions': [
          {
            'id': 'tx-2',
            'amount': -10,
            'action': 'blueprint_generation',
            'description': 'Multi-agent pipeline',
            'created_at': '2026-09-20T10:00:00Z',
          },
        ],
      });

      final invoices = await repo.fetchInvoices();
      expect(invoices, hasLength(1));
      expect(invoices.first.id, 'tx-2');
      expect(invoices.first.description, 'Multi-agent pipeline');
      expect(invoices.first.status, 'SETTLED');
    });

    test('fetchPlans marks the current plan from live usage', () async {
      final repo = _repositoryWith({
        '/api/v1/billing/plans': [
          {
            'id': 'free',
            'name': 'Free Tier',
            'price_usd': 0,
            'monthly_credits': 1000,
            'features': ['1 Workable System'],
          },
          {
            'id': 'pro',
            'name': 'Professional',
            'price_usd': 49,
            'monthly_credits': 10000,
            'features': ['Priority Groq 120B inference'],
          },
        ],
      });

      final plans = await repo.fetchPlans(currentPlanName: 'Professional');
      expect(plans.map((p) => p.id), containsAll(['free', 'pro']));
      expect(plans.firstWhere((p) => p.id == 'pro').isCurrent, isTrue);
      expect(plans.firstWhere((p) => p.id == 'free').isCurrent, isFalse);
    });

    test('purchaseCredits posts the amount the API accepts', () async {
      final repo = _repositoryWith({'/api/v1/billing/topup': {'status': 'success'}});
      await repo.purchaseCredits(5000);
    });

    test('changePlan fails loudly instead of reporting success', () async {
      final repo = _repositoryWith({});
      expect(
        () => repo.changePlan(planId: 'pro'),
        throwsA(isA<Exception>()),
      );
    });
  });

  testWidgets('BillingScreen renders Active Plan, Pricing Tiers, and Top-Up Refills',
      (WidgetTester tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    const billingRoutes = {
      '/api/v1/billing/usage': {
        'plan_name': 'Professional',
        'monthly_limit': 10000,
        'current_balance': 7250,
        'credits_used': 2750,
      },
      '/api/v1/billing/plans': [
        {
          'id': 'pro',
          'name': 'Professional',
          'price_usd': 49,
          'monthly_credits': 10000,
          'features': ['5 Workable Systems'],
        },
      ],
      '/api/v1/billing/transactions': [
        {
          'id': 'tx-1',
          'amount': 5000,
          'action': 'credit_purchase',
          'description': 'Purchased 5,000 AI credits',
          'created_at': '2026-09-20T10:00:00Z',
        },
      ],
    };

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(_clientWith(billingRoutes)),
        ],
        child: const MaterialApp(
          home: BillingScreen(),
        ),
      ),
    );

    // Allow future providers to resolve
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('Billing & Plans'), findsOneWidget);
    expect(find.text('CURRENT ACTIVE PLAN'), findsAtLeastNWidgets(1));
    expect(find.text('MONTHLY'), findsOneWidget);
    expect(find.text('ANNUAL'), findsOneWidget);
    expect(find.text('Instant Compute Refills'), findsOneWidget);
    expect(find.text('Past Invoices & Receipts'), findsOneWidget);

    // The live balance must reach the screen instead of the old 420 fallback.
    expect(find.textContaining('7250'), findsWidgets);
    expect(find.textContaining('420'), findsNothing);
  });
}
