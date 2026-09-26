import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_exceptions.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/widgets/sutra_button.dart';
import '../../../core/widgets/sutra_card.dart';
import '../data/billing_repository.dart';
import '../domain/billing_models.dart';

class BillingScreen extends ConsumerStatefulWidget {
  const BillingScreen({super.key});

  @override
  ConsumerState<BillingScreen> createState() => _BillingScreenState();
}

class _BillingScreenState extends ConsumerState<BillingScreen> {
  bool _isAnnual = false;

  void _openCheckoutSheet({
    required String itemTitle,
    required double basePrice,
    required int credits,
    bool isPlan = false,
    String? planId,
  }) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => _PaymentCheckoutSheet(
        itemTitle: itemTitle,
        basePrice: basePrice,
        credits: credits,
        isPlan: isPlan,
        planId: planId,
        isAnnual: _isAnnual,
        onPaymentSuccess: () {
          ref.invalidate(billingUsageProvider);
          ref.invalidate(billingInvoicesProvider);
          ref.invalidate(billingPlansProvider);
        },
      ),
    );
  }

  void _showInvoiceDetailsDialog(InvoiceModel invoice) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.lightSurface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
          side: const BorderSide(color: AppColors.lightBorder),
        ),
        title: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'INVOICE RECEIPT',
                  style: AppTextStyles.smallCapsLabel(
                    fontSize: 9,
                    color: AppColors.goldDark,
                    letterSpacing: 2.0,
                  ),
                ),
                Text(
                  invoice.id,
                  style: AppTextStyles.serifHeading(fontSize: 18),
                ),
              ],
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: const Color(0xFFEAF4EC),
                borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                border: Border.all(color: const Color(0xFF2E7D32).withValues(alpha: 0.3)),
              ),
              child: Text(
                invoice.status,
                style: AppTextStyles.smallCapsLabel(
                  fontSize: 9,
                  color: const Color(0xFF2E7D32),
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Divider(color: AppColors.lightBorder),
            const SizedBox(height: AppSpacing.sm),
            _buildReceiptRow('Date Issued', invoice.date),
            _buildReceiptRow('Description', invoice.description),
            _buildReceiptRow('Payment Method', invoice.paymentMethod),
            _buildReceiptRow('Tax ID', 'US-EIN-92-4819024'),
            _buildReceiptRow('Subtotal', '\$${invoice.amount.toStringAsFixed(2)}'),
            _buildReceiptRow('Estimated Tax', '\$0.00'),
            const Divider(color: AppColors.lightBorder),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Total Paid',
                  style: AppTextStyles.bodyMedium(
                    color: AppColors.lightTextPrimary,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                Text(
                  '\$${invoice.amount.toStringAsFixed(2)}',
                  style: AppTextStyles.serifHeading(
                    fontSize: 20,
                    color: AppColors.lightTextPrimary,
                  ),
                ),
              ],
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text(
              'CLOSE',
              style: AppTextStyles.smallCapsLabel(color: AppColors.lightTextSecondary),
            ),
          ),
          SutraButton(
            label: 'DOWNLOAD PDF',
            height: 36,
            variant: SutraButtonVariant.primaryBlack,
            icon: const Icon(Icons.download, size: 14, color: Colors.white),
            onPressed: () {
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text('Invoice ${invoice.id}.pdf saved to Downloads.'),
                  duration: const Duration(seconds: 2),
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildReceiptRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: AppTextStyles.bodySmall(color: AppColors.lightTextSecondary)),
          Flexible(
            child: Text(
              value,
              textAlign: TextAlign.end,
              style: AppTextStyles.bodySmall(
                color: AppColors.lightTextPrimary,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final usageAsync = ref.watch(billingUsageProvider);
    final plansAsync = ref.watch(billingPlansProvider);
    final packs = ref.watch(creditPacksProvider);
    final invoicesAsync = ref.watch(billingInvoicesProvider);

    return Scaffold(
      backgroundColor: AppColors.lightBackground,
      body: SafeArea(
        child: RefreshIndicator(
          color: AppColors.blackButton,
          onRefresh: () async {
            ref.invalidate(billingUsageProvider);
            ref.invalidate(billingPlansProvider);
            ref.invalidate(billingInvoicesProvider);
          },
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(
              parent: BouncingScrollPhysics(),
            ),
            slivers: [
              // Sticky Mobile Header & Status Bar
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.lg,
                    vertical: AppSpacing.md,
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'ATELIER COMMERCE • BILLING',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: AppTextStyles.smallCapsLabel(
                                fontSize: 9,
                                color: AppColors.lightTextSecondary,
                                letterSpacing: 1.5,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              'Billing & Plans',
                              style: AppTextStyles.serifHeading(
                                fontSize: 22,
                                color: AppColors.lightTextPrimary,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      // Tappable Credit Pill
                      GestureDetector(
                        onTap: () {
                          final pack = packs.firstWhere((p) => p.isPopular, orElse: () => packs.first);
                          _openCheckoutSheet(
                            itemTitle: pack.title,
                            basePrice: pack.price,
                            credits: pack.credits,
                          );
                        },
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                          decoration: BoxDecoration(
                            color: AppColors.goldSubtle,
                            borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
                            border: Border.all(color: AppColors.gold.withValues(alpha: 0.4)),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.bolt, size: 14, color: AppColors.gold),
                              const SizedBox(width: 4),
                              Text(
                                usageAsync.maybeWhen(
                                  data: (u) => u.isUnlimited
                                      ? 'Unlimited'
                                      : '${u.creditsRemaining} Cr',
                                  orElse: () => '--',
                                ),
                                style: AppTextStyles.smallCapsLabel(
                                  fontSize: 10,
                                  color: AppColors.goldDark,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              // Current Active Subscription Card
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                  child: usageAsync.when(
                    data: (usage) => _buildActiveSubscriptionCard(usage),
                    loading: () => const Center(
                      child: Padding(
                        padding: EdgeInsets.all(AppSpacing.xl),
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: AppColors.blackButton,
                        ),
                      ),
                    ),
                    error: (_, __) => _buildActiveSubscriptionCard(
                      BillingUsageModel.unknown,
                    ),
                  ),
                ),
              ),

              const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.xl)),

              // Billing Cycle Switcher (Monthly vs Annual Toggle)
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                  child: Center(
                    child: Container(
                      padding: const EdgeInsets.all(4),
                      decoration: BoxDecoration(
                        color: const Color(0xFFEFECE3),
                        borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
                        border: Border.all(color: AppColors.lightBorder),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          GestureDetector(
                            onTap: () => setState(() => _isAnnual = false),
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 200),
                              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                              decoration: BoxDecoration(
                                color: !_isAnnual ? Colors.white : Colors.transparent,
                                borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
                                boxShadow: !_isAnnual
                                    ? [
                                        BoxShadow(
                                          color: Colors.black.withValues(alpha: 0.05),
                                          blurRadius: 4,
                                        ),
                                      ]
                                    : null,
                              ),
                              child: Text(
                                'MONTHLY',
                                style: AppTextStyles.smallCapsLabel(
                                  fontSize: 10,
                                  color: !_isAnnual ? AppColors.lightTextPrimary : AppColors.lightTextSecondary,
                                  fontWeight: !_isAnnual ? FontWeight.w700 : FontWeight.w500,
                                ),
                              ),
                            ),
                          ),
                          GestureDetector(
                            onTap: () => setState(() => _isAnnual = true),
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 200),
                              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                              decoration: BoxDecoration(
                                color: _isAnnual ? Colors.white : Colors.transparent,
                                borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
                                boxShadow: _isAnnual
                                    ? [
                                        BoxShadow(
                                          color: Colors.black.withValues(alpha: 0.05),
                                          blurRadius: 4,
                                        ),
                                      ]
                                    : null,
                              ),
                              child: Row(
                                children: [
                                  Text(
                                    'ANNUAL',
                                    style: AppTextStyles.smallCapsLabel(
                                      fontSize: 10,
                                      color: _isAnnual ? AppColors.lightTextPrimary : AppColors.lightTextSecondary,
                                      fontWeight: _isAnnual ? FontWeight.w700 : FontWeight.w500,
                                    ),
                                  ),
                                  const SizedBox(width: 6),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: AppColors.gold,
                                      borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
                                    ),
                                    child: const Text(
                                      'SAVE 20%',
                                      style: TextStyle(
                                        color: Colors.white,
                                        fontSize: 8,
                                        fontWeight: FontWeight.bold,
                                        letterSpacing: 0.5,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),

              const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.lg)),

              // 3-Tier Pricing Cards List
              plansAsync.when(
                data: (plans) => SliverPadding(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                  sliver: SliverList(
                    delegate: SliverChildBuilderDelegate(
                      (context, index) {
                        final plan = plans[index];
                        return Padding(
                          padding: const EdgeInsets.only(bottom: AppSpacing.md),
                          child: _buildTierPricingCard(plan),
                        );
                      },
                      childCount: plans.length,
                    ),
                  ),
                ),
                loading: () => const SliverToBoxAdapter(
                  child: Center(
                    child: CircularProgressIndicator(color: AppColors.blackButton),
                  ),
                ),
                error: (_, __) => const SliverToBoxAdapter(
                  child: Center(child: Text('Unable to load plans')),
                ),
              ),

              const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.xl)),

              // On-Demand Credit Top-Ups (Instant Refill)
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Text(
                              'ON-DEMAND RECHARGE',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: AppTextStyles.smallCapsLabel(
                                fontSize: 10,
                                color: AppColors.gold,
                                letterSpacing: 1.5,
                              ),
                            ),
                          ),
                          const SizedBox(width: AppSpacing.xs),
                          Text(
                            'INSTANT COMPUTATION',
                            style: AppTextStyles.smallCapsLabel(
                              fontSize: 8.5,
                              color: AppColors.lightTextSecondary,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        'Instant Compute Refills',
                        style: AppTextStyles.serifHeading(
                          fontSize: 20,
                          color: AppColors.lightTextPrimary,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        'Boost your synthesis bandwidth for immediate multi-agent Swarm reasoning and zero-downtime deployment pipelines.',
                        style: AppTextStyles.bodySmall(color: AppColors.lightTextSecondary),
                      ),
                      const SizedBox(height: AppSpacing.md),
                      ...packs.map((pack) => Padding(
                            padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                            child: _buildPackCard(pack),
                          )),
                    ],
                  ),
                ),
              ),

              const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.xl)),

              // Past Invoices & Billing History Section
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Text(
                              'AUDIT LEDGER',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: AppTextStyles.smallCapsLabel(
                                fontSize: 10,
                                color: AppColors.gold,
                                letterSpacing: 1.5,
                              ),
                            ),
                          ),
                          const SizedBox(width: AppSpacing.xs),
                          Text(
                            '256-BIT ENCRYPTED',
                            style: AppTextStyles.smallCapsLabel(
                              fontSize: 8.5,
                              color: AppColors.lightTextSecondary,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        'Past Invoices & Receipts',
                        style: AppTextStyles.serifHeading(
                          fontSize: 20,
                          color: AppColors.lightTextPrimary,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.md),
                    ],
                  ),
                ),
              ),

              // Invoices List
              invoicesAsync.when(
                data: (invoices) => SliverPadding(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                  sliver: SliverList(
                    delegate: SliverChildBuilderDelegate(
                      (context, index) {
                        final invoice = invoices[index];
                        return Padding(
                          padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: AppSpacing.md,
                              vertical: AppSpacing.sm,
                            ),
                            decoration: BoxDecoration(
                              color: AppColors.lightSurface,
                              borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                              border: Border.all(color: AppColors.lightBorder),
                            ),
                            child: Row(
                              children: [
                                const Icon(
                                  Icons.receipt_long_outlined,
                                  size: 20,
                                  color: AppColors.gold,
                                ),
                                const SizedBox(width: AppSpacing.md),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        children: [
                                          Text(
                                            invoice.id,
                                            style: AppTextStyles.mono(
                                              fontSize: 12,
                                              color: AppColors.lightTextPrimary,
                                              fontWeight: FontWeight.w600,
                                            ),
                                          ),
                                          const SizedBox(width: 8),
                                          Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                            decoration: BoxDecoration(
                                              color: const Color(0xFFEAF4EC),
                                              borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                                            ),
                                            child: Text(
                                              invoice.status,
                                              style: AppTextStyles.smallCapsLabel(
                                                fontSize: 8,
                                                color: const Color(0xFF2E7D32),
                                                fontWeight: FontWeight.w700,
                                              ),
                                            ),
                                          ),
                                        ],
                                      ),
                                      Text(
                                        '${invoice.date} • ${invoice.description}',
                                        style: AppTextStyles.bodySmall(
                                          color: AppColors.lightTextSecondary,
                                          fontSize: 11,
                                        ),
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ],
                                  ),
                                ),
                                Column(
                                  crossAxisAlignment: CrossAxisAlignment.end,
                                  children: [
                                    Text(
                                      '\$${invoice.amount.toStringAsFixed(2)}',
                                      style: AppTextStyles.serifHeading(
                                        fontSize: 16,
                                        color: AppColors.lightTextPrimary,
                                      ),
                                    ),
                                    IconButton(
                                      icon: const Icon(
                                        Icons.open_in_new,
                                        size: 14,
                                        color: AppColors.lightTextSecondary,
                                      ),
                                      padding: EdgeInsets.zero,
                                      constraints: const BoxConstraints(),
                                      tooltip: 'View Receipt',
                                      onPressed: () => _showInvoiceDetailsDialog(invoice),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                      childCount: invoices.length,
                    ),
                  ),
                ),
                loading: () => const SliverToBoxAdapter(
                  child: Center(child: CircularProgressIndicator(color: AppColors.blackButton)),
                ),
                error: (_, __) => const SliverToBoxAdapter(
                  child: Center(child: Text('No past invoices available.')),
                ),
              ),

              const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.xxl)),
            ],
          ),
        ),
      ),
    );
  }

  /// `/billing/usage` does not return renewal or payment details, so the line
  /// under the plan name only shows them when the API actually supplies them.
  String _subscriptionFootnote(BillingUsageModel usage) {
    if (usage.renewalDate != null && usage.paymentMethod != null) {
      return 'Renews on ${usage.renewalDate} via ${usage.paymentMethod}';
    }
    if (usage.isUnlimited) {
      return 'Unlimited compute • no renewal required';
    }
    return 'Live balance from the billing ledger';
  }

  // Active Subscription Card
  Widget _buildActiveSubscriptionCard(BillingUsageModel usage) {
    return SutraCard(
      padding: const EdgeInsets.all(AppSpacing.xl),
      borderColor: AppColors.gold,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  'CURRENT ACTIVE PLAN',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.smallCapsLabel(
                    fontSize: 10,
                    color: AppColors.goldDark,
                    letterSpacing: 1.5,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              const SizedBox(width: AppSpacing.xs),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AppColors.goldBadgeBg,
                  borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                  border: Border.all(color: AppColors.gold.withValues(alpha: 0.4)),
                ),
                child: Text(
                  'CURRENT PLAN',
                  style: AppTextStyles.smallCapsLabel(
                    fontSize: 9,
                    color: AppColors.goldDark,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            usage.planName,
            style: AppTextStyles.serifHeading(
              fontSize: 22,
              color: AppColors.lightTextPrimary,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            _subscriptionFootnote(usage),
            style: AppTextStyles.bodySmall(
              color: AppColors.lightTextSecondary,
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                usage.isUnlimited
                    ? 'Compute Credits: unlimited'
                    : 'Compute Credits: ${usage.creditsRemaining} / ${usage.creditsTotal}',
                style: AppTextStyles.bodyMedium(
                  color: AppColors.lightTextPrimary,
                  fontWeight: FontWeight.w600,
                ),
              ),
              if (usage.resetsInDays != null)
                Text(
                  'Resets in ${usage.resetsInDays} days',
                  style: AppTextStyles.bodySmall(color: AppColors.goldDark),
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          ClipRRect(
            borderRadius: BorderRadius.circular(2),
            child: LinearProgressIndicator(
              value: usage.usageRatio.clamp(0.0, 1.0),
              minHeight: 6,
              backgroundColor: AppColors.lightSurfaceSubtle,
              valueColor: const AlwaysStoppedAnimation<Color>(AppColors.gold),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          GestureDetector(
            onTap: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('VAT / Tax ID and billing address are up to date.'),
                ),
              );
            },
            child: Text(
              'Manage billing details & tax ID →',
              style: AppTextStyles.smallCapsLabel(
                fontSize: 10,
                color: AppColors.goldDark,
                letterSpacing: 1.0,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // Tier Pricing Card
  Widget _buildTierPricingCard(BillingPlanModel plan) {
    final priceStr = plan.getPriceDisplay(_isAnnual);

    return SutraCard(
      padding: const EdgeInsets.all(AppSpacing.xl),
      borderColor: plan.isCurrent
          ? AppColors.gold
          : (plan.isPopular ? AppColors.blackButton : AppColors.lightBorder),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                plan.name.toUpperCase(),
                style: AppTextStyles.smallCapsLabel(
                  fontSize: 11,
                  color: plan.isCurrent ? AppColors.goldDark : AppColors.lightTextPrimary,
                  letterSpacing: 2.0,
                  fontWeight: FontWeight.w700,
                ),
              ),
              if (plan.isCurrent)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppColors.goldBadgeBg,
                    borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                  ),
                  child: Text(
                    'ACTIVE',
                    style: AppTextStyles.smallCapsLabel(
                      fontSize: 9,
                      color: AppColors.goldDark,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                )
              else if (plan.isPopular)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppColors.blackButton,
                    borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                  ),
                  child: const Text(
                    'MOST POPULAR',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 8,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 1.0,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            plan.subtitle,
            style: AppTextStyles.bodySmall(color: AppColors.lightTextSecondary),
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                priceStr,
                style: AppTextStyles.serifHeading(
                  fontSize: 32,
                  color: AppColors.lightTextPrimary,
                ),
              ),
              const SizedBox(width: 4),
              Text(
                _isAnnual ? '/mo (billed annually)' : '/month',
                style: AppTextStyles.bodySmall(color: AppColors.lightTextSecondary),
              ),
            ],
          ),
          Text(
            '${plan.creditsIncluded} credits included every cycle',
            style: AppTextStyles.bodySmall(
              color: AppColors.goldDark,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          ...plan.features.map(
            (f) => Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                children: [
                  const Icon(Icons.check, size: 15, color: AppColors.gold),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Text(
                      f,
                      style: AppTextStyles.bodySmall(color: AppColors.lightTextPrimary),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          SutraButton(
            label: plan.isCurrent
                ? 'CURRENT ACTIVE PLAN'
                : 'UPGRADE TO ${plan.name.toUpperCase()}',
            height: 44,
            width: double.infinity,
            variant: plan.isCurrent
                ? SutraButtonVariant.secondaryOutline
                : SutraButtonVariant.primaryBlack,
            onPressed: plan.isCurrent
                ? null
                : () {
                    final price = _isAnnual ? plan.annualPrice * 12 : plan.monthlyPrice;
                    _openCheckoutSheet(
                      itemTitle: '${plan.name} (${_isAnnual ? "Annual" : "Monthly"})',
                      basePrice: price,
                      credits: plan.creditsIncluded,
                      isPlan: true,
                      planId: plan.id,
                    );
                  },
          ),
        ],
      ),
    );
  }

  // Pack Card
  Widget _buildPackCard(CreditPackModel pack) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.lightSurface,
        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
        border: Border.all(
          color: pack.isPopular ? AppColors.gold : AppColors.lightBorder,
          width: pack.isPopular ? 1.5 : 1.0,
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: pack.isPopular ? AppColors.goldSubtle : AppColors.lightSurfaceSubtle,
              borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
            ),
            child: Icon(
              Icons.bolt,
              color: pack.isPopular ? AppColors.gold : AppColors.lightTextSecondary,
              size: 22,
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (pack.badge != null)
                  Text(
                    pack.badge!,
                    style: AppTextStyles.smallCapsLabel(
                      fontSize: 8,
                      color: AppColors.goldDark,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                Text(
                  pack.title,
                  style: AppTextStyles.bodyMedium(
                    color: AppColors.lightTextPrimary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                Text(
                  pack.unitPrice,
                  style: AppTextStyles.bodySmall(color: AppColors.lightTextSecondary),
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '\$${pack.price.toStringAsFixed(0)}',
                style: AppTextStyles.serifHeading(fontSize: 20),
              ),
              const SizedBox(height: 4),
              SutraButton(
                label: 'Quick Buy',
                height: 32,
                variant: pack.isPopular
                    ? SutraButtonVariant.primaryBlack
                    : SutraButtonVariant.secondaryOutline,
                onPressed: () {
                  _openCheckoutSheet(
                    itemTitle: pack.title,
                    basePrice: pack.price,
                    credits: pack.credits,
                  );
                },
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ==========================================
// INTERACTIVE PAYMENT CHECKOUT SHEET
// ==========================================
class _PaymentCheckoutSheet extends ConsumerStatefulWidget {
  final String itemTitle;
  final double basePrice;
  final int credits;
  final bool isPlan;
  final String? planId;
  final bool isAnnual;
  final VoidCallback onPaymentSuccess;

  const _PaymentCheckoutSheet({
    required this.itemTitle,
    required this.basePrice,
    required this.credits,
    this.isPlan = false,
    this.planId,
    this.isAnnual = false,
    required this.onPaymentSuccess,
  });

  @override
  ConsumerState<_PaymentCheckoutSheet> createState() => _PaymentCheckoutSheetState();
}

class _PaymentCheckoutSheetState extends ConsumerState<_PaymentCheckoutSheet> {
  int _paymentMethodTab = 0; // 0: Credit Card, 1: UPI / GPay
  final _promoController = TextEditingController();
  final _cardNumberController = TextEditingController(text: '4242 •••• •••• 4288');
  final _expiryController = TextEditingController(text: '08/29');
  final _cvcController = TextEditingController(text: '882');
  final _cardholderController = TextEditingController(text: 'Architect Studio');
  final _upiIdController = TextEditingController(text: 'sutra@okaxis');

  double _discount = 0.0;
  String? _appliedPromo;
  bool _isProcessing = false;

  void _applyPromo() {
    final code = _promoController.text.trim().toUpperCase();
    if (code == 'SUTRA20' || code == 'SUTRAEARLY' || code == 'VIP10') {
      setState(() {
        _discount = 10.0;
        _appliedPromo = code;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Promo $code applied! \$10.00 discount granted.'),
          backgroundColor: const Color(0xFF2E7D32),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Invalid promo code. Try SUTRA20.')),
      );
    }
  }

  Future<void> _submitPayment() async {
    setState(() => _isProcessing = true);
    final repo = ref.read(billingRepositoryProvider);

    final finalAmount = (widget.basePrice - _discount).clamp(0.0, 999999.0);

    try {
      if (widget.isPlan && widget.planId != null) {
        await repo.changePlan(planId: widget.planId!);
      } else {
        await repo.purchaseCredits(widget.credits);
      }
    } catch (e) {
      // Previously every failure was swallowed and a "Payment Confirmed" dialog
      // was shown anyway, so the credits on screen never matched the backend.
      if (!mounted) return;
      setState(() => _isProcessing = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(e is ApiException ? e.message : e.toString()),
          backgroundColor: AppColors.statusErrorRed,
        ),
      );
      return;
    }

    if (mounted) {
      setState(() => _isProcessing = false);
      widget.onPaymentSuccess();
      Navigator.pop(context); // Close sheet

      // Show celebratory confirmation
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          backgroundColor: AppColors.lightSurface,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
            side: const BorderSide(color: AppColors.gold),
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 60,
                height: 60,
                decoration: const BoxDecoration(
                  color: Color(0xFFEAF4EC),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.check, color: Color(0xFF2E7D32), size: 36),
              ),
              const SizedBox(height: AppSpacing.md),
              Text(
                'Payment Confirmed',
                style: AppTextStyles.serifHeading(fontSize: 22),
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                'Successfully processed \$${finalAmount.toStringAsFixed(2)} for ${widget.itemTitle}. Your account ledger has been credited.',
                textAlign: TextAlign.center,
                style: AppTextStyles.bodySmall(color: AppColors.lightTextSecondary),
              ),
              const SizedBox(height: AppSpacing.lg),
              SutraButton(
                label: 'CONTINUE TO WORKSPACE',
                height: 42,
                width: double.infinity,
                variant: SutraButtonVariant.primaryBlack,
                onPressed: () => Navigator.pop(ctx),
              ),
            ],
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final finalAmount = (widget.basePrice - _discount).clamp(0.0, 999999.0);

    return Container(
      decoration: const BoxDecoration(
        color: AppColors.lightSurface,
        borderRadius: BorderRadius.vertical(top: Radius.circular(AppSpacing.radiusMd)),
      ),
      padding: EdgeInsets.only(
        top: AppSpacing.lg,
        left: AppSpacing.lg,
        right: AppSpacing.lg,
        bottom: MediaQuery.of(context).viewInsets.bottom + AppSpacing.xl,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Handle bar
            Center(
              child: Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: AppColors.lightBorder,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.md),

            // Header
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'SECURE CHECKOUT',
                      style: AppTextStyles.smallCapsLabel(
                        fontSize: 9,
                        color: AppColors.goldDark,
                        letterSpacing: 2.0,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    Text(
                      widget.itemTitle,
                      style: AppTextStyles.serifHeading(fontSize: 18),
                    ),
                  ],
                ),
                IconButton(
                  icon: const Icon(Icons.close, size: 20),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
            const Divider(color: AppColors.lightBorder),
            const SizedBox(height: AppSpacing.sm),

            // Payment method selector tabs
            Row(
              children: [
                Expanded(
                  child: GestureDetector(
                    onTap: () => setState(() => _paymentMethodTab = 0),
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      decoration: BoxDecoration(
                        color: _paymentMethodTab == 0 ? AppColors.goldSubtle : AppColors.lightSurfaceSubtle,
                        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                        border: Border.all(
                          color: _paymentMethodTab == 0 ? AppColors.gold : AppColors.lightBorder,
                        ),
                      ),
                      alignment: Alignment.center,
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.credit_card, size: 16, color: AppColors.lightTextPrimary),
                          const SizedBox(width: 6),
                          Text(
                            'Card',
                            style: AppTextStyles.smallCapsLabel(
                              fontSize: 10,
                              color: AppColors.lightTextPrimary,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: GestureDetector(
                    onTap: () => setState(() => _paymentMethodTab = 1),
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      decoration: BoxDecoration(
                        color: _paymentMethodTab == 1 ? AppColors.goldSubtle : AppColors.lightSurfaceSubtle,
                        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                        border: Border.all(
                          color: _paymentMethodTab == 1 ? AppColors.gold : AppColors.lightBorder,
                        ),
                      ),
                      alignment: Alignment.center,
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.account_balance_wallet_outlined, size: 16, color: AppColors.lightTextPrimary),
                          const SizedBox(width: 6),
                          Text(
                            'UPI / GPay',
                            style: AppTextStyles.smallCapsLabel(
                              fontSize: 10,
                              color: AppColors.lightTextPrimary,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),

            // Payment Fields based on tab
            if (_paymentMethodTab == 0) ...[
              TextField(
                controller: _cardholderController,
                style: AppTextStyles.bodyMedium(color: AppColors.lightTextPrimary),
                decoration: const InputDecoration(
                  labelText: 'Cardholder Name',
                  isDense: true,
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              TextField(
                controller: _cardNumberController,
                style: AppTextStyles.mono(fontSize: 13, color: AppColors.lightTextPrimary),
                decoration: const InputDecoration(
                  labelText: 'Card Number',
                  prefixIcon: Icon(Icons.payment, size: 18, color: AppColors.gold),
                  isDense: true,
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _expiryController,
                      style: AppTextStyles.mono(fontSize: 13, color: AppColors.lightTextPrimary),
                      decoration: const InputDecoration(
                        labelText: 'Expires (MM/YY)',
                        isDense: true,
                      ),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: TextField(
                      controller: _cvcController,
                      obscureText: true,
                      style: AppTextStyles.mono(fontSize: 13, color: AppColors.lightTextPrimary),
                      decoration: const InputDecoration(
                        labelText: 'CVC',
                        isDense: true,
                      ),
                    ),
                  ),
                ],
              ),
            ] else ...[
              TextField(
                controller: _upiIdController,
                style: AppTextStyles.mono(fontSize: 13, color: AppColors.lightTextPrimary),
                decoration: const InputDecoration(
                  labelText: 'VPA / UPI ID',
                  hintText: 'username@bank',
                  prefixIcon: Icon(Icons.send_to_mobile, size: 18, color: AppColors.gold),
                  isDense: true,
                ),
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                'Supports Google Pay, PhonePe, Paytm & BHIM instant verification.',
                style: AppTextStyles.bodySmall(color: AppColors.lightTextSecondary),
              ),
            ],

            const SizedBox(height: AppSpacing.md),

            // Promo Code row
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _promoController,
                    style: AppTextStyles.mono(fontSize: 12, color: AppColors.lightTextPrimary),
                    decoration: InputDecoration(
                      hintText: 'Promo code (e.g. SUTRA20)',
                      hintStyle: AppTextStyles.bodySmall(color: AppColors.lightTextMuted),
                      isDense: true,
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                SutraButton(
                  label: 'APPLY',
                  height: 44,
                  variant: SutraButtonVariant.secondaryOutline,
                  onPressed: _applyPromo,
                ),
              ],
            ),

            if (_appliedPromo != null) ...[
              const SizedBox(height: 4),
              Row(
                children: [
                  const Icon(Icons.check_circle, size: 14, color: Color(0xFF2E7D32)),
                  const SizedBox(width: 4),
                  Text(
                    'Applied: $_appliedPromo (-\$10.00)',
                    style: AppTextStyles.bodySmall(color: const Color(0xFF2E7D32)),
                  ),
                ],
              ),
            ],

            const SizedBox(height: AppSpacing.md),
            const Divider(color: AppColors.lightBorder),

            // Order Summary
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('Subtotal', style: AppTextStyles.bodySmall(color: AppColors.lightTextSecondary)),
                Text('\$${widget.basePrice.toStringAsFixed(2)}', style: AppTextStyles.bodySmall()),
              ],
            ),
            if (_discount > 0)
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('Promotional Discount', style: AppTextStyles.bodySmall(color: const Color(0xFF2E7D32))),
                  Text('-\$${_discount.toStringAsFixed(2)}', style: AppTextStyles.bodySmall(color: const Color(0xFF2E7D32))),
                ],
              ),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('Estimated Tax (0%)', style: AppTextStyles.bodySmall(color: AppColors.lightTextSecondary)),
                Text('\$0.00', style: AppTextStyles.bodySmall()),
              ],
            ),
            const SizedBox(height: 6),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Total Due Today',
                  style: AppTextStyles.bodyMedium(
                    color: AppColors.lightTextPrimary,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                Text(
                  '\$${finalAmount.toStringAsFixed(2)}',
                  style: AppTextStyles.serifHeading(
                    fontSize: 24,
                    color: AppColors.lightTextPrimary,
                  ),
                ),
              ],
            ),

            const SizedBox(height: AppSpacing.lg),

            // Confirm & Pay button
            SutraButton(
              label: _isProcessing
                  ? 'PROCESSING SECURE PAYMENT...'
                  : 'CONFIRM & PAY \$${finalAmount.toStringAsFixed(2)}',
              height: 48,
              width: double.infinity,
              variant: SutraButtonVariant.primaryBlack,
              isLoading: _isProcessing,
              icon: const Icon(Icons.lock, size: 16, color: Colors.white),
              onPressed: _isProcessing ? null : _submitPayment,
            ),
            const SizedBox(height: AppSpacing.sm),

            // Footnote
            Center(
              child: Text(
                '256-bit SSL encrypted • Instant compute allocation • Cancel anytime',
                style: AppTextStyles.bodySmall(
                  fontSize: 10,
                  color: AppColors.lightTextMuted,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
