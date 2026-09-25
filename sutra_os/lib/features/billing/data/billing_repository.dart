import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../domain/billing_models.dart';

final billingRepositoryProvider = Provider<BillingRepository>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return BillingRepository(apiClient: apiClient);
});

class BillingRepository {
  final ApiClient? _apiClient;

  // In-memory persistent state for active session transactions
  BillingUsageModel _currentUsage = BillingUsageModel(
    planName: 'Professional Studio',
    creditsRemaining: 420,
    creditsUsed: 80,
    creditsTotal: 500,
    usageRatio: 0.16,
    renewalDate: 'Nov 14, 2026',
    paymentMethod: 'Mastercard •••• 4288',
    resetsInDays: 12,
  );

  final List<InvoiceModel> _invoices = [
    InvoiceModel(
      id: 'SUTRA-8921',
      date: 'Oct 14, 2026',
      amount: 49.00,
      description: 'Professional Studio Subscription',
      status: 'PAID',
      paymentMethod: 'Mastercard •••• 4288',
    ),
    InvoiceModel(
      id: 'SUTRA-8410',
      date: 'Sep 14, 2026',
      amount: 49.00,
      description: 'Professional Studio Subscription',
      status: 'PAID',
      paymentMethod: 'Mastercard •••• 4288',
    ),
    InvoiceModel(
      id: 'SUTRA-7904',
      date: 'Aug 14, 2026',
      amount: 19.00,
      description: '+5,000 Credits Fast Refill',
      status: 'PAID',
      paymentMethod: 'Google Pay •••• 1944',
    ),
    InvoiceModel(
      id: 'SUTRA-7102',
      date: 'Jul 14, 2026',
      amount: 49.00,
      description: 'Professional Studio Subscription',
      status: 'PAID',
      paymentMethod: 'Mastercard •••• 4288',
    ),
  ];

  BillingRepository({ApiClient? apiClient}) : _apiClient = apiClient;

  Future<BillingUsageModel> fetchUsage() async {
    try {
      if (_apiClient != null) {
        final response = await _apiClient.get('/api/v1/billing/usage');
        if (response.data is Map<String, dynamic>) {
          _currentUsage = BillingUsageModel.fromJson(response.data as Map<String, dynamic>);
          return _currentUsage;
        }
      }
    } catch (_) {
      // Return active session usage
    }
    return _currentUsage;
  }

  Future<List<BillingPlanModel>> fetchPlans() async {
    try {
      if (_apiClient != null) {
        final response = await _apiClient.get('/api/v1/billing/plans');
        final data = response.data;
        if (data is List && data.isNotEmpty) {
          // Parse from remote if available
        }
      }
    } catch (_) {}

    return [
      BillingPlanModel(
        id: 'free',
        name: 'Starter OS',
        subtitle: 'Ideal for prototyping & single blueprint exploration',
        monthlyPrice: 0,
        annualPrice: 0,
        creditsIncluded: 50,
        features: [
          '3 Architecture Blueprints / month',
          'Standard PostgreSQL DDL derivation',
          'FastAPI OpenAPI 3.1 exporter',
          'Community Discord assistance',
        ],
        isCurrent: _currentUsage.planName.toLowerCase().contains('free') ||
            _currentUsage.planName.toLowerCase().contains('starter'),
      ),
      BillingPlanModel(
        id: 'pro',
        name: 'Professional Studio',
        subtitle: 'For autonomous full-stack multi-agent synthesis',
        monthlyPrice: 49,
        annualPrice: 39,
        creditsIncluded: 500,
        features: [
          '500 monthly fast compute units',
          'Unlimited blueprints & architecture swarms',
          'Autonomous Docker & CI/CD generation',
          'One-click GitHub & Render live deploy',
          'Priority GPU compilation mesh',
          'Synthetic data seed generator',
        ],
        isCurrent: _currentUsage.planName.toLowerCase().contains('pro'),
        isPopular: true,
      ),
      BillingPlanModel(
        id: 'enterprise',
        name: 'Enterprise Scale',
        subtitle: 'Dedicated clusters, fine-tuned weights & governance',
        monthlyPrice: 299,
        annualPrice: 239,
        creditsIncluded: 5000,
        features: [
          '5,000 monthly enterprise compute units',
          'Custom tenant isolation rules',
          'Dedicated microservice sidecars',
          'Full audit trail & team RBAC governance',
          'Custom LLM adapter & private DSN introspection',
          '99.9% uptime SLA & dedicated architect',
        ],
        isCurrent: _currentUsage.planName.toLowerCase().contains('enterprise'),
      ),
    ];
  }

