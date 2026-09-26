import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/widgets/sutra_button.dart';
import '../data/workspace_repository.dart';
import '../domain/workspace_models.dart';

/// "Why? (Decision Log)" — the web app's ExplainabilityDrawer.
Future<void> showExplainabilityDrawer(
  BuildContext context,
  WidgetRef ref,
  ArtifactModel artifact,
) =>
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.lightSurface,
      shape: const RoundedRectangleBorder(
        borderRadius:
            BorderRadius.vertical(top: Radius.circular(AppSpacing.radiusLg)),
      ),
      builder: (_) => _ExplainabilitySheet(artifact: artifact),
    );

class _ExplainabilitySheet extends ConsumerStatefulWidget {
  const _ExplainabilitySheet({required this.artifact});

  final ArtifactModel artifact;

  @override
  ConsumerState<_ExplainabilitySheet> createState() =>
      _ExplainabilitySheetState();
}

class _ExplainabilitySheetState extends ConsumerState<_ExplainabilitySheet> {
  ExplainabilityModel? _data;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final data = await ref
          .read(workspaceRepositoryProvider)
          .fetchExplainability(widget.artifact.id);
      if (!mounted) return;
      setState(() {
        _data = data;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = '$e';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.85,
      maxChildSize: 0.95,
      builder: (context, controller) => ListView(
        controller: controller,
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'WHY? ${widget.artifact.title.toUpperCase()}',
                  style: AppTextStyles.smallCapsLabel(
                    fontSize: 11,
                    color: AppColors.lightTextPrimary,
                  ),
                ),
              ),
              if ((_data?.confidence ?? 0) > 0)
                Text(
                  '${(_data!.confidence * 100).round()}% CONFIDENCE',
                  style: AppTextStyles.smallCapsLabel(
                    fontSize: 9,
                    color: AppColors.gold,
                  ),
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          if (_loading)
            const Padding(
              padding: EdgeInsets.all(AppSpacing.lg),
              child: Center(
                child: CircularProgressIndicator(color: AppColors.gold),
              ),
            )
          else if (_error != null)
            Text(
              'Could not load the decision log: $_error',
              style: AppTextStyles.bodySmall(color: AppColors.statusErrorRed),
            )
          else if (_data!.isEmpty)
            Text(
              'No decision log was recorded for this artifact.',
              style: AppTextStyles.bodySmall(
                color: AppColors.lightTextSecondary,
              ),
            )
          else ...[
            if (_data!.title.isNotEmpty) ...[
              Text(
                _data!.title,
                style: AppTextStyles.serifHeading(fontSize: 16),
              ),
              const SizedBox(height: AppSpacing.sm),
            ],
            if (_data!.decisions.isNotEmpty) ...[
              _SectionLabel('KEY DECISIONS (${_data!.decisions.length})'),
              for (final d in _data!.decisions) _DecisionBlock(decision: d),
            ],
            if (_data!.assumptions.isNotEmpty) ...[
              _SectionLabel('UNDERLYING ASSUMPTIONS'),
              for (final a in _data!.assumptions)
                _BulletLine(text: a),
            ],
            if (_data!.evidence.isNotEmpty) ...[
              _SectionLabel('EVIDENCE CITATIONS (${_data!.evidence.length})'),
              for (final e in _data!.evidence) _EvidenceBlock(evidence: e),
            ],
          ],
        ],
      ),
    );
  }
}

class _DecisionBlock extends StatelessWidget {
  const _DecisionBlock({required this.decision});

