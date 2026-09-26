import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/widgets/sutra_button.dart';
import '../../auth/presentation/auth_controller.dart';
import '../../billing/data/billing_repository.dart';
import '../../engine/domain/engine_models.dart';
import '../../engine/presentation/engine_providers.dart';
import '../../workspace/data/workspace_repository.dart';
import '../../workspace/presentation/workspace_providers.dart';

class NavigationShell extends ConsumerWidget {
  final StatefulNavigationShell navigationShell;

  const NavigationShell({
    super.key,
    required this.navigationShell,
  });

  void _onDestinationSelected(int index) {
    navigationShell.goBranch(
      index,
      initialLocation: index == navigationShell.currentIndex,
    );
  }

  /// Overflow entries for the workspace branch's sub-routes.
  void _showWorkspaceTools(BuildContext context) {
    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.lightSurface,
      shape: const RoundedRectangleBorder(
        borderRadius:
            BorderRadius.vertical(top: Radius.circular(AppSpacing.radiusMd)),
      ),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: AppSpacing.sm),
            Container(
              width: 36,
              height: 4,
              decoration: BoxDecoration(
                color: AppColors.lightBorder,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            ListTile(
              leading: const Icon(Icons.account_tree_outlined),
              title: const Text('Blueprint Review'),
              subtitle: const Text('Artifacts, approvals, export'),
              onTap: () {
                Navigator.of(ctx).pop();
                context.go('/solution');
              },
            ),
            ListTile(
              leading: const Icon(Icons.inventory_2_outlined),
              title: const Text('Builds'),
              subtitle: const Text('Build, download, deploy'),
              onTap: () {
                Navigator.of(ctx).pop();
                context.go('/builds');
              },
            ),
            ListTile(
              leading: const Icon(Icons.forum_outlined),
              title: const Text('Build Chat'),
              subtitle: const Text('Streaming agent session'),
              onTap: () {
                Navigator.of(ctx).pop();
                context.go('/chat');
              },
            ),
            ListTile(
              leading: const Icon(Icons.terminal_outlined),
              title: const Text('Sandbox'),
              subtitle: const Text('Browse files and preview the app'),
              onTap: () {
                Navigator.of(ctx).pop();
                context.go('/sandbox');
              },
            ),
            ListTile(
              leading: const Icon(Icons.rocket_launch_outlined),
              title: const Text('Live App'),
              subtitle: const Text('Workable Systems preview'),
              onTap: () {
                Navigator.of(ctx).pop();
                context.go('/live-app');
              },
            ),
            const SizedBox(height: AppSpacing.sm),
          ],
        ),
      ),
    );
  }

  /// Replaces the old hardcoded "All synthesis nodes operational" toast with
  /// the engine's real polled health.
  void _showEngineStatus(BuildContext context, WidgetRef ref) {
    final healthAsync = ref.read(engineHealthProvider);
    final resourcesAsync = ref.read(systemResourcesProvider);

    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.lightSurface,
      shape: const RoundedRectangleBorder(
        borderRadius:
            BorderRadius.vertical(top: Radius.circular(AppSpacing.radiusMd)),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'SYNTHESIS ENGINE',
                style: AppTextStyles.smallCapsLabel(
                  fontSize: 10,
                  color: AppColors.goldDark,
                  letterSpacing: 2.0,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              healthAsync.when(
                loading: () => const LinearProgressIndicator(
                  minHeight: 3,
                  color: AppColors.gold,
                  backgroundColor: AppColors.lightSurfaceSubtle,
                ),
                error: (error, _) => Text(
                  'Engine status unavailable: $error',
                  style: AppTextStyles.bodySmall(
                    color: AppColors.statusErrorRed,
                  ),
                ),
                data: (health) => Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 8,
                          height: 8,
                          decoration: BoxDecoration(
                            color: health.isOnline
                                ? AppColors.statusLiveGreen
                                : AppColors.goldDark,
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Text(
                          health.statusLabel,
                          style: AppTextStyles.bodyMedium(
                            color: AppColors.lightTextPrimary,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
                    if (health.model != null) ...[
                      const SizedBox(height: 4),
                      Text(
                        'Model: ${health.model}',
                        style: AppTextStyles.bodySmall(
                          color: AppColors.lightTextSecondary,
                        ),
                      ),
                    ],
                    if (health.latencyMs != null) ...[
                      const SizedBox(height: 2),
                      Text(
                        'Latency: ${health.latencyMs}ms',
                        style: AppTextStyles.bodySmall(
                          color: AppColors.lightTextSecondary,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              resourcesAsync.when(
                loading: () => const SizedBox.shrink(),
                error: (_, __) => const SizedBox.shrink(),
                data: (resources) => Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'RESOURCES',
                      style: AppTextStyles.smallCapsLabel(
                        fontSize: 9,
                        color: AppColors.lightTextMuted,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _formatResources(resources),
                      style: AppTextStyles.bodySmall(
                        color: AppColors.lightTextSecondary,
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  static String _formatResources(SystemResourcesModel r) {
    final parts = <String>[];
    if (r.cpuPercent != null) {
      parts.add('CPU ${r.cpuPercent!.toStringAsFixed(0)}%');
    }
    if (r.cpuCount != null) parts.add('${r.cpuCount} cores');
    if (r.memoryPercent != null) {
      parts.add('RAM ${r.memoryPercent!.toStringAsFixed(0)}%');
    }
    if (r.diskPercent != null) {
      parts.add('Disk ${r.diskPercent!.toStringAsFixed(0)}%');
    }
    return parts.isEmpty ? 'No metrics reported.' : parts.join(' • ');
  }

  void _showWorkspacePicker(BuildContext context, WidgetRef ref) {
    final workspacesAsync = ref.read(workspacesListProvider);
    final activeWsId = ref.read(activeWorkspaceIdProvider);

    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.lightSurface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(AppSpacing.radiusMd)),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'ORGANIZATION WORKSPACES',
                style: AppTextStyles.smallCapsLabel(
                  fontSize: 10,
                  color: AppColors.goldDark,
                  letterSpacing: 2.0,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                'Switch Active Workspace',
                style: AppTextStyles.serifHeading(fontSize: 18),
              ),
              const SizedBox(height: AppSpacing.md),
              workspacesAsync.when(
                data: (list) => ListView.separated(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: list.length,
                  separatorBuilder: (_, __) => const Divider(color: AppColors.lightBorder),
                  itemBuilder: (context, i) {
                    final ws = list[i];
                    final isSelected = ws.id == activeWsId;
                    return ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: Icon(
                        Icons.folder_outlined,
                        color: isSelected ? AppColors.gold : AppColors.lightTextSecondary,
                      ),
                      title: Text(
                        ws.name,
                        style: AppTextStyles.bodyMedium(
                          color: AppColors.lightTextPrimary,
                          fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                        ),
                      ),
                      subtitle: Text(
                        // "ACTIVE" was hardcoded on every row, so every
                        // workspace looked selected.
                        isSelected
                            ? '${ws.solutionCount} Blueprints • ACTIVE'
                            : '${ws.solutionCount} Blueprints',
                        style: AppTextStyles.bodySmall(color: AppColors.lightTextSecondary),
                      ),
                      trailing: isSelected
                          ? const Icon(Icons.check, color: AppColors.gold, size: 18)
                          : null,
                      onTap: () {
                        ref.read(activeWorkspaceIdProvider.notifier).set(ws.id);
                        Navigator.pop(ctx);
                      },
                    );
                  },
                ),
                loading: () => const Center(
                  child: Padding(
                    padding: EdgeInsets.all(AppSpacing.md),
                    child: CircularProgressIndicator(
                      color: AppColors.blackButton,
                      strokeWidth: 2,
                    ),
                  ),
                ),
                error: (_, __) => Text(
                  'Could not load workspaces.',
                  style: AppTextStyles.bodySmall(
                    color: AppColors.statusErrorRed,
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              const Divider(color: AppColors.lightBorder),
              const SizedBox(height: AppSpacing.sm),
              // The workspace picker could change workspace but there was no
              // equivalent for solutions, so blueprints inside a workspace were
              // unreachable.
              _buildSolutionPickerSection(ctx, ref),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSolutionPickerSection(BuildContext ctx, WidgetRef ref) {
    final solutionsAsync = ref.watch(activeSolutionsProvider);
    final activeSolutionId = ref.watch(activeSolutionIdProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'BLUEPRINTS IN THIS WORKSPACE',
          style: AppTextStyles.smallCapsLabel(
            fontSize: 10,
            color: AppColors.goldDark,
            letterSpacing: 2.0,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: AppSpacing.xs),
        solutionsAsync.when(
          loading: () => const Padding(
            padding: EdgeInsets.symmetric(vertical: AppSpacing.sm),
            child: Center(
              child: CircularProgressIndicator(
                color: AppColors.blackButton,
                strokeWidth: 2,
              ),
            ),
          ),
          error: (_, __) => Text(
            'Could not load blueprints.',
            style: AppTextStyles.bodySmall(color: AppColors.statusErrorRed),
          ),
          data: (list) {
            if (list.isEmpty) {
              return Text(
                'No blueprints here yet. Create one to get started.',
                style: AppTextStyles.bodySmall(
                  color: AppColors.lightTextSecondary,
                ),
              );
            }
            return ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 260),
              child: ListView.builder(
                shrinkWrap: true,
                itemCount: list.length,
                itemBuilder: (context, i) {
                  final solution = list[i];
                  final isSelected = solution.id == activeSolutionId;
                  return ListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(
                      Icons.architecture,
                      size: 18,
                      color: isSelected
                          ? AppColors.gold
                          : AppColors.lightTextSecondary,
                    ),
                    title: Text(
                      solution.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.bodySmall(
                        color: AppColors.lightTextPrimary,
                        fontWeight:
                            isSelected ? FontWeight.bold : FontWeight.normal,
                      ),
                    ),
                    trailing: isSelected
                        ? const Icon(Icons.check, color: AppColors.gold, size: 16)
                        : null,
                    onTap: () {
                      ref
                          .read(activeSolutionIdProvider.notifier)
                          .set(solution.id);
                      Navigator.pop(ctx);
                    },
                  );
                },
              ),
            );
          },
        ),
      ],
    );
  }

  void _showNewSolutionDialog(BuildContext context, WidgetRef ref) {
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
              'New Architecture Solution',
              style: AppTextStyles.serifHeading(fontSize: 20),
            ),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Define project scope for autonomous agent decomposition.',
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
                      labelText: 'Product Spec / Intent',
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
                label: isCreating ? 'CREATING...' : '+ CREATE BLUEPRINT',
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

  /// Searches the user's real blueprints by title/description.
  ///
  /// This previously showed a `TextField` with no controller, no `onChanged`
  /// and no filtering, plus four hardcoded jump tags. It looked like search and
  /// did nothing.
  void _showSearchModal(BuildContext context, WidgetRef ref) {
    final solutionsAsync = ref.watch(activeSolutionsProvider);
    final searchController = TextEditingController();

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.lightSurface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(AppSpacing.radiusMd)),
      ),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheetState) {
          final query = searchController.text.trim().toLowerCase();
          final all = solutionsAsync.valueOrNull ?? const [];
          final matches = query.isEmpty
              ? all
              : all
                  .where((s) =>
                      s.title.toLowerCase().contains(query) ||
                      (s.description ?? '').toLowerCase().contains(query))
                  .toList();

          return Padding(
            padding: EdgeInsets.only(
              top: AppSpacing.lg,
              left: AppSpacing.lg,
              right: AppSpacing.lg,
              bottom: MediaQuery.of(ctx).viewInsets.bottom + AppSpacing.lg,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.search, size: 20, color: AppColors.gold),
                    const SizedBox(width: AppSpacing.sm),
                    Text('Search Blueprints',
                        style: AppTextStyles.serifHeading(fontSize: 18)),
                  ],
                ),
                const SizedBox(height: AppSpacing.md),
                TextField(
                  controller: searchController,
                  autofocus: true,
                  onChanged: (_) => setSheetState(() {}),
                  style:
                      AppTextStyles.bodyMedium(color: AppColors.lightTextPrimary),
                  decoration: InputDecoration(
                    hintText: 'Search by title or description...',
                    prefixIcon: const Icon(Icons.search,
                        size: 18, color: AppColors.lightTextSecondary),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                      borderSide: const BorderSide(color: AppColors.lightBorder),
                    ),
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
                if (solutionsAsync.isLoading)
                  const Center(
                    child: Padding(
                      padding: EdgeInsets.all(AppSpacing.md),
                      child: CircularProgressIndicator(
                        color: AppColors.blackButton,
                        strokeWidth: 2,
                      ),
                    ),
                  )
                else if (solutionsAsync.hasError)
                  Text(
                    'Could not load blueprints to search.',
                    style: AppTextStyles.bodySmall(
                      color: AppColors.statusErrorRed,
                    ),
                  )
                else if (matches.isEmpty)
                  Text(
                    query.isEmpty
                        ? 'No blueprints in this workspace yet.'
                        : 'Nothing matches "$query".',
                    style: AppTextStyles.bodySmall(
                      color: AppColors.lightTextSecondary,
                    ),
                  )
                else
                  ConstrainedBox(
                    constraints: const BoxConstraints(maxHeight: 320),
                    child: ListView.separated(
                      shrinkWrap: true,
                      itemCount: matches.length,
                      separatorBuilder: (_, __) =>
                          const Divider(color: AppColors.lightBorder),
                      itemBuilder: (_, i) {
                        final solution = matches[i];
                        return ListTile(
                          dense: true,
                          contentPadding: EdgeInsets.zero,
                          leading: const Icon(Icons.architecture,
                              size: 18, color: AppColors.gold),
                          title: Text(
                            solution.title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: AppTextStyles.bodyMedium(
                              color: AppColors.lightTextPrimary,
                            ),
                          ),
                          subtitle: solution.description == null
                              ? null
                              : Text(
                                  solution.description!,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: AppTextStyles.bodySmall(
                                    color: AppColors.lightTextSecondary,
                                    fontSize: 11,
                                  ),
                                ),
                          onTap: () {
                            ref
                                .read(activeSolutionIdProvider.notifier)
                                .set(solution.id);
                            Navigator.pop(ctx);
                            context.go('/workspace');
                          },
                        );
                      },
                    ),
                  ),
              ],
            ),
          );
        },
      ),
    ).whenComplete(searchController.dispose);
  }

  void _showUserMenu(BuildContext context, WidgetRef ref, String initial) {
    final authState = ref.read(authControllerProvider);
    final user = authState.user;

    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.lightSurface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(AppSpacing.radiusMd)),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 44,
                    height: 44,
                    decoration: const BoxDecoration(
                      color: AppColors.blackButton,
                      shape: BoxShape.circle,
                    ),
                    alignment: Alignment.center,
                    child: Text(
                      initial,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          user?.fullName.isNotEmpty == true ? user!.fullName : 'Architect',
                          style: AppTextStyles.serifHeading(fontSize: 18),
                        ),
                        Text(
                          user?.email ?? 'architect@sutraos.io',
                          style: AppTextStyles.bodySmall(color: AppColors.lightTextSecondary),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: AppColors.goldBadgeBg,
                      borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                    ),
                    child: Text(
                      user?.roleDisplayName ?? 'PRO MEMBER',
                      style: AppTextStyles.smallCapsLabel(
                        fontSize: 9,
                        color: AppColors.goldDark,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.lg),
              const Divider(color: AppColors.lightBorder),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.credit_card_outlined, color: AppColors.lightTextPrimary),
                title: Text('Billing, Plans & Invoices', style: AppTextStyles.bodyMedium()),
                onTap: () {
                  Navigator.pop(ctx);
                  context.go('/billing');
                },
              ),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.settings_outlined, color: AppColors.lightTextPrimary),
                title: Text('Cloud Deployer Settings', style: AppTextStyles.bodyMedium()),
                onTap: () {
                  Navigator.pop(ctx);
                  context.go('/settings');
                },
              ),
              if (user?.isAdmin ?? false)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.shield_outlined, color: AppColors.gold),
                  title: Text('Admin Console', style: AppTextStyles.bodyMedium(color: AppColors.goldDark)),
                  onTap: () {
                    Navigator.pop(ctx);
                    context.go('/admin');
                  },
                ),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.logout, color: AppColors.statusErrorRed),
                title: Text('Sign Out', style: AppTextStyles.bodyMedium(color: AppColors.statusErrorRed)),
                onTap: () async {
                  Navigator.pop(ctx);
                  await ref.read(authControllerProvider.notifier).logout();
                  if (context.mounted) {
                    context.go('/');
                  }
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authControllerProvider);
    final user = authState.user;
    final isAdmin = user?.isAdmin ?? false;
    final usageAsync = ref.watch(billingUsageProvider);
    // Resolve the selected workspace's real name for the header pill.
    final workspacesAsync = ref.watch(workspacesListProvider);
    final activeWorkspaceId = ref.watch(activeWorkspaceIdProvider);
    final activeWorkspaceName = workspacesAsync.maybeWhen(
      data: (list) {
        for (final ws in list) {
          if (ws.id == activeWorkspaceId) return ws.name;
        }
        return list.isEmpty ? 'No Workspace' : list.first.name;
      },
      orElse: () => 'Loading...',
    );
    final userInitial = user?.fullName.isNotEmpty == true
        ? user!.fullName[0].toUpperCase()
        : (user?.email.isNotEmpty == true ? user!.email[0].toUpperCase() : 'A');
    final screenWidth = MediaQuery.of(context).size.width;
    final isNarrow = screenWidth <= 380;
    final isUltraNarrow = screenWidth <= 340;

    return Scaffold(
      backgroundColor: AppColors.lightBackground,
      // Refined Mobile Atelier Top App Bar — completely overflow-proof
      appBar: PreferredSize(
        preferredSize: const Size.fromHeight(56),
        child: Container(
          padding: EdgeInsets.symmetric(
            horizontal: isNarrow ? AppSpacing.sm : AppSpacing.md,
          ),
          decoration: const BoxDecoration(
            color: AppColors.lightBackground,
            border: Border(
              bottom: BorderSide(color: AppColors.lightBorder, width: 1),
            ),
          ),
          child: SafeArea(
            child: Row(
              children: [
                // Left Brand Glyph
                Text(
                  'सूत्र',
                  style: AppTextStyles.devanagariGlyph(
                    fontSize: isNarrow ? 20 : 22,
                    color: AppColors.gold,
                  ),
                ),
                const SizedBox(width: 4),
                Text(
                  'OS',
                  style: AppTextStyles.smallCapsLabel(
                    fontSize: 10,
                    color: AppColors.lightTextPrimary,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1.2,
                  ),
                ),
                const SizedBox(width: 6),

                // Workspace selector dropdown with flexible truncation
                Flexible(
                  child: GestureDetector(
                    onTap: () => _showWorkspacePicker(context, ref),
                    child: Container(
                      constraints: BoxConstraints(
                        maxWidth: isNarrow ? 120 : 150,
                      ),
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
                      decoration: BoxDecoration(
                        color: AppColors.lightSurface,
                        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                        border: Border.all(color: AppColors.lightBorder),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Flexible(
                            child: Text(
                              // The real workspace name. This was the literal
                              // string 'Primary Workspace' regardless of which
                              // workspace was actually selected.
                              activeWorkspaceName,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: AppTextStyles.smallCapsLabel(
                                fontSize: 9,
                                color: AppColors.lightTextPrimary,
                                fontWeight: FontWeight.w600,
                                letterSpacing: 0.3,
                              ),
                            ),
                          ),
                          const SizedBox(width: 2),
                          const Icon(Icons.arrow_drop_down, size: 14, color: AppColors.lightTextSecondary),
                        ],
                      ),
                    ),
                  ),
                ),

                const Spacer(),

                // Live Credit Pill: "⚡ 420"
                GestureDetector(
                  onTap: () => context.go('/billing'),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppColors.goldSubtle,
                      borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
                      border: Border.all(color: AppColors.gold.withValues(alpha: 0.3)),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.bolt, size: 12, color: AppColors.gold),
                        const SizedBox(width: 2),
                        Text(
                          usageAsync.maybeWhen(
                            data: (u) => u.isUnlimited
                                ? '∞'
                                : '${u.creditsRemaining}',
                            orElse: () => '--',
                          ),
                          style: AppTextStyles.smallCapsLabel(
                            fontSize: 9,
                            color: AppColors.goldDark,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 0.4,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),

                const SizedBox(width: 4),

                // New Blueprint Action
                IconButton(
                  icon: const Icon(Icons.add, size: 19, color: AppColors.lightTextPrimary),
                  padding: const EdgeInsets.all(4),
                  constraints: const BoxConstraints(),
                  tooltip: 'New Blueprint',
                  onPressed: () => _showNewSolutionDialog(context, ref),
                ),

                // Search Icon (shown if not ultra-narrow)
                if (!isUltraNarrow) ...[
                  const SizedBox(width: 4),
                  IconButton(
                    icon: const Icon(Icons.search, size: 18, color: AppColors.lightTextSecondary),
                    padding: const EdgeInsets.all(4),
                    constraints: const BoxConstraints(),
                    tooltip: 'Search',
                    onPressed: () => _showSearchModal(context, ref),
                  ),
                ],

                // Workspace tools: blueprint review, builds, build chat.
                // The bottom bar is branch-indexed and already full, so the
                // extra workspace sub-routes live behind an overflow menu.
                if (navigationShell.currentIndex == 1) ...[
                  const SizedBox(width: 4),
                  IconButton(
                    icon: const Icon(Icons.more_vert, size: 19, color: AppColors.lightTextSecondary),
                    padding: const EdgeInsets.all(4),
                    constraints: const BoxConstraints(),
                    tooltip: 'Workspace tools',
                    onPressed: () => _showWorkspaceTools(context),
                  ),
                ],

                // Notification Bell with Gold Dot (shown on wider screens)
                if (!isNarrow) ...[
                  const SizedBox(width: 4),
                  Stack(
                    alignment: Alignment.topRight,
                    children: [
                      IconButton(
                        icon: const Icon(Icons.notifications_none_outlined, size: 19, color: AppColors.lightTextSecondary),
                        padding: const EdgeInsets.all(4),
                        constraints: const BoxConstraints(),
                        onPressed: () => _showEngineStatus(context, ref),
                      ),
                      Container(
                        width: 5,
                        height: 5,
                        decoration: const BoxDecoration(
                          color: AppColors.gold,
                          shape: BoxShape.circle,
                        ),
                      ),
                    ],
                  ),
                ],

                const SizedBox(width: 6),

                // User Avatar Circle
                GestureDetector(
                  onTap: () => _showUserMenu(context, ref, userInitial),
                  child: Container(
                    width: 26,
                    height: 26,
                    decoration: const BoxDecoration(
                      color: AppColors.blackButton,
                      shape: BoxShape.circle,
                    ),
                    alignment: Alignment.center,
                    child: Text(
                      userInitial,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),

      // Active screen branch
      body: navigationShell,

      // Docked Atelier Bottom Navigation Bar
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: AppColors.lightBackground,
          border: Border(
            top: BorderSide(color: AppColors.lightBorder, width: 1),
          ),
        ),
        child: SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Row(
              children: [
                Expanded(
                  child: _buildNavItem(
                    index: 0,
                    label: 'Overview',
                    icon: Icons.dashboard_outlined,
                    selectedIcon: Icons.dashboard,
                    isNarrow: isNarrow,
                  ),
                ),
                Expanded(
                  child: _buildNavItem(
                    index: 1,
                    label: 'Workspace',
                    icon: Icons.alt_route_outlined,
                    selectedIcon: Icons.alt_route,
                    isNarrow: isNarrow,
                  ),
                ),
                Expanded(
                  child: _buildNavItem(
                    index: 2,
                    label: 'Billing',
                    icon: Icons.credit_card_outlined,
                    selectedIcon: Icons.credit_card,
                    isNarrow: isNarrow,
                  ),
                ),
                Expanded(
                  child: _buildNavItem(
                    index: 3,
                    label: 'Deployer',
                    icon: Icons.settings_outlined,
                    selectedIcon: Icons.settings,
                    isNarrow: isNarrow,
                  ),
                ),
                if (isAdmin)
                  Expanded(
                    child: _buildNavItem(
                      index: 4,
                      label: 'Admin',
                      icon: Icons.shield_outlined,
                      selectedIcon: Icons.shield,
                      isNarrow: isNarrow,
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildNavItem({
    required int index,
    required String label,
    required IconData icon,
    required IconData selectedIcon,
    required bool isNarrow,
  }) {
    final isSelected = navigationShell.currentIndex == index;

    return GestureDetector(
      onTap: () => _onDestinationSelected(index),
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: EdgeInsets.symmetric(
          horizontal: isNarrow ? 4 : 8,
          vertical: 4,
        ),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.goldSubtle : Colors.transparent,
          borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              isSelected ? selectedIcon : icon,
              size: isNarrow ? 18 : 20,
              color: isSelected ? AppColors.goldDark : AppColors.lightTextSecondary,
            ),
            const SizedBox(height: 2),
            FittedBox(
              fit: BoxFit.scaleDown,
              child: Text(
                label,
                style: AppTextStyles.smallCapsLabel(
                  fontSize: 9,
                  color: isSelected ? AppColors.goldDark : AppColors.lightTextSecondary,
                  letterSpacing: isNarrow ? 0.4 : 0.8,
                  fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
