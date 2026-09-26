import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/network/api_exceptions.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/utils/file_delivery.dart';
import '../../../core/widgets/prompt_dialog.dart';
import '../../../core/widgets/sutra_button.dart';
import '../../../core/widgets/sutra_card.dart';
import '../data/workspace_repository.dart';
import '../domain/workspace_models.dart';
import 'artifact_visual_views.dart';
import 'explainability_sheets.dart';
import 'markdown_artifact_view.dart';
import 'workspace_providers.dart';

/// Tab labels/icons copied from the web artifact viewer so both apps name the
/// same artifact identically instead of leaking raw enum values.
const Map<String, String> _artifactLabels = {
  'hld': 'High-Level Design',
  'lld': 'Low-Level Design',
  'workable': 'Mounted Live App',
  'bpmn_flows': 'BPMN 2.0 Process',
  'wireframe': 'UI Wireframes',
  'database_schema': 'DB Schema & ERD',
  'api_spec': 'OpenAPI Spec',
  'roadmap': 'Roadmap & Sprints',
  'prd': 'Product Requirements',
  'decision_log': 'Decision Log',
  'gap_analysis': 'Gap Analysis',
};

const Map<String, IconData> _artifactIcons = {
  'hld': Icons.layers_outlined,
  'lld': Icons.account_tree_outlined,
  'workable': Icons.play_arrow_outlined,
  'bpmn_flows': Icons.call_split,
  'wireframe': Icons.dashboard_outlined,
  'database_schema': Icons.storage_outlined,
  'api_spec': Icons.code,
  'roadmap': Icons.calendar_today_outlined,
  'prd': Icons.description_outlined,
  'decision_log': Icons.history_outlined,
  'gap_analysis': Icons.rule_outlined,
};


/// Blueprint review: every artifact, the approval workflow, and export.
///
/// Mirrors the web app's `/solution/[id]`. The Flutter app only ever showed the
/// first schema-shaped and first api-shaped artifact, so decision logs, HLD/LLD,
/// ER diagrams, wireframes and BPMN flows were invisible, and approve /
/// request-changes / export / regenerate had no UI at all.
class SolutionDetailScreen extends ConsumerStatefulWidget {
  const SolutionDetailScreen({super.key});

  @override
  ConsumerState<SolutionDetailScreen> createState() =>
      _SolutionDetailScreenState();
}

class _SolutionDetailScreenState extends ConsumerState<SolutionDetailScreen> {
  @override
  Widget build(BuildContext context) {
    final solutionId = ref.watch(effectiveSolutionIdProvider);
    final detailAsync =
        solutionId == null ? null : ref.watch(solutionDetailProvider(solutionId));

    return Scaffold(
      backgroundColor: AppColors.lightBackground,
      appBar: AppBar(
        backgroundColor: AppColors.lightSurface,
        surfaceTintColor: Colors.transparent,
        title: Text('Blueprint', style: AppTextStyles.serifHeading(fontSize: 20)),
      ),
      body: solutionId == null
          ? const _MissingSelection()
          : RefreshIndicator(
              onRefresh: () async {
                ref.invalidate(solutionDetailProvider(solutionId));
                await ref.read(solutionDetailProvider(solutionId).future);
              },
              child: detailAsync!.when(
                loading: () => const Center(
                  child: CircularProgressIndicator(color: AppColors.blackButton),
                ),
                error: (error, _) => _ErrorView(
                  message: error is ApiException
                      ? error.message
                      : 'Blueprint unavailable.',
                  onRetry: () => ref.invalidate(
                    solutionDetailProvider(solutionId),
                  ),
                ),
                data: (detail) => _DetailBody(detail: detail),
              ),
            ),
    );
  }
}

class _DetailBody extends ConsumerStatefulWidget {
  const _DetailBody({required this.detail});

  final SolutionDetailModel detail;

  @override
  ConsumerState<_DetailBody> createState() => _DetailBodyState();
}

