import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../core/network/api_exceptions.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/utils/file_delivery.dart';
import '../../../core/widgets/prompt_dialog.dart';
import '../../../core/widgets/sutra_button.dart';
import '../../../core/widgets/sutra_card.dart';
import '../../../core/widgets/voice_input_button.dart';
import '../data/workspace_repository.dart';
import '../../chat/application/chat_controller.dart';
import '../domain/workspace_models.dart';
import 'mvp_build_sheets.dart';
import 'workspace_providers.dart';

/// Build lifecycle for the active solution: trigger a build, watch it progress,
/// download the archive, and open the live preview.
///
/// The web app exposes this on `/dashboard`, `/chat`, and `/solution/[id]/mvp`
/// via `BuildCard`. The Flutter app had no UI for any of it, so
/// `mvpBuildsProvider` was defined but never observed and the build endpoints
/// were unreachable.
class MvpBuildsScreen extends ConsumerStatefulWidget {
  const MvpBuildsScreen({super.key});

  @override
  ConsumerState<MvpBuildsScreen> createState() => _MvpBuildsScreenState();
}

class _MvpBuildsScreenState extends ConsumerState<MvpBuildsScreen> {
  bool _isTriggering = false;

  @override
  Widget build(BuildContext context) {
    final solutionId = ref.watch(effectiveSolutionIdProvider);
    final buildsAsync =
        solutionId == null ? null : ref.watch(mvpBuildsProvider(solutionId));

    return DefaultTabController(
      length: 4,
      child: Scaffold(
        backgroundColor: AppColors.lightBackground,
        appBar: AppBar(
          backgroundColor: AppColors.lightSurface,
          surfaceTintColor: Colors.transparent,
          title: Text('Builds', style: AppTextStyles.serifHeading(fontSize: 20)),
          bottom: const TabBar(
            labelColor: AppColors.lightTextPrimary,
            unselectedLabelColor: AppColors.lightTextMuted,
            indicatorColor: AppColors.gold,
            indicatorSize: TabBarIndicatorSize.label,
            dividerColor: AppColors.lightBorder,
            isScrollable: true,
            tabAlignment: TabAlignment.start,
            tabs: [
              Tab(text: 'ARCHITECT CHAT'),
              Tab(text: 'TEMPLATES'),
              Tab(text: 'BUILDS'),
              Tab(text: 'HISTORY & DEPLOYS'),
            ],
          ),
        ),
        body: solutionId == null
            ? _missingSolution()
            : TabBarView(
                children: [
                  _architectChatTab(solutionId),
                  _templatesTab(),
                  _buildsTab(buildsAsync, solutionId),
                  _historyTabView(buildsAsync),
                ],
              ),
      ),
    );
  }

