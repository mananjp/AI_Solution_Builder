import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/widgets/sutra_button.dart';
import '../data/workspace_repository.dart';
import '../domain/workspace_models.dart';
import 'workspace_providers.dart';

/// `POST /mvp/builds/{id}/configure` — app name plus environment overrides.
///
/// Mirrors the web `ConfigureModal`: the env plan is fetched so required keys
/// are labelled as such and prefilled with whatever the build already knows.
Future<void> showConfigureBuildSheet(
  BuildContext context,
  WidgetRef ref,
  MVPBuildModel build,
) =>
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.lightSurface,
      shape: const RoundedRectangleBorder(
        borderRadius:
            BorderRadius.vertical(top: Radius.circular(AppSpacing.radiusLg)),
      ),
      builder: (_) => _ConfigureSheet(build: build),
    );

class _ConfigureSheet extends ConsumerStatefulWidget {
  const _ConfigureSheet({required this.build});

  final MVPBuildModel build;

  @override
  ConsumerState<_ConfigureSheet> createState() => _ConfigureSheetState();
}

class _ConfigureSheetState extends ConsumerState<_ConfigureSheet> {
  final _appName = TextEditingController();
  final _env = <String, TextEditingController>{};

  MVPEnvPlanModel? _plan;
  bool _loadingPlan = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _appName.dispose();
    for (final c in _env.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final plan =
          await ref.read(workspaceRepositoryProvider).fetchEnvPlan(
                widget.build.buildId,
              );
      if (!mounted) return;
      _appName.text = plan.appName ?? '';
      for (final v in plan.vars) {
        _env[v.name] = TextEditingController(text: v.effectiveValue);
      }
      setState(() {
        _plan = plan;
        _loadingPlan = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Could not read the env plan: $e';
        _loadingPlan = false;
      });
    }
  }

  Future<void> _save() async {
    setState(() {
      _saving = true;
      _error = null;
    });

    // Only send keys the user actually filled in, so a blank optional field does
    // not overwrite a value the build already resolved.
    final env = <String, dynamic>{};
    _env.forEach((key, controller) {
      final value = controller.text.trim();
      if (value.isNotEmpty) env[key] = value;
    });

    try {
      final applied = await ref.read(workspaceRepositoryProvider).configureBuild(
            widget.build.buildId,
            appName: _appName.text.trim(),
            env: env,
          );
      if (!mounted) return;
      ref.invalidate(mvpBuildsProvider);
      ref.invalidate(buildStatusProvider(widget.build.buildId));
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            applied.isEmpty
                ? 'Configuration saved.'
                : 'Configuration saved: ${applied.keys.join(', ')}',
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = 'Configure failed: $e';
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
              'CONFIGURE BUILD #${widget.build.buildNumber}',
              style: AppTextStyles.smallCapsLabel(
                fontSize: 11,
                color: AppColors.lightTextPrimary,
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            TextField(
              controller: _appName,
              style: AppTextStyles.mono(fontSize: 12),
              decoration: const InputDecoration(
                labelText: 'App name (optional)',
                hintText: 'my-production-app',
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            if (_loadingPlan)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(AppSpacing.sm),
                  child: CircularProgressIndicator(color: AppColors.gold),
                ),
              )
            else if (_plan != null && _plan!.vars.isEmpty)
              Text(
                'This build reads no environment variables.',
                style: AppTextStyles.bodySmall(
                  color: AppColors.lightTextSecondary,
                ),
              )
            else if (_plan != null) ...[
              Text(
                'ENVIRONMENT OVERRIDES',
                style: AppTextStyles.smallCapsLabel(
                  fontSize: 9,
                  color: AppColors.lightTextMuted,
                ),
              ),
              const SizedBox(height: AppSpacing.xs),
              for (final v in _plan!.vars)
                Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      TextField(
                        controller: _env[v.name],
                        style: AppTextStyles.mono(fontSize: 12),
                        decoration: InputDecoration(
                          labelText: v.required
                              ? '${v.name} (required)'
                              : v.name,
                          helperText: v.autoInjected
                              ? 'Auto-injected on deploy'
                              : v.description,
                          helperMaxLines: 2,
                        ),
                      ),
                    ],
                  ),
                ),
            ],
            if (_error != null) ...[
              const SizedBox(height: AppSpacing.sm),
              Text(
                _error!,
                style: AppTextStyles.bodySmall(
                  color: AppColors.statusErrorRed,
                ),
              ),
            ],
            const SizedBox(height: AppSpacing.md),
            SutraButton(
              label: _saving ? 'Saving...' : 'Save configuration',
              onPressed: _saving ? null : _save,
            ),
          ],
        ),
      ),
    );
  }
}

