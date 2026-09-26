import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../../core/network/json_utils.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_text_styles.dart';
import '../domain/workspace_models.dart';

/// Visual renderers for the two structured artifact types the web app draws
/// instead of showing as text: the BPMN process diagram and the draggable
/// UI wireframe canvas.

// ─── BPMN 2.0 process ─────────────────────────────────────────────────────────

class BpmnNode {
  const BpmnNode({
    required this.id,
    required this.type,
    required this.label,
    this.description = '',
  });

  final String id;

  /// `start` | `task` | `gateway` | `end` | `service`.
  final String type;
  final String label;
  final String description;
}

class BpmnProcessModel {
  const BpmnProcessModel({
    required this.processName,
    required this.swimlanes,
    required this.nodes,
    required this.connections,
    required this.bottlenecks,
  });

  final String processName;
  final List<String> swimlanes;
  final List<BpmnNode> nodes;
  final List<(String, String)> connections;
  final List<String> bottlenecks;

  bool get isEmpty => nodes.isEmpty;

  /// Mirrors the web `toBpmnProcess` mapping, including the `bpmn` ->
  /// `bpmn_flows` alias and the react_flow node/edge payload.
  factory BpmnProcessModel.fromArtifact(ArtifactModel artifact) {
    final content = artifact.content;
    final flow = asMap(content['react_flow']);

    final nodes = <BpmnNode>[];
    for (final raw in asList(flow['nodes'])) {
      final node = asMap(raw);
      final data = asMap(node['data']);
      final type = pick(node, ['type'], asString, 'task');
      nodes.add(BpmnNode(
        id: pick(node, ['id'], asString, 'node'),
        type: const ['start', 'task', 'gateway', 'end', 'service'].contains(type)
            ? type
            : 'task',
        label: pick(data, ['label'], asString, 'Step'),
      ));
    }

    final connections = <(String, String)>[];
    for (final raw in asList(flow['edges'])) {
      final edge = asMap(raw);
      final from = pick(edge, ['source'], asString, '');
      final to = pick(edge, ['target'], asString, '');
      if (from.isNotEmpty && to.isNotEmpty) connections.add((from, to));
    }

    final swimlanes = <String>[];
    for (final raw in asList(content['swimlanes'])) {
      final lane = asMap(raw);
      final label = pick(lane, ['label'], asString, '');
      final id = pick(lane, ['id'], asString, '');
      final value = label.isNotEmpty ? label : id;
      if (value.isNotEmpty) swimlanes.add(value);
    }

    final bottlenecks = <String>[];
    for (final raw in asList(content['bottlenecks'])) {
      final b = asMap(raw);
      final reason = pick(b, ['reason'], asString, '');
      final module = pick(b, ['module'], asString, 'workflow');
      final value = reason.isNotEmpty ? reason : 'Bottleneck in $module';
      if (value.isNotEmpty) bottlenecks.add(value);
    }

    return BpmnProcessModel(
      processName: pick(asMap(content['bpmn']), ['name'], asString,
          'Process Workflow'),
      swimlanes: swimlanes,
      nodes: nodes.isEmpty
          ? const [
              BpmnNode(
                id: 'start',
                type: 'start',
                label: 'Start',
                description: 'Participant',
              ),
            ]
          : nodes,
      connections: connections,
      bottlenecks: bottlenecks,
    );
  }
}

/// Swimlane diagram: one band per participant, nodes laid out left to right
/// inside the lane their sequence belongs to, arrows for the transitions.
class BpmnProcessView extends StatelessWidget {
  const BpmnProcessView({super.key, required this.process});

  final BpmnProcessModel process;

