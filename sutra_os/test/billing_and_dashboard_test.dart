import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sutra_os/features/billing/data/billing_repository.dart';
import 'package:sutra_os/features/billing/presentation/billing_screen.dart';

void main() {
  test('BillingRepository processCheckout updates credits and generates invoice', () async {
    final repo = BillingRepository();

    final initialUsage = await repo.fetchUsage();
    final initialCredits = initialUsage.creditsRemaining;

    final success = await repo.processCheckout(
      itemTitle: '+5,000 Credits',
      amount: 19.00,
      creditsAdded: 5000,
      paymentMethod: 'Mastercard •••• 4288',
      promoCode: 'SUTRA20',
      discount: 10.00,
    );

    expect(success, isTrue);

    final updatedUsage = await repo.fetchUsage();
    expect(updatedUsage.creditsRemaining, initialCredits + 5000);

    final invoices = await repo.fetchInvoices();
    expect(invoices.isNotEmpty, isTrue);
    expect(invoices.first.amount, 9.00);
    expect(invoices.first.status, 'PAID');
    expect(invoices.first.description, '+5,000 Credits');
  });

  testWidgets('BillingScreen renders Active Plan, Pricing Tiers, and Top-Up Refills',
      (WidgetTester tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    final repo = BillingRepository();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          billingRepositoryProvider.overrideWithValue(repo),
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
  });
}