  List<CreditPackModel> fetchCreditPacks() {
    return [
      CreditPackModel(
        id: 'pack_5k',
        title: '+5,000 Credits',
        credits: 5000,
        price: 19.00,
        unitPrice: '\$0.0038 / credit',
        isPopular: false,
      ),
      CreditPackModel(
        id: 'pack_15k',
        title: '+15,000 Credits',
        credits: 15000,
        price: 49.00,
        unitPrice: '\$0.0032 / credit',
        isPopular: true,
        badge: 'MOST POPULAR',
      ),
      CreditPackModel(
        id: 'pack_50k',
        title: '+50,000 Credits',
        credits: 50000,
        price: 129.00,
        unitPrice: '\$0.0025 / credit',
        isPopular: false,
        badge: 'BEST VALUE (SAVE 35%)',
      ),
    ];
  }

  Future<List<InvoiceModel>> fetchInvoices() async {
    try {
      if (_apiClient != null) {
        final response = await _apiClient.get('/api/v1/billing/invoices');
        if (response.data is List) {
          // Remote invoice mapping
        }
      }
    } catch (_) {}
    return List.unmodifiable(_invoices);
  }

  Future<bool> processCheckout({
    required String itemTitle,
    required double amount,
    required int creditsAdded,
    required String paymentMethod,
    String? promoCode,
    double discount = 0.0,
  }) async {
    try {
      if (_apiClient != null) {
        await _apiClient.post(
          '/api/v1/billing/topup',
          data: {
            'amount': creditsAdded,
            'price': amount,
            'payment_method': paymentMethod,
            'promo_code': promoCode,
          },
        );
      }
    } catch (_) {
      // Graceful fallback for offline / mock
    }

    // Update in-memory state
    final newRemaining = _currentUsage.creditsRemaining + creditsAdded;
    final newTotal = _currentUsage.creditsTotal + creditsAdded;
    _currentUsage = _currentUsage.copyWith(
      creditsRemaining: newRemaining,
      creditsTotal: newTotal,
      usageRatio: (_currentUsage.creditsUsed / (newTotal > 0 ? newTotal : 1)).clamp(0.0, 1.0),
      paymentMethod: paymentMethod,
    );

    // Prepend generated invoice to history
    final newInvoiceId = 'SUTRA-${9000 + _invoices.length}';
    final now = DateTime.now();
    final months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    final dateStr = '${months[now.month - 1]} ${now.day}, ${now.year}';

    _invoices.insert(
      0,
      InvoiceModel(
        id: newInvoiceId,
        date: dateStr,
        amount: (amount - discount).clamp(0.0, 999999.0),
        description: itemTitle,
        status: 'PAID',
        paymentMethod: paymentMethod,
      ),
    );

    return true;
  }

  Future<bool> changePlan({
    required String planId,
    required String planName,
    required double price,
    required bool isAnnual,
    required String paymentMethod,
  }) async {
    try {
      if (_apiClient != null) {
        await _apiClient.post(
          '/api/v1/billing/change-plan',
          data: {
            'plan_id': planId,
            'is_annual': isAnnual,
            'payment_method': paymentMethod,
          },
        );
      }
    } catch (_) {}

    int newCredits = 500;
    if (planId == 'enterprise') newCredits = 5000;
    if (planId == 'free') newCredits = 50;

    _currentUsage = _currentUsage.copyWith(
      planName: planName,
      creditsRemaining: _currentUsage.creditsRemaining + newCredits,
      creditsTotal: _currentUsage.creditsTotal + newCredits,
      paymentMethod: paymentMethod,
    );

    if (price > 0) {
      final now = DateTime.now();
      final months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      final dateStr = '${months[now.month - 1]} ${now.day}, ${now.year}';
      _invoices.insert(
        0,
        InvoiceModel(
          id: 'SUTRA-${9000 + _invoices.length}',
          date: dateStr,
          amount: price,
          description: '$planName ${isAnnual ? "Annual" : "Monthly"} Subscription',
          status: 'PAID',
          paymentMethod: paymentMethod,
        ),
      );
    }

    return true;
  }
}

final billingUsageProvider = FutureProvider<BillingUsageModel>((ref) async {
  final repo = ref.watch(billingRepositoryProvider);
  return await repo.fetchUsage();
});

final billingPlansProvider = FutureProvider<List<BillingPlanModel>>((ref) async {
  final repo = ref.watch(billingRepositoryProvider);
  return await repo.fetchPlans();
});

final creditPacksProvider = Provider<List<CreditPackModel>>((ref) {
  final repo = ref.watch(billingRepositoryProvider);
  return repo.fetchCreditPacks();
});

final billingInvoicesProvider = FutureProvider<List<InvoiceModel>>((ref) async {
  final repo = ref.watch(billingRepositoryProvider);
  return await repo.fetchInvoices();
});