  @override
  Widget build(BuildContext context) {
    if (process.isEmpty) {
      return Text(
        'This process has no steps yet.',
        style: AppTextStyles.bodySmall(color: AppColors.lightTextSecondary),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.account_tree_outlined,
                size: 15, color: AppColors.gold),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                process.processName,
                style: AppTextStyles.serifHeading(fontSize: 15),
              ),
            ),
            Text(
              '${process.nodes.length} STEPS',
              style: AppTextStyles.smallCapsLabel(
                fontSize: 9,
                color: AppColors.lightTextMuted,
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.sm),
        LayoutBuilder(
          builder: (context, constraints) {
            // Lanes get equal height, and the diagram scrolls horizontally
            // because a real process is wider than a phone.
            final lanes = process.swimlanes.isEmpty
                ? const ['Process Participants']
                : process.swimlanes;
            final laneHeight = 92.0;
            return SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: CustomPaint(
                size: Size(
                  math.max(constraints.maxWidth, process.nodes.length * 150.0 + 60),
                  lanes.length * laneHeight,
                ),
                painter: _BpmnPainter(process: process, laneHeight: laneHeight),
              ),
            );
          },
        ),
        if (process.bottlenecks.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          Text(
            'BOTTLENECKS',
            style: AppTextStyles.smallCapsLabel(
              fontSize: 9,
              color: AppColors.statusWarningAmber,
            ),
          ),
          const SizedBox(height: 4),
          for (final b in process.bottlenecks)
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Padding(
                    padding: EdgeInsets.only(top: 1, right: 5),
                    child: Icon(Icons.warning_amber_rounded,
                        size: 12, color: AppColors.statusWarningAmber),
                  ),
                  Expanded(
                    child: Text(
                      b,
                      style: AppTextStyles.bodySmall(
                        color: AppColors.lightTextSecondary,
                        fontSize: 11,
                      ),
                    ),
                  ),
                ],
              ),
            ),
        ],
        const SizedBox(height: AppSpacing.sm),
        _BpmnLegend(),
      ],
    );
  }
}

class _BpmnLegend extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    const entries = [
      ('start', 'Start'),
      ('task', 'Task'),
      ('gateway', 'Decision'),
      ('service', 'Service'),
      ('end', 'End'),
    ];
    return Wrap(
      spacing: AppSpacing.sm,
      runSpacing: 4,
      children: [
        for (final (type, label) in entries)
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              _BpmnShape(type: type, size: 12),
              const SizedBox(width: 4),
              Text(
                label,
                style: AppTextStyles.bodySmall(
                  fontSize: 10,
                  color: AppColors.lightTextMuted,
                ),
              ),
            ],
          ),
      ],
    );
  }
}

class _BpmnShape extends StatelessWidget {
  const _BpmnShape({required this.type, this.size = 20});

  final String type;
  final double size;

  @override
  Widget build(BuildContext context) {
    final color = _bpmnColor(type);
    switch (type) {
      case 'start':
      case 'end':
        return Container(
          width: size,
          height: size,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        );
      case 'gateway':
        return Transform.rotate(
          angle: math.pi / 4,
          child: Container(
            width: size * 0.8,
            height: size * 0.8,
            decoration: BoxDecoration(
              border: Border.all(color: color, width: 1.4),
            ),
          ),
        );
      case 'service':
        return Container(
          width: size,
          height: size,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            border: Border.all(color: color, width: 1.4),
          ),
          child: Container(
            width: size * 0.34,
            height: size * 0.34,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
        );
      default:
        return Container(
          width: size * 1.35,
          height: size * 0.8,
          decoration: BoxDecoration(
            border: Border.all(color: color, width: 1.4),
            borderRadius: BorderRadius.circular(2),
          ),
        );
    }
  }
}

Color _bpmnColor(String type) => switch (type) {
      'start' => AppColors.statusLiveGreen,
      'end' => AppColors.statusErrorRed,
      'gateway' => AppColors.statusWarningAmber,
      'service' => AppColors.lightTextSecondary,
      _ => AppColors.gold,
    };

class _BpmnPainter extends CustomPainter {
  _BpmnPainter({required this.process, required this.laneHeight});

  final BpmnProcessModel process;
  final double laneHeight;

  static const _nodeW = 118.0;
  static const _nodeH = 40.0;
  static const _gapX = 32.0;