  final DecisionModel decision;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: AppSpacing.sm),
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: AppColors.lightSurfaceSubtle,
        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
        border: Border.all(color: AppColors.lightBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (decision.topic.isNotEmpty)
            Text(
              decision.topic.toUpperCase(),
              style: AppTextStyles.smallCapsLabel(
                fontSize: 9,
                color: AppColors.gold,
              ),
            ),
          if (decision.choice.isNotEmpty)
            Text(
              decision.choice,
              style: AppTextStyles.bodyMedium(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: AppColors.lightTextPrimary,
              ),
            ),
          if (decision.rationale.isNotEmpty)
            Text(
              decision.rationale,
              style: AppTextStyles.bodySmall(
                color: AppColors.lightTextSecondary,
              ),
            ),
          if (decision.alternatives.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              'Alternatives: ${decision.alternatives.join(', ')}',
              style: AppTextStyles.mono(
                fontSize: 10,
                color: AppColors.lightTextMuted,
              ),
            ),
          ],
          if (decision.impact.isNotEmpty)
            Text(
              'Impact: ${decision.impact}',
              style: AppTextStyles.mono(
                fontSize: 10,
                color: AppColors.lightTextMuted,
              ),
            ),
          if (decision.confidence > 0)
            Text(
              '${(decision.confidence * 100).round()}% confidence',
              style: AppTextStyles.mono(
                fontSize: 10,
                color: AppColors.lightTextMuted,
              ),
            ),
          for (final a in decision.assumptions)
            _BulletLine(text: a, dense: true),
        ],
      ),
    );
  }
}

class _EvidenceBlock extends StatelessWidget {
  const _EvidenceBlock({required this.evidence});

  final EvidenceModel evidence;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: AppSpacing.xs),
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: AppColors.lightSurfaceSubtle,
        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
        border: Border.all(color: AppColors.lightBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (evidence.source.isNotEmpty)
            Text(
              evidence.source,
              style: AppTextStyles.mono(
                fontSize: 10,
                color: AppColors.gold,
              ),
            ),
          if (evidence.excerpt.isNotEmpty)
            Text(
              evidence.excerpt,
              style: AppTextStyles.mono(
                fontSize: 11,
                color: AppColors.lightTextPrimary,
              ),
            ),
        ],
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);

  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(
          top: AppSpacing.sm,
          bottom: AppSpacing.xs,
        ),
        child: Text(
          text,
          style: AppTextStyles.smallCapsLabel(
            fontSize: 9,
            color: AppColors.lightTextMuted,
          ),
        ),
      );
}

class _BulletLine extends StatelessWidget {
  const _BulletLine({required this.text, this.dense = false});

  final String text;
  final bool dense;

  @override
  Widget build(BuildContext context) => Padding(
        padding: EdgeInsets.only(bottom: dense ? 2 : 4),
        child: Text(
          '- $text',
          style: AppTextStyles.bodySmall(
            fontSize: dense ? 11 : 12,
            color: AppColors.lightTextSecondary,
          ),
        ),
      );
}

/// "Impact Preview" — quotes the blast radius and credits before regenerating.
///
/// Uses `dry_run: true` so opening the sheet never spends credits or mutates
/// anything; the real call only fires after the user confirms.
Future<void> showImpactPreview(
  BuildContext context,
  WidgetRef ref,
  String solutionId,
  String artifactType, {
  required VoidCallback onConfirmed,
}) =>
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.lightSurface,
      shape: const RoundedRectangleBorder(
        borderRadius:
            BorderRadius.vertical(top: Radius.circular(AppSpacing.radiusLg)),
      ),
      builder: (_) => _ImpactPreviewSheet(
        solutionId: solutionId,
        artifactType: artifactType,
        onConfirmed: onConfirmed,
      ),
    );

class _ImpactPreviewSheet extends ConsumerStatefulWidget {
  const _ImpactPreviewSheet({
    required this.solutionId,
    required this.artifactType,
    required this.onConfirmed,
  });

  final String solutionId;
  final String artifactType;
  final VoidCallback onConfirmed;

  @override
  ConsumerState<_ImpactPreviewSheet> createState() =>
      _ImpactPreviewSheetState();
}