/// `POST /mvp/builds/{id}/deploy` + live `deploy/status` polling.
///
/// `repo_name` is mandatory and must match the backend's `^[A-Za-z0-9_.-]+$`
/// pattern, so the input is filtered rather than left to fail server-side.
Future<void> showDeployBuildSheet(
  BuildContext context,
  WidgetRef ref,
  MVPBuildModel build,
) =>
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.lightSurface,
      shape: const RoundedRectangleBorder(
        borderRadius:
            BorderRadius.vertical(top: Radius.circular(AppSpacing.radiusLg)),
      ),
      builder: (_) => _DeploySheet(build: build),
    );

class _DeploySheet extends ConsumerStatefulWidget {
  const _DeploySheet({required this.build});

  final MVPBuildModel build;

  @override
  ConsumerState<_DeploySheet> createState() => _DeploySheetState();
}

class _DeploySheetState extends ConsumerState<_DeploySheet> {
  late final TextEditingController _repoName;
  final _description = TextEditingController();
  final _env = <String, TextEditingController>{};

  MVPEnvPlanModel? _plan;
  MVPDeployStatusModel? _status;
  MVPDeployResultModel? _result;

  bool _isPrivate = false;
  bool _force = false;
  bool _busy = false;
  bool _polling = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    // Mirrors the web default of `mvp-<first 8 of build id>`.
    final short = widget.build.buildId.length >= 8
        ? widget.build.buildId.substring(0, 8)
        : widget.build.buildId;
    _repoName = TextEditingController(text: 'mvp-$short');
    _repoName.addListener(_sanitizeRepoName);
    _loadPlan();
    _loadStatus();
  }

  @override
  void dispose() {
    _repoName.dispose();
    _description.dispose();
    for (final c in _env.values) {
      c.dispose();
    }
    super.dispose();
  }

  /// The backend rejects anything outside `[A-Za-z0-9_.-]`, so drop it here
  /// instead of letting the deploy fail after a round trip.
  void _sanitizeRepoName() {
    final cleaned = _repoName.text.replaceAll(RegExp(r'[^A-Za-z0-9_.\-]'), '');
    if (cleaned != _repoName.text) {
      _repoName.value = TextEditingValue(
        text: cleaned,
        selection: TextSelection.collapsed(offset: cleaned.length),
      );
    }
  }

  Future<void> _loadPlan() async {
    try {
      final plan = await ref
          .read(workspaceRepositoryProvider)
          .fetchEnvPlan(widget.build.buildId);
      if (!mounted) return;
      for (final v in plan.vars) {
        _env[v.name] = TextEditingController(text: v.effectiveValue);
      }
      setState(() => _plan = plan);
    } catch (_) {
      // Deploy still works without a plan; the env block just stays hidden.
    }
  }

  Future<void> _loadStatus() async {
    try {
      final status = await ref
          .read(workspaceRepositoryProvider)
          .fetchDeployStatus(widget.build.buildId);
      if (!mounted) return;
      setState(() {
        _status = status;
        // A queued/building deploy is worth following until it settles.
        _polling = status.isInFlight;
      });
      if (status.isInFlight) {
        Future.delayed(const Duration(seconds: 5), () {
          if (mounted && _polling) _loadStatus();
        });
      }
    } catch (_) {
      // Never been deployed; leave the panel empty rather than faking a state.
    }
  }

  Future<void> _deploy() async {
    final repoName = _repoName.text.trim();
    if (repoName.isEmpty) {
      setState(() => _error = 'A repository name is required.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });

    final env = <String, dynamic>{};
    _env.forEach((key, controller) {
      final value = controller.text.trim();
      if (value.isNotEmpty) env[key] = value;
    });

    try {
      final result = await ref.read(workspaceRepositoryProvider).deployBuild(
            widget.build.buildId,
            repoName: repoName,
            description: _description.text.trim(),
            isPrivate: _isPrivate,
            force: _force,
            env: env,
          );
      if (!mounted) return;
      setState(() {
        _result = result;
        _busy = false;
        _polling = true;
      });
      ref.invalidate(mvpBuildsProvider);
      _loadStatus();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = 'Deploy failed: $e';
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
              'DEPLOY BUILD #${widget.build.buildNumber}',
              style: AppTextStyles.smallCapsLabel(
                fontSize: 11,
                color: AppColors.lightTextPrimary,
              ),
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              'Pushes the archive to a new GitHub repo using your saved GitHub '
              'token, with a Render blueprint for auto-deploy.',
              style: AppTextStyles.bodySmall(
                color: AppColors.lightTextSecondary,
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            TextField(
              controller: _repoName,
              style: AppTextStyles.mono(fontSize: 12),
              decoration: const InputDecoration(
                labelText: 'Repository name',
                helperText: 'Letters, numbers, dot, dash and underscore',
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            TextField(
              controller: _description,
              style: AppTextStyles.mono(fontSize: 12),
              decoration: const InputDecoration(
                labelText: 'Description (optional)',
                hintText: 'Auto-generated MVP by AI Solution Builder',
              ),
            ),
            SwitchListTile(
              value: _isPrivate,
              onChanged: (v) => setState(() => _isPrivate = v),
              title: Text(
                'Private repository',
                style: AppTextStyles.bodySmall(
                  color: AppColors.lightTextPrimary,
                ),
              ),
              contentPadding: EdgeInsets.zero,
              dense: true,
            ),
            SwitchListTile(
              value: _force,
              onChanged: (v) => setState(() => _force = v),
              title: Text(
                'Force push (overwrite an existing repo)',
                style: AppTextStyles.bodySmall(
                  color: AppColors.lightTextPrimary,
                ),
              ),
              contentPadding: EdgeInsets.zero,
              dense: true,
            ),
            if (_plan != null && _plan!.vars.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.sm),
              if (_plan!.hasRequired) ...[
                _EnvRequiredWarning(plan: _plan!),
                const SizedBox(height: AppSpacing.sm),
              ],
              Text(
                'ENVIRONMENT',
                style: AppTextStyles.smallCapsLabel(
                  fontSize: 9,
                  color: AppColors.lightTextMuted,
                ),
              ),
              for (final v in _plan!.vars)
                Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                  child: TextField(
                    controller: _env[v.name],
                    style: AppTextStyles.mono(fontSize: 12),
                    decoration: InputDecoration(
                      labelText:
                          v.required ? '${v.name} (required)' : v.name,
                      helperText: v.autoInjected ? 'Auto-injected' : null,
                      helperStyle: AppTextStyles.mono(
                        fontSize: 10,
                        color: v.required && v.autoInjected
                            ? AppColors.statusLiveGreen
                            : AppColors.lightTextMuted,
                      ),
                    ),
                  ),
                ),
            ],
            if (_status != null) ...[
              const SizedBox(height: AppSpacing.sm),
              _DeployStatusPanel(status: _status!),
            ],
            if (_result != null) ...[
              const SizedBox(height: AppSpacing.sm),
              _DeployResultPanel(result: _result!),
            ],
            if (_error != null) ...[
              const SizedBox(height: AppSpacing.sm),
              Text(
                _error!,
                style: AppTextStyles.bodySmall(
                  color: AppColors.statusErrorRed,
                ),
              ),
            ],
            const SizedBox(height: AppSpacing.md),
            SutraButton(
              label: _busy ? 'Deploying...' : 'Deploy',
              onPressed: _busy ? null : _deploy,
            ),
          ],
        ),
      ),
    );
  }
}