  @override
  void paint(Canvas canvas, Size size) {
    final lanes = process.swimlanes.isEmpty
        ? const ['Process Participants']
        : process.swimlanes;

    final lanePaint = Paint()
      ..color = AppColors.lightSurfaceSubtle
      ..style = PaintingStyle.fill;
    final laneBorder = Paint()
      ..color = AppColors.lightBorder
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    final gridPaint = Paint()
      ..color = AppColors.lightBorder
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;

    // Swimlane bands + labels.
    for (var i = 0; i < lanes.length; i++) {
      final top = i * laneHeight;
      final rect = Rect.fromLTWH(0, top, size.width, laneHeight);
      if (i.isEven) canvas.drawRect(rect, lanePaint);
      canvas.drawRect(rect, laneBorder);

      _paintLabel(
        canvas,
        lanes[i],
        Offset(8, top + 6),
        AppTextStyles.smallCapsLabel(
          fontSize: 8,
          color: AppColors.lightTextMuted,
        ),
      );
      canvas.drawLine(
        Offset(0, top.toDouble()),
        Offset(size.width, top),
        gridPaint,
      );
    }

    // Nodes are spread evenly; each is assigned the lane its index maps to.
    final positions = <String, Rect>{};
    final perLane = math.max(1, (process.nodes.length / lanes.length).ceil());
    for (var i = 0; i < process.nodes.length; i++) {
      final laneIndex = (i ~/ perLane).clamp(0, lanes.length - 1);
      final col = i % perLane;
      final x = 20.0 + col * (_nodeW + _gapX);
      final y = laneIndex * laneHeight + (laneHeight - _nodeH) / 2;
      final rect = Rect.fromLTWH(x, y, _nodeW, _nodeH);
      positions[process.nodes[i].id] = rect;
    }

    // Connections first, so nodes paint over the arrow heads.
    final arrow = Paint()
      ..color = AppColors.gold
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4;
    for (final (from, to) in process.connections) {
      final a = positions[from];
      final b = positions[to];
      if (a == null || b == null) continue;
      final start = Offset(a.right, a.center.dy);
      final end = Offset(b.left, b.center.dy);
      final midX = (start.dx + end.dx) / 2;
      final path = Path()
        ..moveTo(start.dx, start.dy)
        ..cubicTo(midX, start.dy, midX, end.dy, end.dx, end.dy);
      canvas.drawPath(path, arrow);
      // Arrow head.
      canvas.drawLine(
        end,
        Offset(end.dx - 6, end.dy - 4),
        arrow,
      );
      canvas.drawLine(end, Offset(end.dx - 6, end.dy + 4), arrow);
    }

    for (final node in process.nodes) {
      final rect = positions[node.id];
      if (rect == null) continue;
      final color = _bpmnColor(node.type);
      final fill = Paint()..color = color.withValues(alpha: 0.12);
      final stroke = Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.3;

      switch (node.type) {
        case 'start':
        case 'end':
          canvas.drawCircle(rect.center, rect.height / 2, fill);
          canvas.drawCircle(rect.center, rect.height / 2, stroke);
        case 'gateway':
          final d = math.min(rect.width, rect.height) * 0.7;
          final path = Path()
            ..moveTo(rect.center.dx, rect.center.dy - d / 2)
            ..lineTo(rect.center.dx + d / 2, rect.center.dy)
            ..lineTo(rect.center.dx, rect.center.dy + d / 2)
            ..lineTo(rect.center.dx - d / 2, rect.center.dy)
            ..close();
          canvas.drawPath(path, fill);
          canvas.drawPath(path, stroke);
        case 'service':
          canvas.drawRRect(
            RRect.fromRectAndRadius(rect, const Radius.circular(3)),
            fill,
          );
          canvas.drawRRect(
            RRect.fromRectAndRadius(rect, const Radius.circular(3)),
            stroke,
          );
          canvas.drawCircle(rect.center, 5, stroke);
        default:
          final rrect = RRect.fromRectAndRadius(rect, const Radius.circular(3));
          canvas.drawRRect(rrect, fill);
          canvas.drawRRect(rrect, stroke);
      }

      _paintLabel(
        canvas,
        node.label,
        Offset(rect.left + 6, rect.center.dy - 5),
        AppTextStyles.bodySmall(fontSize: 10, color: AppColors.lightTextPrimary),
        maxWidth: rect.width - 12,
        maxLines: 2,
      );
    }
  }