class _ImpactPreviewSheetState extends ConsumerState<_ImpactPreviewSheet> {
  bool _cascade = true;
  bool _busy = false;
  bool _evaluating = true;
  List<String> _affected = const [];
  int _credits = 0;
  String? _error;

  @override
  void initState() {
    super.initState();
    _evaluate();
  }

  Future<void> _evaluate() async {
    setState(() {
      _evaluating = true;
      _error = null;
    });
    try {
      final data = await ref
          .read(workspaceRepositoryProvider)
          .regenerateArtifacts(
            widget.solutionId,
            targets: [widget.artifactType],
            feedback: 'Impact evaluation',
            cascade: _cascade,
            dryRun: true,
          );
      if (!mounted) return;
      setState(() {
        _affected =
            (data['affected_artifacts'] as List?)?.map((e) => e.toString()).toList() ??
                [widget.artifactType];
        _credits = (data['estimated_credits'] as num?)?.toInt() ?? 0;
        _evaluating = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = '$e';
        _evaluating = false;
      });
    }
  }

  Future<void> _confirm() async {
    setState(() => _busy = true);
    try {
      await ref
          .read(workspaceRepositoryProvider)
          .regenerateArtifacts(
            widget.solutionId,
            targets: [widget.artifactType],
            feedback: 'Regeneration confirmed from impact preview',
            cascade: _cascade,
            dryRun: false,
          );
      if (!mounted) return;
      Navigator.of(context).pop();
      widget.onConfirmed();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = 'Regeneration failed: $e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final insets = MediaQuery.of(context).viewInsets.bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(
        AppSpacing.md,
        AppSpacing.md,
        AppSpacing.md,
        AppSpacing.md + insets,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'IMPACT PREVIEW & CREDIT QUOTE',
              style: AppTextStyles.smallCapsLabel(
                fontSize: 11,
                color: AppColors.lightTextPrimary,
              ),
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              'Regenerating ${widget.artifactType.replaceAll('_', ' ')}',
              style: AppTextStyles.bodySmall(
                color: AppColors.lightTextSecondary,
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            SwitchListTile(
              value: _cascade,
              onChanged: (v) {
                setState(() => _cascade = v);
                // Cascade changes the dependency set, so re-quote.
                _evaluate();
              },
              title: Text(
                'Cascade to dependent artifacts',
                style: AppTextStyles.bodySmall(
                  color: AppColors.lightTextPrimary,
                ),
              ),
              contentPadding: EdgeInsets.zero,
              dense: true,
            ),
            const SizedBox(height: AppSpacing.sm),
            if (_evaluating)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(AppSpacing.md),
                  child: CircularProgressIndicator(color: AppColors.gold),
                ),
              )
            else ...[
              Text(
                '${_affected.length} AFFECTED ARTIFACT${_affected.length == 1 ? '' : 'S'}',
                style: AppTextStyles.smallCapsLabel(
                  fontSize: 9,
                  color: AppColors.lightTextMuted,
                ),
              ),
              const SizedBox(height: AppSpacing.xs),
              for (final a in _affected)
                Padding(
                  padding: const EdgeInsets.only(bottom: 2),
                  child: Text(
                    '- $a',
                    style: AppTextStyles.mono(
                      fontSize: 11,
                      color: AppColors.lightTextPrimary,
                    ),
                  ),
                ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                'ESTIMATED CREDITS: $_credits',
                style: AppTextStyles.smallCapsLabel(
                  fontSize: 9,
                  color: AppColors.gold,
                ),
              ),
            ],
            if (_error != null) ...[
              const SizedBox(height: AppSpacing.sm),
              Text(
                _error!,
                style: AppTextStyles.bodySmall(color: AppColors.statusErrorRed),
              ),
            ],
            const SizedBox(height: AppSpacing.md),
            SutraButton(
              label: _busy ? 'Regenerating...' : 'Confirm regeneration',
              onPressed: _busy || _evaluating ? null : _confirm,
            ),
          ],
        ),
      ),
    );
  }
}
