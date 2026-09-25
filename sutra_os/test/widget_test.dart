import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sutra_os/core/widgets/sutra_button.dart';
import 'package:sutra_os/core/widgets/sutra_card.dart';
import 'package:sutra_os/core/widgets/sutra_wordmark.dart';

void main() {
  testWidgets('SutraWordmark renders signature brand glyph and tagline',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: SutraWordmark(),
        ),
      ),
    );

    expect(find.text('सूत्र'), findsOneWidget);
    expect(find.text('SUTRA OS'), findsOneWidget);
    expect(
        find.text('Ancient precision. Modern intelligence.'), findsOneWidget);
  });

  testWidgets('SutraButton renders primary CTA with uppercase tracked label',
      (WidgetTester tester) async {
    bool tapped = false;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SutraButton(
            label: 'Build with SUTRA',
            onPressed: () => tapped = true,
          ),
        ),
      ),
    );

    expect(find.text('BUILD WITH SUTRA'), findsOneWidget);
    await tester.tap(find.text('BUILD WITH SUTRA'));
    expect(tapped, isTrue);
  });

  testWidgets('SutraCard renders custom styled container with children',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: SutraCard(
            child: Text('Card Content'),
          ),
        ),
      ),
    );

    expect(find.text('Card Content'), findsOneWidget);
  });
}
