class BillingUsageModel {
  final String planName;
  final int creditsRemaining;
  final int creditsUsed;
  final int creditsTotal;
  final double usageRatio;
  final String renewalDate;
  final String paymentMethod;
  final int resetsInDays;

  BillingUsageModel({
    required this.planName,
    required this.creditsRemaining,
    required this.creditsUsed,
    required this.creditsTotal,
    required this.usageRatio,
    this.renewalDate = 'Nov 14, 2026',
    this.paymentMethod = 'Mastercard •••• 4288',
    this.resetsInDays = 12,
  });

  factory BillingUsageModel.fromJson(Map<String, dynamic> json) {
    final remaining = json['credits_remaining'] is int
        ? json['credits_remaining'] as int
        : (json['credits'] is int ? json['credits'] as int : 420);
    final total = json['credits_total'] is int ? json['credits_total'] as int : 500;
    final used = json['credits_used'] is int
        ? json['credits_used'] as int
        : (total - remaining).clamp(0, total);
    final ratio = total > 0 ? (used / total) : 0.16;

    return BillingUsageModel(
      planName: json['plan']?.toString() ?? 'Professional Studio',
      creditsRemaining: remaining,
      creditsUsed: used,
      creditsTotal: total,
      usageRatio: ratio,
      renewalDate: json['renewal_date']?.toString() ?? 'Nov 14, 2026',
      paymentMethod: json['payment_method']?.toString() ?? 'Mastercard •••• 4288',
      resetsInDays: json['resets_in_days'] is int ? json['resets_in_days'] as int : 12,
    );
  }

  BillingUsageModel copyWith({
    String? planName,
    int? creditsRemaining,
    int? creditsUsed,
    int? creditsTotal,
    double? usageRatio,
    String? renewalDate,
    String? paymentMethod,
    int? resetsInDays,
  }) {
    return BillingUsageModel(
      planName: planName ?? this.planName,
      creditsRemaining: creditsRemaining ?? this.creditsRemaining,
      creditsUsed: creditsUsed ?? this.creditsUsed,
      creditsTotal: creditsTotal ?? this.creditsTotal,
      usageRatio: usageRatio ?? this.usageRatio,
      renewalDate: renewalDate ?? this.renewalDate,
      paymentMethod: paymentMethod ?? this.paymentMethod,
      resetsInDays: resetsInDays ?? this.resetsInDays,
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

  CreditPackModel({
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
  final String status; // 'PAID', 'PENDING'
  final String paymentMethod;
  final String? pdfUrl;

  InvoiceModel({
    required this.id,
    required this.date,
    required this.amount,
    required this.description,
    required this.status,
    required this.paymentMethod,
    this.pdfUrl,
  });
}