  Widget _buildsTab(
      AsyncValue<List<MVPBuildModel>>? buildsAsync, String solutionId) {
    if (buildsAsync == null) return _missingSolution();
    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(mvpBuildsProvider(solutionId));
        await ref.read(mvpBuildsProvider(solutionId).future);
      },
      child: buildsAsync.when(
        loading: () => const Center(
          child: CircularProgressIndicator(color: AppColors.blackButton),
        ),
        error: (error, _) => _errorState(error),
        data: (builds) => _buildList(builds, solutionId),
      ),
    );
  }

  Widget _historyTabView(AsyncValue<List<MVPBuildModel>>? buildsAsync) {
    if (buildsAsync == null) return _historyTab(const []);
    return buildsAsync.when(
      loading: () => const Center(
        child: CircularProgressIndicator(color: AppColors.blackButton),
      ),
      error: (error, _) => _errorState(error),
      data: (builds) => _historyTab(builds),
    );
  }

  /// Solution-scoped architect chat, the default tab of the web MVP page.
  /// Same `POST /opencode/chat` stream as `/chat`, but anchored to this
  /// solution and with the same suggested technical inquiries.
  Widget _architectChatTab(String solutionId) {
    return _ArchitectChat(
      solutionId: solutionId,
      onBuildRequested: () => _triggerBuild(solutionId),
    );
  }

  /// `GET /mvp/templates` + `POST /mvp/quick-build`.
  Widget _templatesTab() {
    final templatesAsync = ref.watch(mvpTemplatesProvider);
    return templatesAsync.when(
      loading: () =>
          const Center(child: CircularProgressIndicator(color: AppColors.gold)),
      error: (e, _) => _errorState(e),
      data: (templates) {
        if (templates.isEmpty) {
          return const Center(child: Text('No templates available yet.'));
        }
        return ListView.separated(
          padding: const EdgeInsets.all(AppSpacing.md),
          itemCount: templates.length,
          separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
          itemBuilder: (context, i) {
            final t = templates[i];
            return SutraCard(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    t.title,
                    style: AppTextStyles.bodyMedium(
                      color: AppColors.lightTextPrimary,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    t.description,
                    style: AppTextStyles.bodySmall(
                      color: AppColors.lightTextSecondary,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Wrap(
                    spacing: 6,
                    runSpacing: 4,
                    children: [
                      if (t.appName.isNotEmpty)
                        _TemplateChip(label: t.appName),
                      if (t.industry.isNotEmpty)
                        _TemplateChip(label: t.industry),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  SutraButton(
                    label: 'Quick build',
                    height: 36,
                    onPressed: () => _quickBuild(t),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  Future<void> _quickBuild(MVPTemplateModel template) async {
    final name = await showPromptDialog(
      context: context,
      title: template.title,
      initialValue: template.appName,
      labelText: 'App name',
      confirmLabel: 'BUILD',
      cancelLabel: 'CANCEL',
    );
    if (name == null || name.isEmpty || !mounted) return;

    _toast(context, 'Starting quick build...');
    try {
      final build = await ref
          .read(workspaceRepositoryProvider)
          .quickBuildMvp(template: template.slug, appName: name);
      ref.read(activeSolutionIdProvider.notifier).set(build.solutionId);
      ref.invalidate(mvpBuildsProvider(build.solutionId));
      if (mounted) _toast(context, 'Quick build started.');
    } catch (e) {
      if (mounted) _toast(context, 'Quick build failed: $e', isError: true);
    }
  }

  /// Chronological build log with deploy state, mirroring the web app's
  /// "Build History & Deploys" tab.
  Widget _historyTab(List<MVPBuildModel> builds) {
    if (builds.isEmpty) {
      return ListView(
        padding: const EdgeInsets.all(AppSpacing.lg),
        children: [
          const SizedBox(height: AppSpacing.xxl),
          Center(
            child: Text(
              'No build history yet.',
              style: AppTextStyles.bodySmall(
                color: AppColors.lightTextSecondary,
              ),
            ),
          ),
        ],
      );
    }

    final sorted = [...builds]
      ..sort((a, b) => b.buildNumber.compareTo(a.buildNumber));

    return ListView.separated(
      padding: const EdgeInsets.all(AppSpacing.lg),
      itemCount: sorted.length,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
      itemBuilder: (context, i) {
        final b = sorted[i];
        final deployed = b.renderDeployStatus == 'live';
        return SutraCard(
          padding: const EdgeInsets.all(AppSpacing.sm),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                width: 34,
                child: Text(
                  '#${b.buildNumber}',
                  style: AppTextStyles.mono(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: AppColors.lightTextSecondary,
                  ),
                ),
              ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      b.statusLabel,
                      style: AppTextStyles.bodySmall(
                        fontSize: 11,
                        color: AppColors.lightTextPrimary,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    if (b.workspacePath.isNotEmpty)
                      Text(
                        b.workspacePath,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppTextStyles.mono(
                          fontSize: 9,
                          color: AppColors.lightTextMuted,
                        ),
                      ),
                    Text(
                      deployed
                          ? 'Deployed: ${b.renderServiceUrl ?? b.frontendUrl ?? 'live'}'
                          : (b.renderDeployStatus == null
                              ? 'Not deployed'
                              : 'Deploy: ${b.renderDeployStatus}'),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.mono(
                        fontSize: 9,
                        color: deployed
                            ? AppColors.statusLiveGreen
                            : AppColors.lightTextSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              _StatusBadge(status: b.status, inFlight: isBuildInFlight(b)),
            ],
          ),
        );
      },
    );
  }

  Widget _missingSolution() {
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
            const SizedBox(height: AppSpacing.xs),
            Text(
              'Pick a blueprint from the workspace switcher first.',
              textAlign: TextAlign.center,
              style: AppTextStyles.bodySmall(
                color: AppColors.lightTextSecondary,
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            SutraButton(
              label: 'Go to workspace',
              onPressed: () => context.go('/workspace'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _errorState(Object error) {
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: [
        const SizedBox(height: AppSpacing.xl),
        const Icon(Icons.cloud_off_outlined,
            size: 40, color: AppColors.statusErrorRed),
        const SizedBox(height: AppSpacing.md),
        Center(
          child: Text(
            error is ApiException ? error.message : 'Builds unavailable.',
            textAlign: TextAlign.center,
            style: AppTextStyles.bodySmall(
              color: AppColors.lightTextSecondary,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildList(List<MVPBuildModel> builds, String solutionId) {
    if (builds.isEmpty) {
      return ListView(
        padding: const EdgeInsets.all(AppSpacing.lg),
        children: [
          const SizedBox(height: AppSpacing.xxl),
          const Icon(Icons.inventory_2_outlined,
              size: 40, color: AppColors.lightTextMuted),
          const SizedBox(height: AppSpacing.md),
          Center(
            child: Text(
              'No builds yet for this blueprint.',
              style: AppTextStyles.bodySmall(
                color: AppColors.lightTextSecondary,
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          SutraButton(
            label: _isTriggering ? 'Dispatching...' : 'Build now',
            isLoading: _isTriggering,
            width: double.infinity,
            onPressed: _isTriggering
                ? null
                : () => _triggerBuild(solutionId),
          ),
        ],
      );
    }

    final sorted = [...builds]
      ..sort((a, b) => b.buildNumber.compareTo(a.buildNumber));

    return ListView.separated(
      padding: const EdgeInsets.all(AppSpacing.lg),
      itemCount: sorted.length + 1,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
      itemBuilder: (context, index) {
        if (index == 0) {
          return Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.sm),
            child: SutraButton(
              label: _isTriggering ? 'Dispatching...' : 'Build now',
              isLoading: _isTriggering,
              width: double.infinity,
              onPressed: _isTriggering
                  ? null
                  : () => _triggerBuild(solutionId),
            ),
          );
        }
        return _BuildCard(model: sorted[index - 1]);
      },
    );
  }

  Future<void> _triggerBuild(String solutionId) async {
    setState(() => _isTriggering = true);
    try {
      await ref.read(workspaceRepositoryProvider).buildSolutionMvp(solutionId);
      ref.invalidate(mvpBuildsProvider(solutionId));
      if (mounted) {
        _toast(context, 'Build dispatched.');
      }
    } catch (e) {
      if (mounted) _toast(context, 'Build failed: $e', isError: true);
    } finally {
      if (mounted) setState(() => _isTriggering = false);
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

class _BuildCard extends ConsumerWidget {
  const _BuildCard({required this.model});

  final MVPBuildModel model;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Live status while the job runs; the listed snapshot once it settles.
    final liveAsync = ref.watch(buildStatusProvider(model.buildId));
    final resolved = liveAsync.valueOrNull ?? model;

    final inFlight = isBuildInFlight(resolved);

    final previewUrl = resolved.frontendUrl ?? resolved.renderServiceUrl;
    final deployStatus = resolved.renderDeployStatus;
    final isDeployed = deployStatus == 'live';
    final progress = resolved.progress;
    final quality = resolved.quality;

    return SutraCard(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'Build #${resolved.buildNumber}',
                  style: AppTextStyles.bodyMedium(
                    color: AppColors.lightTextPrimary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              _StatusBadge(status: resolved.status, inFlight: inFlight),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            '${resolved.fileCount} files • ${resolved.workspacePath.isEmpty ? 'workspace pending' : resolved.workspacePath}',
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: AppTextStyles.mono(
              fontSize: 10,
              color: AppColors.lightTextSecondary,
            ),
          ),
          if (deployStatus != null) ...[
            const SizedBox(height: AppSpacing.xs),
            Row(
              children: [
                const Icon(Icons.cloud_outlined,
                    size: 13, color: AppColors.lightTextSecondary),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    'Render: $deployStatus',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.bodySmall(
                      color: AppColors.lightTextSecondary,
                      fontSize: 11,
                    ),
                  ),
                ),
              ],
            ),
          ],
          if (quality != null) ...[
            const SizedBox(height: AppSpacing.xs),
            _QualityBadge(quality: resolved.quality!),
          ],
          if (progress != null && inFlight) ...[
            const SizedBox(height: AppSpacing.sm),
            _ProgressStepper(progress: progress),
          ],
          if (resolved.isFailed && resolved.errorMessage != null) ...[
            const SizedBox(height: AppSpacing.sm),
            _ErrorPanel(message: resolved.errorMessage!),
          ],
          if (resolved.files.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            _FileTreePanel(
              files: resolved.files,
              onTap: (path) => context.go(
                '/sandbox?build=${Uri.encodeComponent(resolved.buildId)}',
              ),
            ),
          ],
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              Expanded(
                child: SutraButton.outline(
                  label: 'Preview',
                  height: 34,
                  onPressed: previewUrl == null
                      ? null
                      : () => _openPreview(context, previewUrl),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: SutraButton.outline(
                  label: 'Download',
                  height: 34,
                  onPressed: inFlight
                      ? null
                      : () => _download(context, ref),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              Expanded(
                child: SutraButton.outline(
                  label: 'Configure',
                  height: 34,
                  onPressed: inFlight
                      ? null
                      : () => showConfigureBuildSheet(context, ref, resolved),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: SutraButton(
                  label: isDeployed ? 'Deployed' : 'Deploy',
                  height: 34,
                  // A build has to finish before it can be pushed anywhere.
                  onPressed: inFlight
                      ? null
                      : () => showDeployBuildSheet(context, ref, resolved),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              Expanded(
                child: SutraButton.outline(
                  label: 'Live app',
                  height: 34,
                  onPressed: resolved.liveAppUrl == null
                      ? null
                      : () => _openExternal(context, resolved.liveAppUrl!),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: SutraButton.outline(
                  label: 'GitHub',
                  height: 34,
                  onPressed: resolved.repoUrl == null
                      ? null
                      : () => _openExternal(context, resolved.repoUrl!),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: SutraButton.outline(
                  label: 'API docs',
                  height: 34,
                  onPressed: () => _openExternal(
                    context,
                    '${ApiEndpoints.baseUrl}/docs',
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              if (previewUrl != null) ...[
                Expanded(
                  child: SutraButton.outline(
                    label: 'Teardown',
                    height: 34,
                    onPressed: () => _teardown(context, ref),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
              ],
              Expanded(
                child: SutraButton.outline(
                  label: resolved.isFailed ? 'Clear build' : 'Delete',
                  height: 34,
                  onPressed: () => _delete(context, ref),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  /// Opens a deployed URL outside the app. `url_launcher` is already a
  /// dependency (billing invoice preview and the login links use it).
  Future<void> _openExternal(BuildContext context, String url) async {
    final uri = Uri.tryParse(url);
    if (uri == null) return;
    final ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!ok && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not open $url')),
      );
    }
  }

  /// `POST /mvp/builds/{id}/preview/destroy` — stop the running preview.
  Future<void> _teardown(BuildContext context, WidgetRef ref) async {
    final ok = await _confirm(
      context,
      'Teardown preview',
      'Stop the running preview for build #${model.buildNumber}? '
      'You can deploy it again at any time.',
    );
    if (!ok) return;
    try {
      await ref.read(workspaceRepositoryProvider).destroyPreview(model.buildId);
      ref.invalidate(buildStatusProvider(model.buildId));
      if (context.mounted) _toast(context, 'Preview stopped.');
    } catch (e) {
      if (context.mounted) _toast(context, 'Teardown failed: $e', isError: true);
    }
  }

  /// `DELETE /mvp/builds/{id}` — remove a failed/cancelled build.
  Future<void> _delete(BuildContext context, WidgetRef ref) async {
    final ok = await _confirm(
      context,
      'Delete build',
      'Delete build #${model.buildNumber} and its generated files? '
      'This cannot be undone.',
    );
    if (!ok) return;
    try {
      await ref.read(workspaceRepositoryProvider).deleteBuild(model.buildId);
      ref.invalidate(mvpBuildsProvider);
      if (context.mounted) _toast(context, 'Build deleted.');
    } catch (e) {
      if (context.mounted) _toast(context, 'Delete failed: $e', isError: true);
    }
  }

  void _openPreview(BuildContext context, String url) {
    // Route to the sandbox viewer rather than dumping the user out to a browser.
    context.go('/sandbox?build=${Uri.encodeComponent(model.buildId)}');
  }

  Future<void> _download(BuildContext context, WidgetRef ref) async {
    try {
      final bytes =
          await ref.read(workspaceRepositoryProvider).downloadBuild(model.buildId);
      if (bytes.isEmpty) {
        if (!context.mounted) return;
        _toast(context, 'That build produced no archive.', isError: true);
        return;
      }

      final short = model.buildId.length > 8
          ? model.buildId.substring(0, 8)
          : model.buildId;
      await FileDelivery.saveAndShare(
        bytes,
        'sutra_build_$short.zip',
        subject: 'Sutra build #${model.buildNumber}',
      );
    } catch (e) {
      if (context.mounted) _toast(context, 'Download failed: $e', isError: true);
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

  /// Guard for destructive actions so a mis-tap cannot delete a build.
  Future<bool> _confirm(
    BuildContext context,
    String title,
    String body,
  ) async {
    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.lightSurface,
        title: Text(title, style: AppTextStyles.serifHeading(fontSize: 17)),
        content: Text(
          body,
          style: AppTextStyles.bodySmall(color: AppColors.lightTextSecondary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(
              'Confirm',
              style: AppTextStyles.bodySmall(color: AppColors.gold),
            ),
          ),
        ],
      ),
    );
    return result ?? false;
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.status, required this.inFlight});

  final String status;
  final bool inFlight;

  @override
  Widget build(BuildContext context) {
    final label = switch (status.toLowerCase()) {
      'complete' || 'succeeded' || 'success' => 'COMPLETE',
      'failed' || 'error' => 'FAILED',
      'building' || 'running' => 'BUILDING',
      'queued' || 'pending' => 'QUEUED',
      _ => status.toUpperCase(),
    };
    final color = switch (status.toLowerCase()) {
      'complete' || 'succeeded' || 'success' => AppColors.statusLiveGreen,
      'failed' || 'error' => AppColors.statusErrorRed,
      _ => AppColors.goldDark,
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (inFlight) ...[
            const SizedBox(
              width: 8,
              height: 8,
              child: CircularProgressIndicator(strokeWidth: 1.5),
            ),
            const SizedBox(width: 5),
          ],
          Text(
            label,
            style: AppTextStyles.smallCapsLabel(
              fontSize: 8,
              color: color,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

/// Acceptance-test outcome from the build's verification phase.
class _QualityBadge extends StatelessWidget {
  const _QualityBadge({required this.quality});

  final MVPQualityModel quality;

  @override
  Widget build(BuildContext context) {
    final color = quality.isPassing
        ? AppColors.statusLiveGreen
        : AppColors.statusWarningAmber;
    final repairs = quality.repairLoops == 1
        ? '1 repair loop'
        : '${quality.repairLoops} repair loops';
    return Row(
      children: [
        Icon(
          quality.isPassing
              ? Icons.verified_outlined
              : Icons.report_problem_outlined,
          size: 13,
          color: color,
        ),
        const SizedBox(width: 4),
        Expanded(
          child: Text(
            '${quality.passed}/${quality.total} CHECKS * $repairs',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: AppTextStyles.bodySmall(color: color, fontSize: 11),
          ),
        ),
      ],
    );
  }
}

/// The 5-step build stepper, mirroring `BUILD_STEPS` in the backend so the
/// mobile step labels match the web BuildCard.
class _ProgressStepper extends StatelessWidget {
  const _ProgressStepper({required this.progress});

  final MVPProgressModel progress;

  @override
  Widget build(BuildContext context) {
    final steps = progress.steps;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                progress.message.isEmpty
                    ? 'STEP ${progress.step}/${progress.totalSteps}'
                    : progress.message,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppTextStyles.bodySmall(
                  color: AppColors.lightTextPrimary,
                  fontSize: 11,
                ),
              ),
            ),
            Text(
              '${progress.percentage}%',
              style: AppTextStyles.mono(fontSize: 10, color: AppColors.gold),
            ),
          ],
        ),
        const SizedBox(height: 5),
        ClipRRect(
          borderRadius: BorderRadius.circular(2),
          child: LinearProgressIndicator(
            value: (progress.percentage / 100).clamp(0.0, 1.0),
            minHeight: 3,
            backgroundColor: AppColors.lightSurfaceSubtle,
            color: AppColors.gold,
          ),
        ),
        if (steps.isNotEmpty) ...[
          const SizedBox(height: 5),
          Row(
            children: [
              for (var i = 0; i < steps.length; i++) ...[
                Expanded(
                  child: Tooltip(
                    message: steps[i].label,
                    child: Container(
                      height: 3,
                      decoration: BoxDecoration(
                        color: switch (steps[i].status) {
                          'completed' => AppColors.gold,
                          'active' => AppColors.statusLiveGreen,
                          _ => AppColors.lightBorder,
                        },
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                ),
                if (i < steps.length - 1) const SizedBox(width: 3),
              ],
            ],
          ),
        ],
      ],
    );
  }
}

/// Why a build failed. The backend stores the exception in `error_message`,
/// so surface it instead of a bare FAILED pill.
class _ErrorPanel extends StatelessWidget {
  const _ErrorPanel({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: AppColors.statusErrorRed.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
        border: Border.all(
          color: AppColors.statusErrorRed.withValues(alpha: 0.3),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.error_outline,
            size: 14,
            color: AppColors.statusErrorRed,
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              message,
              style: AppTextStyles.mono(
                fontSize: 10,
                color: AppColors.statusErrorRed,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Collapsed file tree on the build card, tappable through to the sandbox.
class _FileTreePanel extends StatelessWidget {
  const _FileTreePanel({required this.files, required this.onTap});

  final List<MVPFileEntryModel> files;
  final ValueChanged<String> onTap;

  @override
  Widget build(BuildContext context) {
    final visible = files.take(4).toList();
    final extra = files.length - visible.length;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: AppColors.lightSurfaceSubtle,
        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
        border: Border.all(color: AppColors.lightBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'GENERATED FILES',
            style: AppTextStyles.smallCapsLabel(
              fontSize: 8,
              color: AppColors.lightTextMuted,
            ),
          ),
          const SizedBox(height: 4),
          for (final file in visible)
            InkWell(
              onTap: file.isDir ? null : () => onTap(file.path),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Text(
                  file.isDir ? '${file.path}/' : file.path,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.mono(
                    fontSize: 10,
                    color: AppColors.lightTextSecondary,
                  ),
                ),
              ),
            ),
          if (extra > 0)
            Text(
              '+$extra more in sandbox',
              style: AppTextStyles.mono(fontSize: 10, color: AppColors.gold),
            ),
        ],
      ),
    );
  }
}
class _TemplateChip extends StatelessWidget {
  const _TemplateChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: AppColors.goldSubtle,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.gold.withValues(alpha: 0.35)),
      ),
      child: Text(
        label,
        style: AppTextStyles.mono(fontSize: 9, color: AppColors.goldDark),
      ),
    );
  }
}

/// The solution-scoped architect chat from the web MVP page: a stream of
/// `POST /opencode/chat` turns plus the suggested technical inquiries.
class _ArchitectChat extends ConsumerStatefulWidget {
  const _ArchitectChat({required this.solutionId, this.onBuildRequested});

  final String solutionId;
  final VoidCallback? onBuildRequested;

  @override
  ConsumerState<_ArchitectChat> createState() => _ArchitectChatState();
}

class _ArchitectChatState extends ConsumerState<_ArchitectChat> {
  static const _suggestedPrompts = [
    'Explain the system architecture and technicalities of this project.',
    'How does the customer menu, cart drawer & kitchen admin work?',
    'What database models, tables, and API endpoints are being created?',
    'Synthesize and prepare my custom solution build now.',
  ];

  final _input = TextEditingController();
  final _scroll = ScrollController();
  final _local = <ChatMessage>[];
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.md,
            AppSpacing.sm,
            AppSpacing.md,
            0,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'SUGGESTED TECHNICAL INQUIRIES',
                style: AppTextStyles.smallCapsLabel(
                  fontSize: 9,
                  color: AppColors.lightTextMuted,
                ),
              ),
              const SizedBox(height: 5),
              Wrap(
                spacing: 5,
                runSpacing: 5,
                children: [
                  for (final p in _suggestedPrompts)
                    GestureDetector(
                      onTap: _busy ? null : () => _send(p),
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 9,
                          vertical: 5,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.blackButton,
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(color: AppColors.lightBorder),
                        ),
                        child: Text(
                          p,
                          style: AppTextStyles.bodySmall(
                            fontSize: 10,
                            color: AppColors.lightTextSecondary,
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ],
          ),
        ),
        Expanded(
          child: Container(
            width: double.infinity,
            margin: const EdgeInsets.all(AppSpacing.md),
            padding: const EdgeInsets.all(AppSpacing.md),
            decoration: BoxDecoration(
              color: AppColors.darkBackground,
              borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
              border: Border.all(color: AppColors.lightBorder),
            ),
            child: _local.isEmpty && !_busy
                ? Center(
                    child: Text(
                      'Ask about the architecture, data model or APIs.',
                      textAlign: TextAlign.center,
                      style: AppTextStyles.mono(
                        fontSize: 11,
                        color: AppColors.darkTextSecondary,
                      ),
                    ),
                  )
                : ListView.builder(
                    controller: _scroll,
                    itemCount: _local.length + (_busy ? 1 : 0),
                    itemBuilder: (context, i) {
                      if (i >= _local.length) {
                        return Padding(
                          padding: const EdgeInsets.symmetric(vertical: 6),
                          child: Text(
                            'Architect is thinking...',
                            style: AppTextStyles.mono(
                              fontSize: 11,
                              color: AppColors.darkTextSecondary,
                            ),
                          ),
                        );
                      }
                      final m = _local[i];
                      return Padding(
                        padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              m.role == ChatRole.user ? 'YOU' : 'ARCHITECT',
                              style: AppTextStyles.smallCapsLabel(
                                fontSize: 8,
                                color: m.role == ChatRole.user
                                    ? AppColors.gold
                                    : AppColors.darkTextMuted,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              m.text,
                              style: AppTextStyles.mono(
                                fontSize: 11,
                                color: AppColors.darkTextPrimary,
                              ),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
          ),
        ),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
            child: Text(
              _error!,
              style: AppTextStyles.bodySmall(
                color: AppColors.statusErrorRed,
                fontSize: 11,
              ),
            ),
          ),
        if (_busy)
          const LinearProgressIndicator(minHeight: 2, color: AppColors.gold),
        Container(
          padding: const EdgeInsets.all(AppSpacing.sm),
          decoration: BoxDecoration(
            color: AppColors.lightSurface,
            border: Border(
              top: BorderSide(color: AppColors.lightBorder),
              bottom: BorderSide(
                color: AppColors.lightBorder,
                width: MediaQuery.of(context).padding.bottom,
              ),
            ),
          ),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _input,
                  enabled: !_busy,
                  minLines: 1,
                  maxLines: 3,
                  style: AppTextStyles.mono(fontSize: 12),
                  decoration: const InputDecoration(
                    hintText: 'Ask about this solution...',
                    isDense: true,
                  ),
                ),
              ),
              const SizedBox(width: AppSpacing.xs),
              VoiceInputButton(
                disabled: _busy,
                onTranscribed: (text, lang) {
                  final cur = _input.text.trim();
                  setState(() {
                    _input.text = cur.isEmpty ? text : '$cur\n$text';
                  });
                },
              ),
              const SizedBox(width: AppSpacing.xs),
              IconButton(
                onPressed: _busy ? null : () => _send(_input.text.trim()),
                icon: const Icon(Icons.send, size: 18),
                color: AppColors.gold,
              ),
            ],
          ),
        ),
      ],
    );
  }

  Future<void> _send(String text) async {
    final message = text.trim();
    if (message.isEmpty || _busy) return;
    _input.clear();
    setState(() {
      _busy = true;
      _error = null;
      _local.add(ChatMessage(role: ChatRole.user, text: message));
    });

    final assistant = StringBuffer();
    try {
      final client = ref.read(apiClientProvider);
      final turns = streamChatTurn(
        client,
        message: message,
        sessionId: 'architect-${widget.solutionId}',
        solutionId: widget.solutionId,
        buildRequested: message.toLowerCase().contains('build now'),
      );
      await for (final turn in turns) {
        if (!mounted) return;
        final text_ = turn.message;
        if (text_ != null && text_.isNotEmpty && turn.event == 'message') {
          assistant.write(text_);
          setState(() {
            _local.add(
              ChatMessage(role: ChatRole.assistant, text: text_),
            );
          });
        } else if (turn.event == 'error') {
          setState(() => _error = turn.message);
        }
      }
      final wasBuildRequest = message.toLowerCase().contains('build now');
      if (assistant.isEmpty && wasBuildRequest) {
        setState(() {
          _local.add(
            const ChatMessage(
              role: ChatRole.assistant,
              text: 'Synthesis kicked off. Track it in the BUILDS tab.',
            ),
          );
        });
        widget.onBuildRequested?.call();
      }
    } catch (e) {
      if (mounted) setState(() => _error = 'Chat failed: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }
}