  /// Text on a canvas has no layout box, so clip it manually.
  void _paintLabel(
    Canvas canvas,
    String text,
    Offset at,
    TextStyle style, {
    double maxWidth = 160,
    int maxLines = 2,
  }) {
    final painter = TextPainter(
      text: TextSpan(text: text, style: style),
      textDirection: TextDirection.ltr,
      maxLines: maxLines,
      ellipsis: '…',
    )..layout(maxWidth: maxWidth);
    painter.paint(canvas, at);
    painter.dispose();
  }

  @override
  bool shouldRepaint(covariant _BpmnPainter old) =>
      old.process != process || old.laneHeight != laneHeight;
}

// ─── UI wireframe canvas ─────────────────────────────────────────────────────

class WireframeNode {
  WireframeNode({
    required this.id,
    required this.label,
    required this.isScreen,
    required this.position,
    this.subtitle = '',
    this.componentType = 'widget',
    this.fieldCount = 0,
  });

  final String id;
  final String label;

  /// Screens own their components; components hang below their screen.
  final bool isScreen;
  Offset position;
  String subtitle;
  String componentType;
  int fieldCount;

  static const width = 168.0;
  static const height = 62.0;

  Rect get rect => Rect.fromLTWH(position.dx, position.dy, width, height);
}

class WireframeCanvasState {
  WireframeCanvasState({required this.nodes, required this.edges});

  final List<WireframeNode> nodes;

  /// `(fromNodeId, toNodeId)` pairs; a component is connected to its screen.
  final List<(String, String)> edges;

  WireframeNode? byId(String id) {
    for (final n in nodes) {
      if (n.id == id) return n;
    }
    return null;
  }

  void move(String id, Offset delta) {
    byId(id)?.position += delta;
  }

  void addScreen(String id, String label, Offset at) {
    nodes.add(WireframeNode(
      id: id,
      label: label,
      isScreen: true,
      position: at,
    ));
  }

  void addComponent({
    required String id,
    required String screenId,
    required String label,
    required Offset at,
    String type = 'widget',
  }) {
    final node = WireframeNode(
      id: id,
      label: label,
      isScreen: false,
      position: at,
      componentType: type,
    );
    nodes.add(node);
    edges.removeWhere((e) => e.$1 == id);
    edges.add((screenId, id));
  }

  void remove(String id) {
    nodes.removeWhere((n) => n.id == id);
    edges.removeWhere((e) => e.$1 == id || e.$2 == id);
  }
}

/// Builds the canvas from the wireframe artifacts, matching the web layout:
/// screens in a row, each screen's components stacked beneath it.
WireframeCanvasState buildWireframeCanvas(List<ArtifactModel> artifacts) {
  final nodes = <WireframeNode>[];
  final edges = <(String, String)>[];
  const screenGapX = 220.0;
  const componentGapY = 78.0;
  var cursorX = 16.0;

  for (final artifact in artifacts) {
    final content = artifact.content;
    final rawScreens = asList(content['screens']);

    final screens = rawScreens.isEmpty
        ? [
            {
              'name': artifact.title.isEmpty ? 'Wireframe' : artifact.title,
              'description': pick(content, ['description'], asString, ''),
              'components': asList(content['components']),
            }
          ]
        : rawScreens.map(asMap).toList();

    for (var s = 0; s < screens.length; s++) {
      final screen = screens[s];
      final screenId = '${artifact.id}-screen-$s';
      nodes.add(WireframeNode(
        id: screenId,
        label: pick(screen, ['name'], asString, 'Untitled Screen'),
        isScreen: true,
        position: Offset(cursorX, 12),
        subtitle: pick(screen, ['description'], asString, ''),
      ));

      final comps = asList(screen['components']);
      for (var c = 0; c < comps.length; c++) {
        final comp = asMap(comps[c]);
        final compId = '$screenId-comp-$c';
        nodes.add(WireframeNode(
          id: compId,
          label: pick(comp, ['title', 'name'], asString, 'Component'),
          isScreen: false,
          position: Offset(cursorX, 12 + WireframeNode.height + 16 +
              c * componentGapY),
          componentType: pick(comp, ['type'], asString, 'widget'),
          subtitle: pick(comp, ['description'], asString, ''),
          fieldCount: asList(comp['fields']).length,
        ));
        edges.add((screenId, compId));
      }
      cursorX += screenGapX;
    }
  }

  return WireframeCanvasState(nodes: nodes, edges: edges);
}

