import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sutra_os/core/theme/app_colors.dart';
import 'package:sutra_os/core/widgets/sutra_card.dart';
import 'package:sutra_os/features/workspace/domain/workspace_models.dart';
import 'package:sutra_os/features/workspace/presentation/artifact_visual_views.dart';
import 'package:sutra_os/features/workspace/presentation/markdown_artifact_view.dart';

ArtifactModel _artifact({
  required String type,
  Map<String, dynamic> content = const {},
  String? text,
  String title = 'Artifact',
}) {
  return ArtifactModel(
    id: 'a1',
    solutionId: 's1',
    artifactType: type,
    title: title,
    content: content,
    contentText: text,
  );
}

Widget _host(Widget child) {
  return ProviderScope(
    child: MaterialApp(
      home: Scaffold(
        backgroundColor: AppColors.lightBackground,
        body: SingleChildScrollView(
          child: SizedBox(width: 500, child: child),
        ),
      ),
    ),
  );
}

void main() {
  group('MarkdownArtifactView', () {
    testWidgets('renders a table and keeps the paragraph that follows it',
        (tester) async {
      const source = '''
Intro paragraph.

| Endpoint | Method | Auth |
| --- | --- | --- |
| /health | GET | no |
| /builds | POST | yes |

Trailing paragraph must survive.
''';

      await tester.pumpWidget(_host(MarkdownArtifactView(content: source)));
      await tester.pumpAndSettle();

      // Header + both rows.
      expect(find.text('Endpoint'), findsOneWidget);
      expect(find.text('Method'), findsOneWidget);
      expect(find.text('/health'), findsOneWidget);
      expect(find.text('/builds'), findsOneWidget);

      // The bug this guards: the line after a table used to be swallowed by
      // the row loop's index juggling.
      expect(find.text('Trailing paragraph must survive.'), findsOneWidget);
      expect(find.text('Intro paragraph.'), findsOneWidget);
    });

    testWidgets('accepts a separator without a leading pipe', (tester) async {
      const source = '''
| Name | Value |
--- | ---
| alpha | 1 |

After.
''';
      await tester.pumpWidget(_host(MarkdownArtifactView(content: source)));
      await tester.pumpAndSettle();
      expect(find.text('alpha'), findsOneWidget);
      expect(find.text('After.'), findsOneWidget);
    });

    testWidgets('renders headings, lists and a fenced code block',
        (tester) async {
      const source = '''
# Design

- first item
- second item

```sql
CREATE TABLE users (id INT);
```
''';
      await tester.pumpWidget(_host(MarkdownArtifactView(content: source)));
      await tester.pumpAndSettle();
      expect(find.text('Design'), findsOneWidget);
      expect(find.text('first item'), findsOneWidget);
      expect(find.textContaining('CREATE TABLE users'), findsOneWidget);
    });
  });

  group('BpmnProcessModel', () {
    test('maps react_flow nodes, edges, swimlanes and bottlenecks', () {
      final model = BpmnProcessModel.fromArtifact(_artifact(
        type: 'bpmn_flows',
        content: {
          'bpmn': {'name': 'Checkout Flow'},
          'swimlanes': [
            {'id': 'lane-1', 'label': 'Customer'},
            {'id': 'lane-2'},
          ],
          'bottlenecks': [
            {'module': 'payment', 'reason': 'Gateway timeout'},
            {'module': 'email'},
          ],
          'react_flow': {
            'nodes': [
              {
                'id': 'n1',
                'type': 'start',
                'data': {'label': 'Start order'},
              },
              {
                'id': 'n2',
                'type': 'gateway',
                'data': {'label': 'Approved?'},
              },
              {
                'id': 'n3',
                'type': 'not-a-real-type',
                'data': {},
              },
            ],
            'edges': [
              {'source': 'n1', 'target': 'n2'},
              {'source': 'n2', 'target': 'n3'},
              {'source': 'n3'},
            ],
          },
        },
      ));

      expect(model.processName, 'Checkout Flow');
      expect(model.swimlanes, ['Customer', 'lane-2']);
      expect(model.nodes.map((n) => n.label), ['Start order', 'Approved?', 'Step']);
      // Unknown node types degrade to `task` rather than crashing the painter.
      expect(model.nodes[2].type, 'task');
      // The edge with a missing target is dropped.
      expect(model.connections.length, 2);
      expect(model.bottlenecks, ['Gateway timeout', 'Bottleneck in email']);
    });

    test('falls back to a Start node when the payload has no flow', () {
      final model = BpmnProcessModel.fromArtifact(_artifact(
        type: 'bpmn',
        content: const {},
      ));
      expect(model.nodes.single.type, 'start');
      expect(model.isEmpty, isFalse);
    });

    testWidgets('draws swimlanes, nodes, arrows and bottleneck callouts',
        (tester) async {
      final model = BpmnProcessModel.fromArtifact(_artifact(
        type: 'bpmn_flows',
        content: {
          'bpmn': {'name': 'Onboarding'},
          'swimlanes': [
            {'label': 'User'},
            {'label': 'System'},
          ],
          'bottlenecks': [
            {'reason': 'KYC provider is slow'},
          ],
          'react_flow': {
            'nodes': [
              {'id': 'a', 'type': 'start', 'data': {'label': 'Sign up'}},
              {'id': 'b', 'type': 'task', 'data': {'label': 'Verify ID'}},
              {'id': 'c', 'type': 'end', 'data': {'label': 'Active'}},
            ],
            'edges': [
              {'source': 'a', 'target': 'b'},
              {'source': 'b', 'target': 'c'},
            ],
          },
        },
      ));

      await tester.pumpWidget(_host(BpmnProcessView(process: model)));
      await tester.pumpAndSettle();

      // Node/step labels are painted onto a canvas, so they are not in the
      // widget tree; assert the surrounding chrome and the paint surface.
      expect(find.text('Onboarding'), findsOneWidget);
      expect(find.text('3 STEPS'), findsOneWidget);
      expect(find.text('KYC provider is slow'), findsOneWidget);
      expect(find.text('Decision'), findsOneWidget);
      expect(find.text('Service'), findsOneWidget);
      expect(
        find.byWidgetPredicate(
          (w) => w is CustomPaint && w.size != Size.zero,
        ),
        findsWidgets,
      );
    });
  });

  group('Wireframe canvas', () {
    ArtifactModel wireframe(String id) => _artifact(
          type: 'wireframe',
          title: 'App wireframe',
          content: {
            'screens': [
              {
                'name': 'Login',
                'description': 'Email + password',
                'components': [
                  {
                    'title': 'Email field',
                    'type': 'input',
                    'fields': [
                      {'name': 'email'},
                      {'name': 'label'},
                    ],
                  },
                  {'name': 'Submit button', 'type': 'button'},
                ],
              },
              {
                'name': 'Home',
                'components': <dynamic>[],
              },
            ],
          },
        );

    test('lays out screens in a row with their components beneath', () {
      final canvas = buildWireframeCanvas([wireframe('a1')]);
      final screens = canvas.nodes.where((n) => n.isScreen).toList();
      final comps = canvas.nodes.where((n) => !n.isScreen).toList();

      expect(screens.map((s) => s.label), ['Login', 'Home']);
      expect(screens[1].position.dx, greaterThan(screens[0].position.dx));
      expect(comps.length, 2);
      expect(comps.first.label, 'Email field');
      expect(comps.first.fieldCount, 2);
      // Components sit below their screen and are connected to it.
      expect(comps.first.position.dy, greaterThan(screens.first.position.dy));
      expect(canvas.edges.length, 2);
      expect(canvas.edges.first.$1, screens.first.id);
    });

    test('falls back to a single screen for a flat wireframe artifact', () {
      final canvas = buildWireframeCanvas([
        _artifact(
          type: 'wireframe',
          title: 'Checkout',
          content: {
            'components': [
              {'title': 'Cart list', 'type': 'list'},
            ],
          },
        ),
      ]);
      expect(canvas.nodes.where((n) => n.isScreen).single.label, 'Checkout');
      expect(canvas.nodes.length, 2);
    });

    test('add, move and remove keep edges consistent', () {
      final canvas = buildWireframeCanvas([wireframe('a1')]);
      final screen = canvas.nodes.firstWhere((n) => n.isScreen);

      canvas.addComponent(
        id: 'c-new',
        screenId: screen.id,
        label: 'Password field',
        at: Offset.zero,
      );
      expect(canvas.edges, contains((screen.id, 'c-new')));

      final before = screen.position;
      canvas.move(screen.id, const Offset(20, 5));
      expect(screen.position.dx, before.dx + 20);

      canvas.remove('c-new');
      expect(canvas.edges, isNot(contains((screen.id, 'c-new'))));
      expect(canvas.byId('c-new'), isNull);
    });

    testWidgets('renders the canvas with an add control', (tester) async {
      final canvas = buildWireframeCanvas([wireframe('a1')]);
      await tester.pumpWidget(_host(
        SizedBox(
          height: 420,
          child: WireframeCanvasView(state: canvas, onChanged: (_) {}),
        ),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Login'), findsOneWidget);
      expect(find.text('Email field'), findsOneWidget);
      expect(find.text('ADD'), findsOneWidget);
      expect(find.text('DELETE'), findsOneWidget);
    });

    testWidgets('ADD inserts a screen when nothing is selected',
        (tester) async {
      final canvas = buildWireframeCanvas([wireframe('a1')]);
      var changes = 0;
      await tester.pumpWidget(_host(
        SizedBox(
          height: 420,
          child: WireframeCanvasView(
            state: canvas,
            onChanged: (_) => changes++,
          ),
        ),
      ));
      await tester.pumpAndSettle();

      final screensBefore = canvas.nodes.where((n) => n.isScreen).length;
      await tester.tap(find.text('ADD'));
      await tester.pumpAndSettle();

      expect(canvas.nodes.where((n) => n.isScreen).length,
          screensBefore + 1);
      expect(changes, greaterThan(0));
    });
  });

  group('Friendly artifact labels', () {
    testWidgets('long artifact names fit the tab chrome', (tester) async {
      await tester.pumpWidget(_host(
        SutraCard(
          child: Row(
            children: [
              const Icon(Icons.call_split, size: 12, color: Colors.white),
              Text(
                'BPMN 2.0 PROCESS',
                style: const TextStyle(fontSize: 9, color: Colors.white),
              ),
              const SizedBox(width: 6),
              Text(
                'UI WIREFRAMES',
                style: const TextStyle(fontSize: 9, color: Colors.white),
              ),
            ],
          ),
        ),
      ));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.text('BPMN 2.0 PROCESS'), findsOneWidget);
    });
  });
}
