import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../core/network/api_exceptions.dart';
import '../../../core/network/json_utils.dart';
import '../domain/billing_models.dart';

final billingRepositoryProvider = Provider<BillingRepository>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return BillingRepository(apiClient: apiClient);
});

/// Read/act layer for billing.
///
/// Deliberately stateless: the previous version cached credits and invoices in
/// fields, so a refetch mixed server truth with values mutated locally and the
/// screen kept rendering numbers that no longer existed anywhere. The providers
/// below own the state; this class only talks to the API.
class BillingRepository {
  final ApiClient _apiClient;

  BillingRepository({required ApiClient apiClient}) : _apiClient = apiClient;

  Future<BillingUsageModel> fetchUsage() async {
    final response = await _apiClient.get(ApiEndpoints.billingUsage);
    return BillingUsageModel.fromJson(asMap(response.data));
  }

  /// `/billing/plans` returns `{id, name, price_usd, monthly_credits, features}`.
  /// The API exposes a single monthly price, so the annual figure mirrors it
  /// rather than being invented.
  Future<List<BillingPlanModel>> fetchPlans({String? currentPlanName}) async {
    final response = await _apiClient.get(ApiEndpoints.billingPlans);
    final current = (currentPlanName ?? '').toLowerCase();

    return asList(response.data).map(asMap).map((json) {
      final id = pick(json, ['id'], asString, '');
      final price = asDouble(json['price_usd']);
      return BillingPlanModel(
        id: id,
        name: pick(json, ['name'], asString, id),
        subtitle: pick(json, ['subtitle', 'description'], asString, ''),
        monthlyPrice: price,
        annualPrice: price,
        creditsIncluded: asInt(json['monthly_credits']),
        features: asList(json['features']).map(asString).toList(),
        isCurrent: current.isNotEmpty && current.contains(id),
        isPopular: id == 'pro',
      );
    }).toList();
  }

  List<CreditPackModel> fetchCreditPacks() {
    return const [
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

  /// `GET /billing/transactions` returns the credit ledger:
  /// `{id, amount, action, description, created_at}`.
  Future<List<InvoiceModel>> fetchInvoices() async {
    final response = await _apiClient.get(ApiEndpoints.billingTransactions);
    return asList(response.data).map(asMap).map((json) {
      final amount = asInt(json['amount']);
      return InvoiceModel(
        id: asId(json['id']),
        date: asDisplayDate(json['created_at']),
        amount: amount.toDouble(),
        description: pick(json, ['description', 'action'], asString, 'Credit transaction'),
        // Credit ledger entries are debits, not card charges.
        status: 'SETTLED',
        paymentMethod: 'Credits',
      );
    }).toList();
  }

  /// `POST /billing/topup` accepts only `{amount}` and is admin-gated, so a
  /// non-admin caller gets a 403. That is surfaced rather than swallowed, which
  /// is what previously made a failed purchase look successful.
  Future<void> purchaseCredits(int credits) async {
    if (credits <= 0) {
      throw ApiException(message: 'Credit amount must be positive.');
    }
    await _apiClient.post(
      ApiEndpoints.billingTopup,
      data: {'amount': credits},
    );
  }

  /// There is no plan-change endpoint on the backend. Rather than POST to a
  /// 404 and report success, this fails loudly.
  Future<void> changePlan({required String planId}) async {
    throw ApiException(
      message: 'Plan changes are not enabled on this deployment.',
    );
  }
}

final billingUsageProvider = FutureProvider<BillingUsageModel>((ref) async {
  final repo = ref.watch(billingRepositoryProvider);
  return await repo.fetchUsage();
});

final billingPlansProvider = FutureProvider<List<BillingPlanModel>>((ref) async {
  final repo = ref.watch(billingRepositoryProvider);
  // Derive the "current plan" badge from live usage so it cannot drift.
  final usage = await ref.watch(billingUsageProvider.future);
  return await repo.fetchPlans(currentPlanName: usage.planName);
});

final creditPacksProvider = Provider<List<CreditPackModel>>((ref) {
  final repo = ref.watch(billingRepositoryProvider);
  return repo.fetchCreditPacks();
});

final billingInvoicesProvider = FutureProvider<List<InvoiceModel>>((ref) async {
  final repo = ref.watch(billingRepositoryProvider);
  return await repo.fetchInvoices();
});