class _DetailBodyState extends ConsumerState<_DetailBody> {
  late String _selectedType = widget.detail.artifacts.isEmpty
      ? ''
      : widget.detail.artifacts.first.artifactType;
  bool _busy = false;

  SolutionDetailModel get detail => widget.detail;

  @override
  Widget build(BuildContext context) {
    final solutionId = detail.solution.id;

    // One entry per artifact type, so every type is reachable.
    final types = <String, ArtifactModel>{};
    for (final a in detail.artifacts) {
      types.putIfAbsent(a.artifactType, () => a);
    }
    if (!types.containsKey(_selectedType) && types.isNotEmpty) {
      _selectedType = types.keys.first;
    }

    final selected = types[_selectedType];
    final approval = detail.solution.approvalStatus;

    return ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: [
        Text(
          detail.title,
          style: AppTextStyles.serifHeading(
            fontSize: 24,
            color: AppColors.lightTextPrimary,
          ),
        ),
        if (detail.description != null) ...[
          const SizedBox(height: AppSpacing.xs),
          Text(
            detail.description!,
            style: AppTextStyles.bodySmall(
              color: AppColors.lightTextSecondary,
            ),
          ),
        ],
        const SizedBox(height: AppSpacing.sm),
        _GuidedStepper(
          current: detail.guidedStage,
          completed: detail.completedGuidedStages,
        ),
        const SizedBox(height: AppSpacing.md),
        Wrap(
          spacing: AppSpacing.xs,
          runSpacing: AppSpacing.xs,
          children: [
            _Pill(label: detail.solution.statusLabel),
            if (approval != null)
              _Pill(label: approval.toUpperCase(), accent: true),
            if (detail.isApproved)
              _Pill(label: 'SNAPSHOT LOCKED', accent: true),
          ],
        ),
        const SizedBox(height: AppSpacing.md),
        if (detail.hasGaps) ...[
          _WhatYouMissedPanel(
            requirements: detail.missingRequirements,
            questions: detail.openQuestions,
          ),
          const SizedBox(height: AppSpacing.md),
        ],
        _buildApprovalActions(solutionId),

        const Divider(color: AppColors.lightBorder, height: AppSpacing.xl),
        Text(
          'ARTIFACTS (${detail.artifacts.length})',
          style: AppTextStyles.smallCapsLabel(
            fontSize: 10,
            color: AppColors.gold,
            letterSpacing: 1.5,
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        if (detail.artifacts.isEmpty)
          Text(
            'No artifacts generated yet. Use the Orchestrator to synthesize some.',
            style: AppTextStyles.bodySmall(
              color: AppColors.lightTextSecondary,
            ),
          )
        else ...[
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (final type in types.keys)
                GestureDetector(
                  onTap: () => setState(() => _selectedType = type),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: type == _selectedType
                          ? AppColors.blackButton
                          : AppColors.lightSurface,
                      borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                      border: Border.all(
                        color: type == _selectedType
                            ? AppColors.blackButton
                            : AppColors.lightBorder,
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          _artifactIcons[type] ?? Icons.description_outlined,
                          size: 12,
                          color: type == _selectedType
                              ? Colors.white
                              : AppColors.lightTextPrimary,
                        ),
                        const SizedBox(width: 5),
                        Text(
                          _artifactLabels[type]?.toUpperCase() ??
                              type.toUpperCase(),
                          style: AppTextStyles.smallCapsLabel(
                            fontSize: 9,
                            color: type == _selectedType
                                ? Colors.white
                                : AppColors.lightTextPrimary,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          if (selected != null)
            _ArtifactViewer(
              artifact: selected,
              solutionId: solutionId,
              siblings: detail.artifacts,
            ),
        ],

        const Divider(color: AppColors.lightBorder, height: AppSpacing.xl),
        Text(
          'EXPORT',
          style: AppTextStyles.smallCapsLabel(
            fontSize: 10,
            color: AppColors.gold,
            letterSpacing: 1.5,
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        Row(
          children: [
            for (final format in const ['json', 'markdown', 'zip']) ...[
              Expanded(
                child: SutraButton.outline(
                  label: format.toUpperCase(),
                  height: 36,
                  onPressed: _busy
                      ? null
                      : () => _export(solutionId, format),
                ),
              ),
              if (format != 'zip') const SizedBox(width: AppSpacing.sm),
            ],
          ],
        ),
      ],
    );
  }

  Widget _buildApprovalActions(String solutionId) {
    // Once approved the snapshot is frozen, so offering Approve / Request
    // changes again would let the user edit a blueprint that is already signed
    // off. The web app hides them the same way.
    if (detail.isApproved) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(
          color: AppColors.statusLiveGreen.withValues(alpha: 0.07),
          borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
          border: Border.all(
            color: AppColors.statusLiveGreen.withValues(alpha: 0.3),
          ),
        ),
        child: Row(
          children: [
            const Icon(
              Icons.lock_outline,
              size: 16,
              color: AppColors.statusLiveGreen,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                'Snapshot Frozen - Ready for Build',
                style: AppTextStyles.bodySmall(
                  color: AppColors.statusLiveGreen,
                  fontSize: 12,
                ),
              ),
            ),
          ],
        ),
      );
    }

    return Row(

      children: [
        Expanded(
          child: SutraButton(
            label: 'Approve',
            height: 38,
            isLoading: _busy,
            onPressed: _busy ? null : () => _approve(solutionId),
          ),
        ),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: SutraButton.outline(
            label: 'Request changes',
            height: 38,
            onPressed: _busy ? null : () => _requestChanges(solutionId),
          ),
        ),
      ],
    );
  }

  Future<void> _approve(String solutionId) async {
    setState(() => _busy = true);
    try {
      final result =
          await ref.read(workspaceRepositoryProvider).approveSolution(solutionId);
      ref.invalidate(solutionDetailProvider(solutionId));
      if (mounted) {
        final snapshotted = result['artifacts_snapshotted'];
        _toast(
          context,
          snapshotted == null
              ? 'Blueprint approved.'
              : 'Approved. $snapshotted artifact version(s) snapshotted.',
        );
      }
    } catch (e) {
      if (mounted) _toast(context, 'Approval failed: $e', isError: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _requestChanges(String solutionId) async {
    final comments = await showPromptDialog(
      context: context,
      title: 'Request changes',
      labelText: 'What needs to change?',
      confirmLabel: 'SEND',
      cancelLabel: 'CANCEL',
      maxLines: 4,
    );

    if (comments == null || comments.isEmpty) return;
    if (!mounted) return;

    setState(() => _busy = true);
    try {
      await ref
          .read(workspaceRepositoryProvider)
          .requestSolutionChanges(solutionId, comments);
      ref.invalidate(solutionDetailProvider(solutionId));
      if (mounted) _toast(context, 'Change request sent.');
    } catch (e) {
      if (mounted) _toast(context, 'Could not send request: $e', isError: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _export(String solutionId, String format) async {
    setState(() => _busy = true);
    try {
      final bytes =
          await ref.read(workspaceRepositoryProvider).exportArtifacts(solutionId, format);
      final ext = format == 'markdown' ? 'md' : format;
      final safeTitle = detail.title
          .replaceAll(RegExp(r'[^A-Za-z0-9_-]+'), '_')
          .replaceAll(RegExp(r'_+'), '_');
      await FileDelivery.saveAndShare(
        bytes,
        '${safeTitle.isEmpty ? 'blueprint' : safeTitle}.$ext',
        subject: detail.title,
      );
    } catch (e) {
      if (mounted) _toast(context, 'Export failed: $e', isError: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _toast(BuildContext context, String message, {bool isError = false}) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(message),
          backgroundColor: isError ? AppColors.statusErrorRed : null,
        ),
      );
  }
}

/// Canvas / Details switch shown above the wireframe, same two modes as the
/// web viewer's toolbar.
class _WireframeViewToggle extends StatelessWidget {
  const _WireframeViewToggle({required this.canvas, required this.onChanged});

  final bool canvas;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    Widget button(String label, bool value) {
      final active = canvas == value;
      return GestureDetector(
        onTap: () => onChanged(value),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: active ? AppColors.lightSurface : Colors.transparent,
            border: Border.all(
              color: active ? AppColors.lightBorder : Colors.transparent,
            ),
            borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
          ),
          child: Text(
            label.toUpperCase(),
            style: AppTextStyles.smallCapsLabel(
              fontSize: 9,
              color: active
                  ? AppColors.lightTextPrimary
                  : AppColors.lightTextMuted,
              fontWeight: active ? FontWeight.w700 : FontWeight.w500,
            ),
          ),
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.all(2),
      color: AppColors.lightSurfaceSubtle,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          button('Canvas Editor', true),
          button('Details', false),
        ],
      ),
    );
  }
}

class _ArtifactViewer extends ConsumerStatefulWidget {
  const _ArtifactViewer({
    required this.artifact,
    required this.solutionId,
    required this.siblings,
  });

  final ArtifactModel artifact;
  final String solutionId;

  /// All artifacts of the solution; the wireframe canvas draws every
  /// wireframe together, like the web viewer does.
  final List<ArtifactModel> siblings;

  @override
  ConsumerState<_ArtifactViewer> createState() => _ArtifactViewerState();
}

class _ArtifactViewerState extends ConsumerState<_ArtifactViewer> {
  bool _busy = false;
  bool _wireframeCanvas = true;
  WireframeCanvasState? _canvas;

  bool get _isBpmn {
    final t = widget.artifact.artifactType;
    return t == 'bpmn_flows' || t == 'bpmn';
  }

  bool get _isWireframe => widget.artifact.artifactType == 'wireframe';

  @override
  Widget build(BuildContext context) {
    final body = _renderableBody();
    return SutraCard(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  widget.artifact.title,
                  style: AppTextStyles.bodyMedium(
                    color: AppColors.lightTextPrimary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              Text(
                'v${widget.artifact.version}',
                style: AppTextStyles.mono(
                  fontSize: 10,
                  color: AppColors.lightTextMuted,
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          if (_isWireframe) ...[
            Row(
              children: [
                _WireframeViewToggle(
                  canvas: _wireframeCanvas,
                  onChanged: (v) => setState(() => _wireframeCanvas = v),
                ),
                const Spacer(),
                const Icon(Icons.draw_outlined,
                    size: 13, color: AppColors.lightTextMuted),
                const SizedBox(width: 4),
                Text(
                  'DRAG & CONNECT',
                  style: AppTextStyles.smallCapsLabel(
                    fontSize: 9,
                    color: AppColors.lightTextMuted,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            if (_wireframeCanvas)
              SizedBox(
                height: 420,
                child: _buildWireframeCanvas(),
              )
            else
              _textBox(body),
          ] else if (_isBpmn)
            _themeBox(
              child: BpmnProcessView(
                process: BpmnProcessModel.fromArtifact(widget.artifact),
              ),
            )
          else
            _themeBox(child: MarkdownArtifactView(content: body)),

          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              Expanded(
                child: SutraButton.outline(
                  label: 'Copy',
                  height: 34,
                  onPressed: () async {
                    await Clipboard.setData(ClipboardData(text: body));
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Artifact copied.')),
                      );
                    }
                  },
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: SutraButton.outline(
                  label: 'Export',
                  height: 34,
                  onPressed: _busy ? null : _exportSelf,
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: SutraButton.outline(
                  label: 'History',
                  height: 34,
                  onPressed: _busy ? null : _showHistory,
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              Expanded(
                child: SutraButton.outline(
                  label: _busy ? 'Working...' : 'Regenerate',
                  height: 34,
                  onPressed: _busy ? null : _regenerate,
                ),
              ),
            ],
          ),

          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              Expanded(
                child: SutraButton.outline(
                  label: 'Why?',
                  height: 34,
                  onPressed: () =>
                      showExplainabilityDrawer(context, ref, widget.artifact),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: SutraButton.outline(
                  label: 'Impact preview',
                  height: 34,
                  onPressed: _busy
                      ? null
                      : () => showImpactPreview(
                            context,
                            ref,
                            widget.solutionId,
                            widget.artifact.artifactType,
                            onConfirmed: () {
                              ref.invalidate(solutionDetailProvider);
                              if (context.mounted) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text('Regeneration started.'),
                                  ),
                                );
                              }
                            },
                          ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  /// Dark code panel used for raw/pretty-printed artifacts.
  Widget _textBox(String body) {
    return Container(
      width: double.infinity,
      constraints: const BoxConstraints(maxHeight: 420),
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: AppColors.darkBackground,
        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
      ),
      child: SingleChildScrollView(
        child: SelectableText(
          body,
          style: AppTextStyles.mono(
            fontSize: 11,
            color: AppColors.darkTextPrimary,
          ),
        ),
      ),
    );
  }

  /// Light panel for the rich renderers, matching the web viewer's `bg-2` card.
  Widget _themeBox({required Widget child}) {
    return Container(
      width: double.infinity,
      constraints: const BoxConstraints(maxHeight: 520),
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.lightSurfaceSubtle,
        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
        border: Border.all(color: AppColors.lightBorder),
      ),
      child: SingleChildScrollView(
        child: child,
      ),
    );
  }

  /// Builds the canvas from every wireframe artifact once, then keeps the
  /// edits in local state (the web canvas does not persist them either).
  Widget _buildWireframeCanvas() {
    final wireframes = widget.siblings
        .where((a) => a.artifactType == 'wireframe')
        .toList();
    _canvas ??= buildWireframeCanvas(
      wireframes.isEmpty ? [widget.artifact] : wireframes,
    );
    if (_canvas!.nodes.isEmpty) {
      return Text(
        'This wireframe has no components to lay out yet.',
        style: AppTextStyles.bodySmall(color: AppColors.lightTextSecondary),
      );
    }
    return WireframeCanvasView(
      state: _canvas!,
      onChanged: (s) => setState(() => _canvas = s),
    );
  }

  /// Prefers the server-rendered text, then pretty-prints the structured
  /// content, so JSON/DDL artifacts are not shown as a bare `Map` toString.
  String _renderableBody() {

    final artifact = widget.artifact;
    final text = artifact.contentText;
    if (text != null && text.trim().isNotEmpty) return text;

    if (artifact.content.isNotEmpty) {
      try {
        return const JsonEncoder.withIndent('  ')
            .convert(artifact.content);
      } catch (_) {
        return artifact.content.toString();
      }
    }
    return 'This artifact has no renderable content.';
  }

  /// Writes just this artifact to a file. The web view does the same thing
  /// client-side with a `{artifact_type}-spec.txt` blob.
  Future<void> _exportSelf() async {
    setState(() => _busy = true);
    try {
      final body = _renderableBody();
      final bytes = Uint8List.fromList(utf8.encode(body));
      final type = widget.artifact.artifactType
          .replaceAll(RegExp(r'[^a-zA-Z0-9_-]'), '_')
          .toLowerCase();
      await FileDelivery.saveAndShare(
        bytes,
        '$type-spec.txt',
        subject: widget.artifact.title,
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Export failed: $e'),
            backgroundColor: AppColors.statusErrorRed,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// `GET /artifacts/{solution_id}/history/{artifact_type}` - every prior
  /// version, so the user can see what regeneration changed.
  Future<void> _showHistory() async {
    setState(() => _busy = true);
    try {
      final versions = await ref
          .read(workspaceRepositoryProvider)
          .fetchArtifactHistory(widget.solutionId, widget.artifact.artifactType);
      if (!mounted) return;
      showModalBottomSheet<void>(
        context: context,
        backgroundColor: AppColors.lightSurface,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(AppSpacing.md)),
        ),
        builder: (_) => _ArtifactHistorySheet(
          artifactType: widget.artifact.artifactType,
          versions: versions,
          currentVersion: widget.artifact.version,
        ),
      );
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('History unavailable: $e'),
            backgroundColor: AppColors.statusErrorRed,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _regenerate() async {
    final feedback = await showPromptDialog(
      context: context,
      title: 'Regenerate artifact',
      labelText: 'What should change?',
      confirmLabel: 'REGENERATE',
      cancelLabel: 'CANCEL',
      maxLines: 3,
    );

    if (feedback == null) return;
    if (!mounted) return;

    setState(() => _busy = true);
    try {
      await ref.read(workspaceRepositoryProvider).regenerateArtifact(
            solutionId: widget.solutionId,
            artifactType: widget.artifact.artifactType,
            userFeedback: feedback,
          );
      ref.invalidate(solutionDetailProvider(widget.solutionId));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Regeneration requested.')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Regeneration failed: $e'),
            backgroundColor: AppColors.statusErrorRed,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }
}

class _Pill extends StatelessWidget {
  const _Pill({required this.label, this.accent = false});

  final String label;
  final bool accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: accent ? AppColors.goldSubtle : AppColors.lightSurfaceSubtle,
        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
      ),
      child: Text(
        label,
        style: AppTextStyles.smallCapsLabel(
          fontSize: 9,
          color: accent ? AppColors.goldDark : AppColors.lightTextSecondary,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _MissingSelection extends StatelessWidget {
  const _MissingSelection();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.layers_outlined,
                size: 40, color: AppColors.lightTextMuted),
            const SizedBox(height: AppSpacing.md),
            Text('No blueprint selected',
                style: AppTextStyles.serifHeading(fontSize: 18)),
            const SizedBox(height: AppSpacing.md),
            SutraButton(
              label: 'Go to dashboard',
              onPressed: () => context.go('/dashboard'),
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: [
        const SizedBox(height: AppSpacing.xl),
        const Icon(Icons.cloud_off_outlined,
            size: 40, color: AppColors.statusErrorRed),
        const SizedBox(height: AppSpacing.md),
        Center(
          child: Text(
            message,
            textAlign: TextAlign.center,
            style: AppTextStyles.bodySmall(
              color: AppColors.lightTextSecondary,
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        Center(
          child: SutraButton.outline(
            label: 'Retry',
            onPressed: onRetry,
          ),
        ),
      ],
    );
  }
}

/// Input -> Clarify -> Blueprint -> Approve, derived from the same solution
/// fields the web GuidedStepper reads.
class _GuidedStepper extends StatelessWidget {
  const _GuidedStepper({required this.current, required this.completed});

  final String current;
  final List<String> completed;

  static const _stages = ['input', 'clarify', 'blueprint', 'approve'];
  static const _labels = ['Input', 'Clarify', 'Blueprint', 'Approve'];

  @override
  Widget build(BuildContext context) {
    final currentIndex = _stages.indexOf(current);
    return Row(
      children: [
        for (var i = 0; i < _stages.length; i++) ...[
          if (i > 0)
            Expanded(
              child: Container(
                height: 1,
                color: completed.contains(_stages[i])
                    ? AppColors.gold
                    : AppColors.lightBorder,
              ),
            ),
          Column(
            children: [
              Container(
                width: 22,
                height: 22,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: completed.contains(_stages[i])
                      ? AppColors.gold
                      : i == currentIndex
                          ? AppColors.blackButton
                          : AppColors.lightSurfaceSubtle,
                  border: Border.all(
                    color: i == currentIndex
                        ? AppColors.blackButton
                        : AppColors.lightBorder,
                  ),
                ),
                child: completed.contains(_stages[i])
                    ? const Icon(Icons.check, size: 12, color: Colors.white)
                    : Text(
                        '${i + 1}',
                        style: AppTextStyles.mono(
                          fontSize: 10,
                          color: i == currentIndex
                              ? Colors.white
                              : AppColors.lightTextMuted,
                        ),
                      ),
              ),
              const SizedBox(height: 3),
              Text(
                _labels[i],
                style: AppTextStyles.smallCapsLabel(
                  fontSize: 8,
                  color: i == currentIndex
                      ? AppColors.gold
                      : AppColors.lightTextMuted,
                ),
              ),
            ],
          ),
        ],
      ],
    );
  }
}

/// Architecture and compliance gaps the gap analyzer flagged. Port of the web
/// WhatYouMissedPanel: open questions with their business impact first, then
/// missing NFR / regulatory requirements.
class _WhatYouMissedPanel extends StatelessWidget {
  const _WhatYouMissedPanel({
    required this.requirements,
    required this.questions,
  });

  final List<MissingRequirementModel> requirements;
  final List<OpenQuestionModel> questions;

  @override
  Widget build(BuildContext context) {
    final total = requirements.length + questions.length;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.lightSurfaceSubtle,
        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
        border: Border.all(color: AppColors.gold.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.manage_search,
                size: 18,
                color: AppColors.gold,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'What You Missed: Architecture & Compliance Gaps',
                  style: AppTextStyles.bodyMedium(
                    color: AppColors.lightTextPrimary,
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                  ),
                ),
              ),
              Text(
                '$total ITEMS',
                style: AppTextStyles.smallCapsLabel(
                  fontSize: 9,
                  color: AppColors.gold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 3),
          Text(
            'The gap analyzer flagged essential NFRs, regulatory standards '
            'and open questions.',
            style: AppTextStyles.bodySmall(
              color: AppColors.lightTextSecondary,
              fontSize: 11,
            ),
          ),
          if (questions.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.md),
            Text(
              'CRITICAL CLARIFICATIONS',
              style: AppTextStyles.smallCapsLabel(
                fontSize: 9,
                color: AppColors.gold,
              ),
            ),
            const SizedBox(height: AppSpacing.xs),
            for (final q in questions) _QuestionBlock(question: q),
          ],
          if (requirements.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.md),
            Text(
              'MISSING REQUIREMENTS',
              style: AppTextStyles.smallCapsLabel(
                fontSize: 9,
                color: AppColors.gold,
              ),
            ),
            const SizedBox(height: AppSpacing.xs),
            for (final r in requirements) _RequirementTile(requirement: r),
          ],
        ],
      ),
    );
  }
}

class _QuestionBlock extends StatelessWidget {
  const _QuestionBlock({required this.question});

  final OpenQuestionModel question;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: AppSpacing.sm),
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: AppColors.lightSurface,
        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
        border: Border.all(color: AppColors.lightBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (question.category.isNotEmpty)
            Text(
              question.category.toUpperCase(),
              style: AppTextStyles.smallCapsLabel(
                fontSize: 8,
                color: AppColors.lightTextMuted,
              ),
            ),
          const SizedBox(height: 2),
          Text(
            question.question,
            style: AppTextStyles.bodySmall(
              color: AppColors.lightTextPrimary,
              fontSize: 12,
            ),
          ),
          if (question.whyItMatters.isNotEmpty) ...[
            const SizedBox(height: 3),
            Text(
              question.whyItMatters,
              style: AppTextStyles.bodySmall(
                color: AppColors.lightTextSecondary,
                fontSize: 11,
              ),
            ),
          ],
          if (question.suggestedAnswers.isNotEmpty) ...[
            const SizedBox(height: 5),
            Wrap(
              spacing: 5,
              runSpacing: 5,
              children: [
                for (final answer in question.suggestedAnswers)
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 7,
                      vertical: 3,
                    ),
                    decoration: BoxDecoration(
                      color: AppColors.goldSubtle,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: AppColors.gold.withValues(alpha: 0.35),
                      ),
                    ),
                    child: Text(
                      answer,
                      style: AppTextStyles.mono(
                        fontSize: 9,
                        color: AppColors.goldDark,
                      ),
                    ),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _RequirementTile extends StatelessWidget {
  const _RequirementTile({required this.requirement});

  final MissingRequirementModel requirement;

  @override
  Widget build(BuildContext context) {
    final high = requirement.priority.toLowerCase() == 'high';
    final color = high ? AppColors.statusErrorRed : AppColors.statusWarningAmber;
    return Container(
      margin: const EdgeInsets.only(bottom: AppSpacing.xs),
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: AppColors.lightSurface,
        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
        border: Border.all(color: AppColors.lightBorder),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            margin: const EdgeInsets.only(top: 2),
            padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(3),
            ),
            child: Text(
              requirement.priority.toUpperCase(),
              style: AppTextStyles.smallCapsLabel(fontSize: 7, color: color),
            ),
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  requirement.kind,
                  style: AppTextStyles.smallCapsLabel(
                    fontSize: 8,
                    color: AppColors.lightTextMuted,
                  ),
                ),
                Text(
                  requirement.text,
                  style: AppTextStyles.bodySmall(
                    color: AppColors.lightTextPrimary,
                    fontSize: 12,
                  ),
                ),
                for (final e in requirement.evidence)
                  Padding(
                    padding: const EdgeInsets.only(top: 3),
                    child: Text(
                      '${e.source}: ${e.excerpt}',
                      style: AppTextStyles.mono(
                        fontSize: 9,
                        color: AppColors.lightTextMuted,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Prior versions of one artifact type, newest first.
class _ArtifactHistorySheet extends StatelessWidget {
  const _ArtifactHistorySheet({
    required this.artifactType,
    required this.versions,
    required this.currentVersion,
  });

  final String artifactType;
  final List<ArtifactModel> versions;
  final int currentVersion;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'VERSION HISTORY',
              style: AppTextStyles.smallCapsLabel(
                fontSize: 10,
                color: AppColors.gold,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              artifactType,
              style: AppTextStyles.mono(
                fontSize: 11,
                color: AppColors.lightTextSecondary,
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            if (versions.isEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.md),
                child: Text(
                  'No earlier versions recorded.',
                  style: AppTextStyles.bodySmall(
                    color: AppColors.lightTextSecondary,
                  ),
                ),
              )
            else
              Flexible(
                child: ListView.separated(
                  shrinkWrap: true,
                  itemCount: versions.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 6),
                  itemBuilder: (context, i) {
                    final v = versions[i];
                    final isCurrent = v.version == currentVersion;
                    return Container(
                      padding: const EdgeInsets.all(AppSpacing.sm),
                      decoration: BoxDecoration(
                        color: AppColors.lightSurfaceSubtle,
                        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                        border: Border.all(
                          color: isCurrent
                              ? AppColors.gold
                              : AppColors.lightBorder,
                        ),
                      ),
                      child: Row(
                        children: [
                          Text(
                            'v${v.version}',
                            style: AppTextStyles.mono(
                              fontSize: 11,
                              color: isCurrent
                                  ? AppColors.gold
                                  : AppColors.lightTextMuted,
                            ),
                          ),
                          const SizedBox(width: AppSpacing.sm),
                          Expanded(
                            child: Text(
                              v.title,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: AppTextStyles.bodySmall(
                                color: AppColors.lightTextPrimary,
                                fontSize: 12,
                              ),
                            ),
                          ),
                          Text(
                            v.createdAt ?? '',

                            style: AppTextStyles.mono(
                              fontSize: 9,
                              color: AppColors.lightTextMuted,
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ),
          ],
        ),
      ),
    );
  }
}