class _DeployStatusPanel extends StatelessWidget {
  const _DeployStatusPanel({required this.status});

  final MVPDeployStatusModel status;

  @override
  Widget build(BuildContext context) {
    final color = status.isLive
        ? AppColors.statusLiveGreen
        : status.overall == 'failed'
            ? AppColors.statusErrorRed
            : AppColors.gold;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'DEPLOY STATUS: ${status.overall.toUpperCase()}',
          style: AppTextStyles.smallCapsLabel(fontSize: 9, color: color),
        ),
        if (status.frontendUrl != null) _LinkRow(label: 'App', url: status.frontendUrl!),
        if (status.backendUrl != null)
          _LinkRow(label: 'API', url: status.backendUrl!),
        if (status.repoUrl != null)
          _LinkRow(label: 'Repo', url: status.repoUrl!),
        if (status.services.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.sm),
          Text(
            'SERVICES',
            style: AppTextStyles.smallCapsLabel(
              fontSize: 9,
              color: AppColors.lightTextMuted,
            ),
          ),
          for (final svc in status.services) _ServiceRow(service: svc),
        ],
      ],
    );
  }
}

/// One provisioned Render service, with its own status, error and links.
class _ServiceRow extends StatelessWidget {
  const _ServiceRow({required this.service});

  final MVPDeployServiceModel service;

