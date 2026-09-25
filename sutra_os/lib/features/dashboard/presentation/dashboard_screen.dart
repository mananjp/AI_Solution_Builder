import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/widgets/stat_card.dart';
import '../../../core/widgets/status_chip.dart';
import '../../../core/widgets/sutra_button.dart';
import '../../../core/widgets/sutra_card.dart';
import '../../billing/data/billing_repository.dart';
import '../../workspace/data/workspace_repository.dart';
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
                          final wsId = ref.read(activeWorkspaceIdProvider) ?? 'ws_default';
                          final repo = ref.read(workspaceRepositoryProvider);
                          final solution = await repo.createSolution(
                            workspaceId: wsId,
                            title: title,
                            description: descController.text.trim(),
                          );
                          ref.read(activeSolutionIdProvider.notifier).set(solution.id);
                          if (dialogCtx.mounted) {
                            Navigator.pop(dialogCtx);
                            ref.invalidate(workspacesListProvider);
                            context.go('/workspace');
                          }
                        } catch (_) {
                          if (dialogCtx.mounted) {
                            Navigator.pop(dialogCtx);
                            context.go('/workspace');
                          }
                        }
                      },
              ),
            ],
          );
        },
      ),
    );
  }

  void _buildStarterApp(BuildContext context, WidgetRef ref, String templateTitle, String description) async {
    final wsId = ref.read(activeWorkspaceIdProvider) ?? 'ws_default';
    final repo = ref.read(workspaceRepositoryProvider);

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Dispatching autonomous synthesis for $templateTitle...')),
    );

    try {
      final sol = await repo.createSolution(
        workspaceId: wsId,
        title: templateTitle,
        description: description,
      );
      ref.read(activeSolutionIdProvider.notifier).set(sol.id);
      ref.invalidate(workspacesListProvider);
      if (context.mounted) {
        context.go('/workspace');
      }
    } catch (_) {
      if (context.mounted) {
        context.go('/workspace');
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final workspacesAsync = ref.watch(workspacesListProvider);
    final usageAsync = ref.watch(billingUsageProvider);

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
                        data: (usage) => usage.creditsRemaining,
                        orElse: () => 420,
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
                                value: '● LIVE',
                                icon: Icons.memory,
                                iconColor: AppColors.statusLiveGreen,
                              ),
                              StatCard(
                                label: 'Compute Credits',
                                value: creditsRemaining.toString(),
                                icon: Icons.bolt,
                                iconColor: AppColors.gold,
                              ),
                              StatCard(
                                label: 'Total Solutions',
                                value: (totalSolutions > 0 ? totalSolutions : 3).toString(),
                                icon: Icons.layers_outlined,
                                iconColor: AppColors.lightTextPrimary,
                              ),
                              StatCard(
                                label: 'Active Swarms',
                                value: '1 Active',
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
                    error: (_, __) => StatCard(
                      label: 'Status',
                      value: 'Online',
                      icon: Icons.check_circle_outline,
                      iconColor: AppColors.statusLiveGreen,
                    ),
                  ),
                ),
              ),

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

              // Starter Templates Cards
              SliverToBoxAdapter(
                child: SizedBox(
                  height: 175,
                  child: ListView(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                    children: [
                      _buildTemplateCard(
                        title: 'E-Commerce Mesh',
                        stack: 'PostgreSQL • FastAPI • Stripe',
                        description: 'Multi-tenant cart, inventory reservations & webhook ledger.',
                        onTap: () => _buildStarterApp(
                          context,
                          ref,
                          'E-Commerce Microservices',
                          'Multi-tenant checkout, inventory ledger, Stripe webhooks, and order dispatch.',
                        ),
                      ),
                      const SizedBox(width: AppSpacing.md),
                      _buildTemplateCard(
                        title: 'AI SaaS Boilerplate',
                        stack: 'VectorDB • JWT • Render',
                        description: 'Auth roles, token quotas, and background embedding queue.',
                        onTap: () => _buildStarterApp(
                          context,
                          ref,
                          'AI SaaS Boilerplate',
                          'Subscription quotas, vector embeddings, JWT session guards, and rate limiter.',
                        ),
                      ),
                      const SizedBox(width: AppSpacing.md),
                      _buildTemplateCard(
                        title: 'Logistics Fleet OS',
                        stack: 'Kafka • Telematics • Maps',
                        description: 'Real-time vehicle telemetry, geofencing, and driver dispatch.',
                        onTap: () => _buildStarterApp(
                          context,
                          ref,
                          'Logistics Fleet OS',
                          'Vehicle IoT telemetry, route optimization, geofenced triggers, and dispatch.',
                        ),
                      ),
                    ],
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
                      _buildRecentBlueprintItem(
                        context: context,
                        title: 'Autonomous Payment Router',
                        spec: 'PostgreSQL DDL • 14 Endpoints',
                        stateBadge: 'SYNTHESIZED',
                        stateColor: const Color(0xFF2E7D32),
                        stateBg: const Color(0xFFEAF4EC),
                        timestamp: '12m ago',
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      _buildRecentBlueprintItem(
                        context: context,
                        title: 'Omni-Channel Agent Swarm',
                        spec: 'WebSocket • Event Mesh • Redis',
                        stateBadge: 'BUILDING',
                        stateColor: AppColors.goldDark,
                        stateBg: AppColors.goldSubtle,
                        timestamp: '45m ago',
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      _buildRecentBlueprintItem(
                        context: context,
                        title: 'Identity & Access Mesh',
                        spec: 'OAuth2 • JWT • RBAC',
                        stateBadge: 'DRAFT',
                        stateColor: AppColors.lightTextSecondary,
                        stateBg: AppColors.lightSurfaceSubtle,
                        timestamp: '2d ago',
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

  Widget _buildRecentBlueprintItem({
    required BuildContext context,
    required String title,
    required String spec,
    required String stateBadge,
    required Color stateColor,
    required Color stateBg,
    required String timestamp,
  }) {
    return GestureDetector(
      onTap: () => context.go('/workspace'),
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
                    title,
                    style: AppTextStyles.bodyMedium(
                      color: AppColors.lightTextPrimary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  Text(
                    '$spec • $timestamp',
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
                color: stateBg,
                borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
              ),
              child: Text(
                stateBadge,
                style: AppTextStyles.smallCapsLabel(
                  fontSize: 8,
                  color: stateColor,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