/// Pan / zoom / drag canvas. The web canvas edits the artifact in page state
/// only (no server write), so this keeps its edits local too and hands the
/// serialized result to [onChanged].
class WireframeCanvasView extends StatefulWidget {
  const WireframeCanvasView({
    super.key,
    required this.state,
    required this.onChanged,
  });

  final WireframeCanvasState state;
  final ValueChanged<WireframeCanvasState> onChanged;

  @override
  State<WireframeCanvasView> createState() => _WireframeCanvasViewState();
}

class _WireframeCanvasViewState extends State<WireframeCanvasView> {
  final _transform = TransformationController();
  String? _selected;
  String? _dragging;
  Offset? _dragAnchor;
  Size _viewport = Size.zero;
  int _seq = 0;

  @override
  void dispose() {
    _transform.dispose();
    super.dispose();
  }

  Offset _toScene(Offset local) =>
      _transform.toScene(local);

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _toolbar(),
        Expanded(
          child: LayoutBuilder(
            builder: (context, constraints) {
              _viewport = Size(constraints.maxWidth, constraints.maxHeight);
              final sceneWidth = math.max(
                constraints.maxWidth,
                widget.state.nodes.isEmpty
                    ? 0.0
                    : widget.state.nodes
                            .map((n) => n.position.dx + WireframeNode.width)
                            .reduce(math.max) +
                        40.0,
              );
              final sceneHeight = math.max(
                constraints.maxHeight,
                widget.state.nodes.isEmpty
                    ? 0.0
                    : widget.state.nodes
                            .map((n) => n.position.dy + WireframeNode.height)
                            .reduce(math.max) +
                        40.0,
              );
              return ClipRect(
                child: GestureDetector(
                  onTap: () => setState(() => _selected = null),
                  child: InteractiveViewer(
                    transformationController: _transform,
                    minScale: 0.4,
                    maxScale: 2.5,
                    constrained: false,
                    boundaryMargin: const EdgeInsets.all(400),
                    child: SizedBox(
                      width: sceneWidth,
                      height: sceneHeight,
                      child: Stack(
                        children: [
                          Positioned.fill(
                            child: CustomPaint(
                              painter: _WireframePainter(
                                state: widget.state,
                                selectedId: _selected,
                              ),
                            ),
                          ),
                          for (final node in widget.state.nodes)
                            Positioned(
                              left: node.position.dx,
                              top: node.position.dy,
                              width: WireframeNode.width,
                              height: WireframeNode.height,
                              child: _WireframeCard(
                                node: node,
                                selected: _selected == node.id,
                                onTap: () => setState(
                                  () => _selected =
                                      _selected == node.id ? null : node.id,
                                ),
                                onDragStart: (local) {
                                  setState(() {
                                    _dragging = node.id;
                                    _dragAnchor = _toScene(local);
                                  });
                                },
                                onDragUpdate: (delta) {
                                  final id = _dragging;
                                  if (id == null) return;
                                  final scene = _toScene(delta);
                                  final target = widget.state.byId(id);
                                  if (target == null) return;
                                  setState(() {
                                    target.position = target.position +
                                        (scene - _dragAnchor!);
                                    _dragAnchor = scene;
                                  });
                                  widget.onChanged(widget.state);
                                },
                                onDragEnd: () {
                                  setState(() {
                                    _dragging = null;
                                    _dragAnchor = null;
                                  });
                                },
                              ),
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _toolbar() {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: 6,
      ),
      color: AppColors.lightSurfaceSubtle,
      child: Row(
        children: [
          Text(
            _selected == null ? 'TAP A NODE' : 'SELECTED',
            style: AppTextStyles.smallCapsLabel(
              fontSize: 9,
              color: AppColors.lightTextMuted,
            ),
          ),
          const Spacer(),
          TextButton.icon(
            onPressed: () {
              final anchor = _selected == null
                  ? null
                  : widget.state.byId(_selected!);
              _seq++;
              setState(() {
                if (anchor != null && !anchor.isScreen) {
                  widget.state.addComponent(
                    id: 'new-$_seq',
                    screenId: anchor.id,
                    label: 'Component $_seq',
                    at: anchor.position +
                        const Offset(0, WireframeNode.height + 12),
                  );
                } else {
                  final at = Offset(
                    _viewport.width / 2 - WireframeNode.width / 2,
                    20 + _seq * 12,
                  );
                  widget.state.addScreen('new-$_seq', 'Screen $_seq', at);
                }
              });
              widget.onChanged(widget.state);
            },
            icon: const Icon(Icons.add, size: 14),
            label: Text(
              'ADD',
              style: AppTextStyles.smallCapsLabel(
                fontSize: 9,
                color: AppColors.gold,
              ),
            ),
          ),
          TextButton.icon(
            onPressed: _selected == null
                ? null
                : () {
                    setState(() {
                      widget.state.remove(_selected!);
                      _selected = null;
                    });
                    widget.onChanged(widget.state);
                  },
            icon: const Icon(Icons.delete_outline, size: 14),
            label: Text(
              'DELETE',
              style: AppTextStyles.smallCapsLabel(
                fontSize: 9,
                color: AppColors.statusErrorRed,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _WireframeCard extends StatelessWidget {
  const _WireframeCard({
    required this.node,
    required this.selected,
    required this.onTap,
    required this.onDragStart,
    required this.onDragUpdate,
    required this.onDragEnd,
  });

  final WireframeNode node;
  final bool selected;
  final VoidCallback onTap;
  final ValueChanged<Offset> onDragStart;
  final ValueChanged<Offset> onDragUpdate;
  final VoidCallback onDragEnd;

  @override
  Widget build(BuildContext context) {
    final accent = node.isScreen ? AppColors.gold : AppColors.lightTextSecondary;
    return GestureDetector(
      onTap: onTap,
      onPanStart: (d) => onDragStart(d.globalPosition),
      onPanUpdate: (d) => onDragUpdate(d.globalPosition),
      onPanEnd: (_) => onDragEnd(),
      child: Container(
        padding: const EdgeInsets.all(6),
        decoration: BoxDecoration(
          color: node.isScreen
              ? AppColors.darkBackground
              : AppColors.lightSurface,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(
            color: selected ? accent : AppColors.lightBorder,
            width: selected ? 1.6 : 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              node.label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.bodySmall(
                fontSize: 10,
                color: node.isScreen
                    ? AppColors.darkTextPrimary
                    : AppColors.lightTextPrimary,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              node.isScreen
                  ? (node.subtitle.isEmpty ? 'Screen' : node.subtitle)
                  : '${node.componentType}'
                      '${node.fieldCount > 0 ? ' - ${node.fieldCount} fields' : ''}',
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: AppTextStyles.mono(
                fontSize: 8,
                color: node.isScreen
                    ? AppColors.darkTextMuted
                    : AppColors.lightTextMuted,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _WireframePainter extends CustomPainter {
  _WireframePainter({required this.state, required this.selectedId});

  final WireframeCanvasState state;
  final String? selectedId;

  @override
  void paint(Canvas canvas, Size size) {
    final line = Paint()
      ..color = AppColors.gold
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4;

    for (final (fromId, toId) in state.edges) {
      final from = state.byId(fromId);
      final to = state.byId(toId);
      if (from == null || to == null) continue;
      final start = Offset(from.position.dx + WireframeNode.width / 2,
          from.position.dy + WireframeNode.height);
      final end = Offset(to.position.dx + WireframeNode.width / 2,
          to.position.dy);
      final midY = (start.dy + end.dy) / 2;
      final path = Path()
        ..moveTo(start.dx, start.dy)
        ..lineTo(start.dx, midY)
        ..lineTo(end.dx, midY)
        ..lineTo(end.dx, end.dy);
      canvas.drawPath(path, line);
      canvas.drawLine(end, Offset(end.dx - 4, end.dy - 6), line);
      canvas.drawLine(end, Offset(end.dx + 4, end.dy - 6), line);
    }

    // Selection ring for the node the canvas is not drawing a body for.
    final selected = selectedId == null ? null : state.byId(selectedId!);
    if (selected != null) {
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          selected.rect.inflate(3),
          const Radius.circular(7),
        ),
        Paint()
          ..color = AppColors.gold.withValues(alpha: 0.5)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.2,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _WireframePainter old) =>
      old.state != state || old.selectedId != selectedId;
}