  @override
  Widget build(BuildContext context) {
    final color = service.isFailed
        ? AppColors.statusErrorRed
        : service.isLive
            ? AppColors.statusLiveGreen
            : AppColors.gold;
    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.xs),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  color: color,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  service.name,
                  style: AppTextStyles.bodySmall(
                    color: AppColors.lightTextPrimary,
                    fontSize: 12,
                  ),
                ),
              ),
              Text(
                service.status.toUpperCase(),
                style: AppTextStyles.mono(fontSize: 9, color: color),
              ),
            ],
          ),
          if (service.error != null)
            Padding(
              padding: const EdgeInsets.only(left: 12, top: 2),
              child: Text(
                service.error!,
                style: AppTextStyles.mono(
                  fontSize: 9,
                  color: AppColors.statusErrorRed,
                ),
              ),
            ),
          if (service.url != null)
            Padding(
              padding: const EdgeInsets.only(left: 12, top: 2),
              child: _LinkRow(label: 'Visit', url: service.url!),
            ),
          if (service.dashboardUrl != null)
            Padding(
              padding: const EdgeInsets.only(left: 12, top: 2),
              child: _LinkRow(label: 'Render', url: service.dashboardUrl!),
            ),
        ],
      ),
    );
  }
}

/// Required env vars the agent cannot fill on its own. Deploy still works, but
/// the service will come up short, so say so before the user hits Deploy.
class _EnvRequiredWarning extends StatelessWidget {
  const _EnvRequiredWarning({required this.plan});

  final MVPEnvPlanModel plan;

  @override
  Widget build(BuildContext context) {
    final missing = plan.vars
        .where((v) => v.required && !v.autoInjected)
        .map((v) => v.name)
        .toList();
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: AppColors.statusWarningAmber.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
        border: Border.all(
          color: AppColors.statusWarningAmber.withValues(alpha: 0.3),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.warning_amber_rounded,
            size: 14,
            color: AppColors.statusWarningAmber,
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  missing.isEmpty
                      ? 'Required variables still need values'
                      : 'Missing required: ${missing.join(', ')}',
                  style: AppTextStyles.bodySmall(
                    color: AppColors.statusWarningAmber,
                    fontSize: 11,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  'Auto-injected values are already wired by the agent.',
                  style: AppTextStyles.mono(
                    fontSize: 9,
                    color: AppColors.lightTextMuted,
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

class _DeployResultPanel extends StatelessWidget {
  const _DeployResultPanel({required this.result});

  final MVPDeployResultModel result;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'PUSHED ${result.fileCount} FILES',
          style: AppTextStyles.smallCapsLabel(
            fontSize: 9,
            color: AppColors.lightTextMuted,
          ),
        ),
        _LinkRow(label: 'Repo', url: result.repoUrl),
        if (result.frontendUrl != null)
          _LinkRow(label: 'App', url: result.frontendUrl!),
        if (result.renderDeployStatus != null)
          Text(
            'Render: ${result.renderDeployStatus}',
            style: AppTextStyles.mono(
              fontSize: 10,
              color: AppColors.lightTextSecondary,
            ),
          ),
      ],
    );
  }
}

class _LinkRow extends StatelessWidget {
  const _LinkRow({required this.label, required this.url});

  final String label;
  final String url;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        SizedBox(
          width: 42,
          child: Text(
            label,
            style: AppTextStyles.smallCapsLabel(
              fontSize: 9,
              color: AppColors.lightTextMuted,
            ),
          ),
        ),
        Expanded(
          child: Text(
            url,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: AppTextStyles.mono(
              fontSize: 10,
              color: AppColors.lightTextSecondary,
            ),
          ),
        ),
        IconButton(
          tooltip: 'Copy',
          iconSize: 14,
          padding: EdgeInsets.zero,
          constraints: const BoxConstraints(),
          onPressed: () async {
            await Clipboard.setData(ClipboardData(text: url));
            if (context.mounted) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('$label URL copied.')),
              );
            }
          },
          icon: const Icon(
            Icons.copy,
            size: 14,
            color: AppColors.lightTextSecondary,
          ),
        ),
      ],
    );
  }
}
