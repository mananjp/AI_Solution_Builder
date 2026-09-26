import '../../../core/network/json_utils.dart';

/// Mirrors `GET /api/v1/billing/usage`.
///
/// A `null` balance means the organization is unlimited (demo / anonymous
/// accounts), so every credit field is nullable rather than defaulting to a
/// fabricated number.
class BillingUsageModel {
  final String planName;

  /// `null` = unlimited.
  final int? creditsRemaining;
  final int? creditsUsed;

  /// Monthly allowance. `null` = unlimited.
  final int? creditsTotal;
  final double usageRatio;
  final String? renewalDate;
  final String? paymentMethod;
  final int? resetsInDays;

  const BillingUsageModel({
    required this.planName,
    this.creditsRemaining,
    this.creditsUsed,
    this.creditsTotal,
    this.usageRatio = 0,
    this.renewalDate,
    this.paymentMethod,
    this.resetsInDays,
  });

  bool get isUnlimited => creditsRemaining == null;

  /// Placeholder for the error state, so a failed fetch never renders invented
  /// figures as if they were real.
  static const unknown = BillingUsageModel(planName: 'Unavailable');

  factory BillingUsageModel.fromJson(Map<String, dynamic> json) {
    final balance =
        asIntOrNull(json['current_balance']) ?? asIntOrNull(json['credits_remaining']);
    final total = asIntOrNull(json['monthly_limit']) ?? asIntOrNull(json['credits_total']);
    final used = asIntOrNull(json['credits_used']);

    final ratio = (balance != null && total != null && total > 0)
        ? ((used ?? (total - balance)) / total).clamp(0.0, 1.0)
        : 0.0;

    return BillingUsageModel(
      planName: pick(json, ['plan_name', 'plan'], asString, 'Free'),
      creditsRemaining: balance,
      creditsUsed: used ?? (balance != null && total != null ? total - balance : null),
      creditsTotal: total,
      usageRatio: ratio,
      renewalDate: asStringOrNull(json['renewal_date']),
      paymentMethod: asStringOrNull(json['payment_method']),
      resetsInDays: asIntOrNull(json['resets_in_days']),
    );
  }
}

class BillingPlanModel {
  final String id;
  final String name;
  final String subtitle;
  final double monthlyPrice;
  final double annualPrice;
  final int creditsIncluded;
  final List<String> features;
  final bool isCurrent;
  final bool isPopular;

  BillingPlanModel({
    required this.id,
    required this.name,
    required this.subtitle,
    required this.monthlyPrice,
    required this.annualPrice,
    required this.creditsIncluded,
    required this.features,
    this.isCurrent = false,
    this.isPopular = false,
  });

  String getPriceDisplay(bool isAnnual) {
    if (monthlyPrice == 0) return '\$0';
    return isAnnual
        ? '\$${annualPrice.toStringAsFixed(0)}'
        : '\$${monthlyPrice.toStringAsFixed(0)}';
  }

  String get price => '\$${monthlyPrice.toStringAsFixed(0)}';
  String get interval => '/mo';
}

class CreditPackModel {
  final String id;
  final String title;
  final int credits;
  final double price;
  final String unitPrice;
  final bool isPopular;
  final String? badge;

  const CreditPackModel({
    required this.id,
    required this.title,
    required this.credits,
    required this.price,
    required this.unitPrice,
    this.isPopular = false,
    this.badge,
  });
}

class InvoiceModel {
  final String id;
  final String date;
  final double amount;
  final String description;
  final String status; // 'SETTLED', 'PENDING'
  final String paymentMethod;
  final String? pdfUrl;

  const InvoiceModel({
    required this.id,
    required this.date,
    required this.amount,
    required this.description,
    required this.status,
    required this.paymentMethod,
    this.pdfUrl,
  });
}
