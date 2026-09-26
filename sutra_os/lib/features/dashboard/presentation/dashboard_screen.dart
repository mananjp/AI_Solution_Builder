import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/widgets/prompt_dialog.dart';
import '../../../core/widgets/stat_card.dart';
import '../../../core/widgets/status_chip.dart';
import '../../../core/widgets/sutra_button.dart';
import '../../../core/widgets/sutra_card.dart';
import '../../billing/data/billing_repository.dart';
import '../../engine/domain/engine_models.dart';
import '../../engine/presentation/engine_providers.dart';
import '../../workspace/data/workspace_repository.dart';
import '../../workspace/domain/workspace_models.dart';
import '../../workspace/presentation/workspace_providers.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  void _showNewBlueprintDialog(BuildContext context, WidgetRef ref) {
    final titleController = TextEditingController();
    final descController = TextEditingController();
    bool isCreating = false;

    showDialog(
      context: context,
      builder: (dialogCtx) => StatefulBuilder(
        builder: (context, setDialogState) {
          return AlertDialog(
            backgroundColor: AppColors.lightSurface,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
              side: const BorderSide(color: AppColors.lightBorder),
            ),
            title: Text(
              'Initialize Architecture Blueprint',
              style: AppTextStyles.serifHeading(fontSize: 20),
            ),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Specify product scope for the multi-agent reasoning swarm.',
                    style: AppTextStyles.bodySmall(color: AppColors.lightTextSecondary),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  TextField(
                    controller: titleController,
                    style: AppTextStyles.bodyMedium(color: AppColors.lightTextPrimary),
                    decoration: const InputDecoration(
                      labelText: 'Solution Title',
                      hintText: 'e.g. Distributed Payment Gateway',
                    ),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  TextField(
                    controller: descController,
                    maxLines: 3,
                    style: AppTextStyles.bodyMedium(color: AppColors.lightTextPrimary),
                    decoration: const InputDecoration(
                      labelText: 'Intent / Architecture Spec',
                      hintText: 'Entities, events, API protocols, and cloud scaling requirements.',
                    ),
                  ),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogCtx),
                child: Text(
                  'CANCEL',
                  style: AppTextStyles.smallCapsLabel(color: AppColors.lightTextSecondary),
                ),
              ),
              SutraButton(
                label: isCreating ? 'DISPATCHING...' : 'DISPATCH AGENTS',
                height: 38,
                variant: SutraButtonVariant.primaryBlack,
                isLoading: isCreating,
                onPressed: isCreating
                    ? null
                    : () async {
                        final title = titleController.text.trim();
                        if (title.isEmpty) return;
                        setDialogState(() => isCreating = true);
                        try {
                          final repo = ref.read(workspaceRepositoryProvider);
                          final wsId = ref.read(activeWorkspaceIdProvider) ?? '';
                          final solution = await repo.createSolution(
                            workspaceId: wsId,
                            title: title,
                            description: descController.text.trim(),
                          );
                          ref.read(activeSolutionIdProvider.notifier).set(solution.id);
                          ref.read(activeWorkspaceIdProvider.notifier).set(solution.workspaceId);
                          if (dialogCtx.mounted) {
                            Navigator.pop(dialogCtx);
                            // The new solution has to appear in both the
                            // workspace counters and its own list.
                            invalidateWorkspaceScoped(ref, solution.workspaceId);
                            context.go('/workspace');
                          }
                        } catch (e) {
                          if (!dialogCtx.mounted) return;
                          setDialogState(() => isCreating = false);
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text('Could not create blueprint: $e'),
                              backgroundColor: AppColors.statusErrorRed,
                            ),
                          );
                        }
                      },
              ),
            ],
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final workspacesAsync = ref.watch(workspacesListProvider);
    final usageAsync = ref.watch(billingUsageProvider);
    // These three were previously unused: the dashboard showed a hardcoded
    // '● LIVE' engine, a hardcoded '1 Active' swarm count, and a hardcoded
    // "recent syntheses" list. All of it is now driven by the API.
    final engineHealthAsync = ref.watch(engineHealthProvider);
    final solutionsAsync = ref.watch(activeSolutionsProvider);
    final templatesAsync = ref.watch(mvpTemplatesProvider);

    return Scaffold(
      backgroundColor: AppColors.lightBackground,
      body: SafeArea(
        child: RefreshIndicator(
          color: AppColors.blackButton,
          onRefresh: () async {
            ref.invalidate(workspacesListProvider);
            ref.invalidate(mvpTemplatesProvider);
            ref.invalidate(billingUsageProvider);
          },
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(
              parent: BouncingScrollPhysics(),
            ),
            slivers: [
              // Top Bar Breadcrumbs & Status
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
                              'WORKSPACE • PRIMARY WORKSPACE',
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
                              'Overview',
                              style: AppTextStyles.serifHeading(
                                fontSize: 24,
                                color: AppColors.lightTextPrimary,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      const StatusChip(
                        label: 'SYNAPSE MESH',
                        statusText: 'LIVE',
                      ),
                    ],
                  ),
                ),
              ),

              // Quick Action Ribbon / Carousel
              SliverToBoxAdapter(
                child: SizedBox(
                  height: 40,
                  child: ListView(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                    children: [
                      _buildQuickActionPill(
                        context: context,
                        icon: Icons.add,
                        label: '+ New Blueprint',
                        isPrimary: true,
                        onTap: () => _showNewBlueprintDialog(context, ref),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      _buildQuickActionPill(
                        context: context,
                        icon: Icons.upload_file_outlined,
                        label: 'Upload Spec',
                        onTap: () => context.go('/workspace'),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      _buildQuickActionPill(
                        context: context,
                        icon: Icons.rocket_launch_outlined,
                        label: 'Deploy Cloud',
                        onTap: () => context.go('/settings'),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      _buildQuickActionPill(
                        context: context,
                        icon: Icons.bolt,
                        label: 'Recharge Credits',
                        onTap: () => context.go('/billing'),
                      ),
                    ],
                  ),
                ),
              ),

              const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.lg)),

              // 2x2 Telemetry Metric Cards Grid
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                  child: workspacesAsync.when(
                    data: (workspaces) {
                      final totalSolutions = workspaces.fold<int>(
                        0,
                        (sum, w) => sum + w.solutionCount,
                      );
                      final creditsRemaining = usageAsync.maybeWhen(
                        data: (usage) => usage.isUnlimited
                            ? 'Unlimited'
                            : usage.creditsRemaining.toString(),
                        orElse: () => '--',
                      );
                      // Real engine reading, polled every 15s. Previously this
                      // was the literal string '● LIVE', so the card reported
                      // a healthy engine even when the backend was down.
                      final engineValue = engineHealthAsync.maybeWhen(
                        data: (health) => health.isOnline ? '● LIVE' : '○ DOWN',
                        orElse: () => '--',
                      );
                      final engineColor = engineHealthAsync.maybeWhen(
                        data: (health) => health.isOnline
                            ? AppColors.statusLiveGreen
                            : AppColors.statusErrorRed,
                        orElse: () => AppColors.lightTextMuted,
                      );
                      // Derived from the solutions actually on the server
                      // rather than the hardcoded '1 Active'.
                      final activeSwarms = solutionsAsync.maybeWhen(
                        data: (solutions) => solutions
                            .where((s) => _isInFlight(s))
                            .length
                            .toString(),
                        orElse: () => '--',
                      );

                      return LayoutBuilder(
                        builder: (context, constraints) {
                          final isNarrow = constraints.maxWidth < 600;
                          return GridView.count(
                            shrinkWrap: true,
                            physics: const NeverScrollableScrollPhysics(),
                            crossAxisCount: isNarrow ? 2 : 4,
                            crossAxisSpacing: AppSpacing.sm,
                            mainAxisSpacing: AppSpacing.sm,
                            childAspectRatio: isNarrow ? 1.25 : 1.6,
                            children: [
                              StatCard(
                                label: 'Engine Mesh',
                                value: engineValue,
                                icon: Icons.memory,
                                iconColor: engineColor,
                              ),
                              StatCard(
                                label: 'Compute Credits',
                                value: creditsRemaining,
                                icon: Icons.bolt,
                                iconColor: AppColors.gold,
                              ),
                              StatCard(
                                label: 'Total Solutions',
                                value: totalSolutions.toString(),
                                icon: Icons.layers_outlined,
                                iconColor: AppColors.lightTextPrimary,
                              ),
                              StatCard(
                                label: 'Active Swarms',
                                value: activeSwarms,
                                icon: Icons.hub_outlined,
                                iconColor: AppColors.goldDark,
                              ),
                            ],
                          );
                        },
                      );
                    },
                    loading: () => const Center(
                      child: CircularProgressIndicator(color: AppColors.blackButton),
                    ),
                    // A failed request must not render a green "Online" card.
                    error: (_, __) => SutraCard(
                      padding: const EdgeInsets.all(AppSpacing.md),
                      child: Row(
                        children: [
                          const Icon(Icons.cloud_off_outlined,
                              color: AppColors.statusErrorRed, size: 18),
                          const SizedBox(width: AppSpacing.sm),
                          Expanded(
                            child: Text(
                              'Workspace data unavailable. Pull down to retry.',
                              style: AppTextStyles.bodySmall(
                                color: AppColors.lightTextSecondary,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
              // Live Runtime Resources & Sidecar self-check
              const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.md)),
              const SliverToBoxAdapter(child: _LiveRuntimeResourcesCard()),
              const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.sm)),
              const SliverToBoxAdapter(child: _EngineDiagnosisPanel()),

              const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.xl)),

              // Autonomous Swarm Architect Card (Hero Card)
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                  child: SutraCard(
                    padding: const EdgeInsets.all(AppSpacing.md),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Flexible(
                              child: FittedBox(
                                fit: BoxFit.scaleDown,
                                alignment: Alignment.centerLeft,
                                child: Text(
                                  'AUTONOMOUS SWARM ARCHITECT',
                                  style: AppTextStyles.smallCapsLabel(
                                    fontSize: 10,
                                    color: AppColors.goldDark,
                                    letterSpacing: 1.8,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ),
                            ),
                            const SizedBox(width: AppSpacing.xs),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: AppColors.goldSubtle,
                                borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                              ),
                              child: Text(
                                'DETERMINISTIC',
                                style: AppTextStyles.smallCapsLabel(
                                  fontSize: 8,
                                  color: AppColors.goldDark,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: AppSpacing.sm),
                        Text(
                          'Dissect business scope into production cloud infrastructure.',
                          style: AppTextStyles.serifHeading(
                            fontSize: 18,
                            color: AppColors.lightTextPrimary,
                          ),
                        ),
                        const SizedBox(height: AppSpacing.xs),
                        Text(
                          'Sutra orchestrates multi-agent negotiations to compile verified relational models, state machines, and OpenAPI 3.1 microservices.',
                          style: AppTextStyles.bodyMedium(
                            color: AppColors.lightTextSecondary,
                          ),
                        ),
                        const SizedBox(height: AppSpacing.md),

                        // Visual Pipeline Steps Tracker (responsive)
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: AppSpacing.sm,
                            vertical: AppSpacing.md,
                          ),
                          decoration: BoxDecoration(
                            color: AppColors.lightSurfaceSubtle,
                            borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                            border: Border.all(color: AppColors.lightBorder),
                          ),
                          child: Row(
                            children: [
                              Expanded(child: _buildPipelineStep('01', 'Domain Model')),
                              const Padding(
                                padding: EdgeInsets.symmetric(horizontal: 2),
                                child: Icon(Icons.arrow_forward, size: 12, color: AppColors.lightBorder),
                              ),
                              Expanded(child: _buildPipelineStep('02', 'Protocol Mesh')),
                              const Padding(
                                padding: EdgeInsets.symmetric(horizontal: 2),
                                child: Icon(Icons.arrow_forward, size: 12, color: AppColors.lightBorder),
                              ),
                              Expanded(child: _buildPipelineStep('03', 'Synthesis')),
                            ],
                          ),
                        ),

                        const SizedBox(height: AppSpacing.lg),

                        // Full-width polished obsidian CTA button
                        SutraButton(
                          label: 'Initialize Architecture Blueprint →',
                          height: 48,
                          width: double.infinity,
                          variant: SutraButtonVariant.primaryBlack,
                          onPressed: () => _showNewBlueprintDialog(context, ref),
                        ),
                      ],
                    ),
                  ),
                ),
              ),

              const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.xl)),

              // Curated Starter Blueprints (Starter Templates)
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
                              'CURATED BLUEPRINTS',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: AppTextStyles.smallCapsLabel(
                                fontSize: 10,
                                color: AppColors.gold,
                                letterSpacing: 1.5,
                              ),
                            ),
                          ),
                          const SizedBox(width: AppSpacing.sm),
                          GestureDetector(
                            onTap: () => context.go('/workspace'),
                            child: Text(
                              'OPEN WORKSPACE →',
                              style: AppTextStyles.smallCapsLabel(
                                fontSize: 9,
                                color: AppColors.lightTextPrimary,
                                letterSpacing: 0.8,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        'Production Topologies',
                        style: AppTextStyles.serifHeading(
                          fontSize: 18,
                          color: AppColors.lightTextPrimary,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.sm),
                    ],
                  ),
                ),
              ),

              // Starter Templates — now sourced from GET /api/v1/mvp/templates.
              // These three cards used to be hardcoded literals while the real
              // template provider sat unwatched.
              SliverToBoxAdapter(
                child: SizedBox(
                  height: 175,
                  child: templatesAsync.when(
                    loading: () => const Center(
                      child: CircularProgressIndicator(color: AppColors.blackButton),
                    ),
                    error: (_, __) => Padding(
                      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                      child: Text(
                        'Templates unavailable right now.',
                        style: AppTextStyles.bodySmall(
                          color: AppColors.lightTextSecondary,
                        ),
                      ),
                    ),
                    data: (templates) {
                      if (templates.isEmpty) {
                        return Padding(
                          padding:
                              const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                          child: Text(
                            'No starter templates published yet.',
                            style: AppTextStyles.bodySmall(
                              color: AppColors.lightTextSecondary,
                            ),
                          ),
                        );
                      }
                      return ListView.separated(
                        scrollDirection: Axis.horizontal,
                        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                        itemCount: templates.length,
                        separatorBuilder: (_, __) =>
                            const SizedBox(width: AppSpacing.md),
                        itemBuilder: (context, index) {
                          final template = templates[index];
                          return _buildTemplateCard(
                            title: template.title,
                            stack: template.industry.isEmpty
                                ? 'Full-Stack Scaffold'
                                : template.industry,
                            description: template.description,
                            onTap: () => _quickBuildFromTemplate(
                              context,
                              ref,
                              template.slug,
                              template.appName.isEmpty
                                  ? template.title
                                  : template.appName,
                            ),
                          );
                        },
                      );
                    },
                  ),
                ),
              ),

              const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.xl)),

              // Recent Syntheses & Blueprints
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'LIFECYCLE TRACKER',
                        style: AppTextStyles.smallCapsLabel(
                          fontSize: 10,
                          color: AppColors.gold,
                          letterSpacing: 2.0,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        'Recent Syntheses',
                        style: AppTextStyles.serifHeading(
                          fontSize: 18,
                          color: AppColors.lightTextPrimary,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.md),
                      // Real solutions from the server. This was three
                      // hardcoded rows ("Autonomous Payment Router",
                      // "Omni-Channel Agent Swarm", "Identity & Access Mesh")
                      // that appeared for every user regardless of their data
                      // and all navigated to the same screen.
                      solutionsAsync.when(
                        loading: () => const Center(
                          child: Padding(
                            padding: EdgeInsets.all(AppSpacing.md),
                            child: CircularProgressIndicator(
                              color: AppColors.blackButton,
                            ),
                          ),
                        ),
                        error: (_, __) => Text(
                          'Blueprints unavailable. Pull down to retry.',
                          style: AppTextStyles.bodySmall(
                            color: AppColors.statusErrorRed,
                          ),
                        ),
                        data: (solutions) {
                          if (solutions.isEmpty) {
                            return Text(
                              'No blueprints yet. Use "New Blueprint" to start one.',
                              style: AppTextStyles.bodySmall(
                                color: AppColors.lightTextSecondary,
                              ),
                            );
                          }
                          // Newest first. `createdAtUtc` is null when the server
                          // omits a timestamp, so those sort last.
                          final recent = [...solutions]
                            ..sort((a, b) {
                              final at = a.createdAtUtc;
                              final bt = b.createdAtUtc;
                              if (at == null && bt == null) return 0;
                              if (at == null) return 1;
                              if (bt == null) return -1;
                              return bt.compareTo(at);
                            });
                          return Column(
                            children: [
                              for (var i = 0;
                                  i < recent.length && i < 5;
                                  i++) ...[
                                if (i > 0)
                                  const SizedBox(height: AppSpacing.xs),
                                _buildSolutionRow(context, ref, recent[i]),
                              ],
                            ],
                          );
                        },
                      ),
                    ],
                  ),
                ),
              ),

              const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.xxl)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildQuickActionPill({
    required BuildContext context,
    required IconData icon,
    required String label,
    required VoidCallback onTap,
    bool isPrimary = false,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: isPrimary ? AppColors.blackButton : AppColors.lightSurface,
          borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
          border: Border.all(
            color: isPrimary ? AppColors.blackButton : AppColors.lightBorder,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 14,
              color: isPrimary ? Colors.white : AppColors.lightTextPrimary,
            ),
            const SizedBox(width: 6),
            Text(
              label,
              style: AppTextStyles.smallCapsLabel(
                fontSize: 10,
                color: isPrimary ? Colors.white : AppColors.lightTextPrimary,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPipelineStep(String stepNumber, String title) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 18,
          height: 18,
          decoration: BoxDecoration(
            color: AppColors.blackButton,
            borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
          ),
          alignment: Alignment.center,
          child: Text(
            stepNumber,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 8,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
        const SizedBox(width: 4),
        Flexible(
          child: FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(
              title,
              style: AppTextStyles.smallCapsLabel(
                fontSize: 9,
                color: AppColors.lightTextPrimary,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildTemplateCard({
    required String title,
    required String stack,
    required String description,
    required VoidCallback onTap,
  }) {
    return Container(
      width: 250,
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.lightSurface,
        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
        border: Border.all(color: AppColors.lightBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            stack.toUpperCase(),
            style: AppTextStyles.smallCapsLabel(
              fontSize: 8,
              color: AppColors.goldDark,
              letterSpacing: 1.0,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            title,
            style: AppTextStyles.serifHeading(
              fontSize: 16,
              color: AppColors.lightTextPrimary,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            description,
            style: AppTextStyles.bodySmall(
              color: AppColors.lightTextSecondary,
              fontSize: 11,
            ),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          const Spacer(),
          SutraButton(
            label: '🚀 Build App',
            height: 32,
            width: double.infinity,
            variant: SutraButtonVariant.primaryBlack,
            onPressed: onTap,
          ),
        ],
      ),
    );
  }

  /// A real row for one solution on the server. Selecting it makes the solution
  /// active and opens the workspace, which is the only way the user can reach
  /// work that already exists.
  Widget _buildSolutionRow(
    BuildContext context,
    WidgetRef ref,
    SolutionModel solution,
  ) {
    final inFlight = solution.isInFlight;
    return GestureDetector(
      onTap: () {
        ref.read(activeSolutionIdProvider.notifier).set(solution.id);
        context.go('/workspace');
      },
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
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: AppColors.goldSubtle,
                borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
              ),
              child: const Icon(Icons.architecture, color: AppColors.gold, size: 18),
            ),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    solution.title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.bodyMedium(
                      color: AppColors.lightTextPrimary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  Text(
                    solution.createdAtUtc == null
                        ? 'No date'
                        : _relativeTime(solution.createdAtUtc!),
                    style: AppTextStyles.bodySmall(
                      color: AppColors.lightTextSecondary,
                      fontSize: 11,
                    ),
                  ),
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
              decoration: BoxDecoration(
                color: inFlight ? AppColors.goldSubtle : AppColors.lightSurfaceSubtle,
                borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
              ),
              child: Text(
                solution.statusLabel,
                style: AppTextStyles.smallCapsLabel(
                  fontSize: 8,
                  color: inFlight
                      ? AppColors.goldDark
                      : AppColors.lightTextSecondary,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  bool _isInFlight(SolutionModel solution) => solution.isInFlight;

  static String _relativeTime(DateTime then) {
    final delta = DateTime.now().difference(then);
    if (delta.isNegative || delta.inMinutes < 1) return 'just now';
    if (delta.inMinutes < 60) return '${delta.inMinutes}m ago';
    if (delta.inHours < 24) return '${delta.inHours}h ago';
    if (delta.inDays < 30) return '${delta.inDays}d ago';
    return '${(delta.inDays / 30).floor()}mo ago';
  }

  /// `POST /mvp/quick-build` with `{template, app_name}`, matching the web app.
  Future<void> _quickBuildFromTemplate(
    BuildContext context,
    WidgetRef ref,
    String slug,
    String fallbackName,
  ) async {
    if (slug.isEmpty) {
      _toast(context, 'That template has no identifier.', isError: true);
      return;
    }

    final appName = await showPromptDialog(
      context: context,
      title: 'Quick Build',
      initialValue: fallbackName,
      labelText: 'App name',
      confirmLabel: 'DISPATCH',
      cancelLabel: 'CANCEL',
    );

    if (appName == null || appName.isEmpty) return;
    if (!context.mounted) return;

    try {
      final build = await ref.read(workspaceRepositoryProvider).quickBuildMvp(
            template: slug,
            appName: appName,
          );
      // A quick build creates a new solution, so both the solution list and
      // the workspace counts are now stale.
      ref.invalidate(activeSolutionsProvider);
      invalidateWorkspaceScoped(ref, ref.read(activeWorkspaceIdProvider));
      if (build.solutionId.isNotEmpty) {
        ref.read(activeSolutionIdProvider.notifier).set(build.solutionId);
      }
      if (!context.mounted) return;
      _toast(context, 'Quick build dispatched for "$appName".');
    } catch (e) {
      if (!context.mounted) return;
      _toast(context, 'Quick build failed: $e', isError: true);
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



class _LiveRuntimeResourcesCard extends ConsumerWidget {
  const _LiveRuntimeResourcesCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final resourcesAsync = ref.watch(systemResourcesProvider);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
      child: SutraCard(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.speed, size: 14, color: AppColors.gold),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    'LIVE RUNTIME RESOURCES',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppTextStyles.smallCapsLabel(
                      fontSize: 10,
                      color: AppColors.goldDark,
                      letterSpacing: 1.4,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.xs),
                Text(
                  'CPU • RAM • DISK',
                  style: AppTextStyles.mono(
                    fontSize: 9,
                    color: AppColors.lightTextMuted,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            resourcesAsync.when(
              loading: () => const LinearProgressIndicator(
                minHeight: 2,
                color: AppColors.gold,
                backgroundColor: AppColors.lightSurfaceSubtle,
              ),
              error: (err, _) => Text(
                'Resource metrics unavailable: $err',
                style: AppTextStyles.bodySmall(color: AppColors.lightTextMuted),
              ),
              data: (r) {
                final cpu = r.cpuPercent ?? 0.0;
                final ram = r.memoryPercent ?? 0.0;
                final disk = r.diskPercent ?? 0.0;

                return Column(
                  children: [
                    _ResourceBar(
                      icon: Icons.memory,
                      label: 'CPU',
                      value: '${cpu.toStringAsFixed(0)}%',
                      percent: cpu / 100.0,
                      subtitle: r.cpuCount != null ? '${r.cpuCount} cores' : null,
                      color: cpu > 85
                          ? AppColors.statusErrorRed
                          : (cpu > 70 ? AppColors.statusWarningAmber : AppColors.statusLiveGreen),
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    _ResourceBar(
                      icon: Icons.developer_board,
                      label: 'RAM',
                      value: '${ram.toStringAsFixed(0)}%',
                      percent: ram / 100.0,
                      subtitle: r.memoryUsedMb != null && r.memoryTotalMb != null
                          ? '${(r.memoryUsedMb! / 1024).toStringAsFixed(1)} / ${(r.memoryTotalMb! / 1024).toStringAsFixed(1)} GB'
                          : null,
                      color: ram > 85
                          ? AppColors.statusErrorRed
                          : (ram > 70 ? AppColors.statusWarningAmber : AppColors.statusLiveGreen),
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    _ResourceBar(
                      icon: Icons.storage_outlined,
                      label: 'DISK',
                      value: '${disk.toStringAsFixed(0)}%',
                      percent: disk / 100.0,
                      subtitle: r.diskFreeBytes != null && r.diskTotalBytes != null
                          ? '${(r.diskFreeBytes! / 1073741824).toStringAsFixed(1)} GB free'
                          : null,
                      color: disk > 90
                          ? AppColors.statusErrorRed
                          : (disk > 75 ? AppColors.statusWarningAmber : AppColors.goldDark),
                    ),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _ResourceBar extends StatelessWidget {
  const _ResourceBar({
    required this.icon,
    required this.label,
    required this.value,
    required this.percent,
    required this.color,
    this.subtitle,
  });

  final IconData icon;
  final String label;
  final String value;
  final double percent;
  final Color color;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    final clamped = percent.clamp(0.0, 1.0);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(icon, size: 12, color: AppColors.lightTextSecondary),
            const SizedBox(width: 4),
            Text(
              label,
              style: AppTextStyles.smallCapsLabel(
                fontSize: 9,
                color: AppColors.lightTextSecondary,
                fontWeight: FontWeight.w600,
              ),
            ),
            if (subtitle != null) ...[
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  '($subtitle)',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.mono(
                    fontSize: 8,
                    color: AppColors.lightTextMuted,
                  ),
                ),
              ),
            ] else
              const Spacer(),
            const SizedBox(width: 4),
            Text(
              value,
              style: AppTextStyles.mono(
                fontSize: 10,
                color: AppColors.lightTextPrimary,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
        const SizedBox(height: 3),
        ClipRRect(
          borderRadius: BorderRadius.circular(2),
          child: LinearProgressIndicator(
            value: clamped,
            minHeight: 4,
            color: color,
            backgroundColor: AppColors.lightSurfaceSubtle,
          ),
        ),
      ],
    );
  }
}

class _EngineDiagnosisPanel extends ConsumerStatefulWidget {
  const _EngineDiagnosisPanel();

  @override
  ConsumerState<_EngineDiagnosisPanel> createState() =>
      _EngineDiagnosisPanelState();
}

class _EngineDiagnosisPanelState extends ConsumerState<_EngineDiagnosisPanel> {
  bool _open = false;

  @override
  Widget build(BuildContext context) {
    final diagAsync = _open ? ref.watch(engineDiagnosisProvider) : null;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
      child: SutraCard(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.biotech_outlined, size: 14, color: AppColors.goldDark),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    'OPENCODE SIDECAR DIAGNOSTIC',
                    style: AppTextStyles.smallCapsLabel(
                      fontSize: 10,
                      color: AppColors.lightTextPrimary,
                      letterSpacing: 1.4,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                if (_open)
                  TextButton(
                    onPressed: () => ref.refresh(engineDiagnosisProvider),
                    child: Text(
                      'RE-RUN',
                      style: AppTextStyles.smallCapsLabel(
                        fontSize: 9,
                        color: AppColors.goldDark,
                      ),
                    ),
                  ),
                TextButton(
                  onPressed: () => setState(() => _open = !_open),
                  child: Text(
                    _open ? 'CLOSE' : 'RUN CHECK',
                    style: AppTextStyles.smallCapsLabel(
                      fontSize: 9,
                      color: AppColors.gold,
                    ),
                  ),
                ),
              ],
            ),
            if (!_open)
              Text(
                'Runs a live round-trip to prove the sidecar can generate, not '
                'just that the port is open.',
                style: AppTextStyles.bodySmall(
                  color: AppColors.lightTextSecondary,
                ),
              ),
            if (diagAsync != null) ...[
              const SizedBox(height: AppSpacing.sm),
              diagAsync.when(
                loading: () => Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const LinearProgressIndicator(
                      minHeight: 2,
                      color: AppColors.gold,
                      backgroundColor: AppColors.lightSurfaceSubtle,
                    ),
                    const SizedBox(height: 6),
                    Text(
                      'Running live round-trip check...',
                      style: AppTextStyles.bodySmall(
                        color: AppColors.lightTextSecondary,
                      ),
                    ),
                  ],
                ),
                error: (e, _) => Text(
                  'Diagnostic failed: $e',
                  style: AppTextStyles.bodySmall(
                    color: AppColors.statusErrorRed,
                  ),
                ),
                data: (diag) => Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 6,
                          height: 6,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: diag.ok
                                ? AppColors.statusLiveGreen
                                : AppColors.statusErrorRed,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            diag.ok ? 'ALL CHECKS PASSED' : 'DIAGNOSIS WARNINGS',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: AppTextStyles.smallCapsLabel(
                              fontSize: 9,
                              color: diag.ok
                                  ? AppColors.statusLiveGreen
                                  : AppColors.statusErrorRed,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        if (diag.model != null) ...[
                          const SizedBox(width: AppSpacing.xs),
                          Flexible(
                            child: Text(
                              diag.model!,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: AppTextStyles.mono(
                                fontSize: 9,
                                color: AppColors.lightTextMuted,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    for (final check in diag.checks)
                      _DiagnosisCheckRow(check: check),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _DiagnosisCheckRow extends StatelessWidget {
  const _DiagnosisCheckRow({required this.check});

  final EngineCheckModel check;

  @override
  Widget build(BuildContext context) {
    final color = switch (check.status.toLowerCase()) {
      'ok' || 'pass' || 'passed' || 'healthy' => AppColors.statusLiveGreen,
      'warn' || 'warning' => AppColors.statusWarningAmber,
      _ => AppColors.statusErrorRed,
    };
    return Container(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      margin: const EdgeInsets.only(bottom: AppSpacing.sm),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppColors.lightBorder)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(color: color, shape: BoxShape.circle),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  check.name,
                  style: AppTextStyles.bodySmall(
                    color: AppColors.lightTextPrimary,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              Text(
                check.status.toUpperCase(),
                style: AppTextStyles.mono(fontSize: 9, color: color),
              ),
            ],
          ),
          if (check.detail != null)
            Padding(
              padding: const EdgeInsets.only(left: 12, top: 2),
              child: Text(
                check.detail!,
                style: AppTextStyles.bodySmall(
                  color: AppColors.lightTextSecondary,
                  fontSize: 11,
                ),
              ),
            ),
          if (check.fix != null)
            Container(
              margin: const EdgeInsets.only(left: 12, top: 4),
              padding: const EdgeInsets.all(AppSpacing.sm),
              decoration: BoxDecoration(
                color: AppColors.lightSurfaceSubtle,
                borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                border: Border.all(color: AppColors.lightBorder),
              ),
              child: Text(
                check.fix!,
                style: AppTextStyles.mono(
                  fontSize: 10,
                  color: AppColors.lightTextPrimary,
                ),
              ),
            ),
        ],
      ),
    );
  }
}