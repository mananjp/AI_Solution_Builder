import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/widgets/sutra_button.dart';
import '../../auth/presentation/auth_controller.dart';
import '../../billing/data/billing_repository.dart';
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
              workspacesAsync.maybeWhen(
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
                        '${ws.solutionCount} Blueprints • ACTIVE',
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
                orElse: () => const Text('Primary Workspace'),
              ),
            ],
          ),
        ),
      ),
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

  void _showSearchModal(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.lightSurface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(AppSpacing.radiusMd)),
      ),
      builder: (ctx) => Padding(
        padding: EdgeInsets.only(
          top: AppSpacing.lg,
          left: AppSpacing.lg,
          right: AppSpacing.lg,
          bottom: MediaQuery.of(context).viewInsets.bottom + AppSpacing.lg,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.search, size: 20, color: AppColors.gold),
                const SizedBox(width: AppSpacing.sm),
                Text('Quick Search & Jump', style: AppTextStyles.serifHeading(fontSize: 18)),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            TextField(
              autofocus: true,
              style: AppTextStyles.bodyMedium(color: AppColors.lightTextPrimary),
              decoration: InputDecoration(
                hintText: 'Search blueprints, PostgreSQL DDL, routes...',
                prefixIcon: const Icon(Icons.search, size: 18, color: AppColors.lightTextSecondary),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                  borderSide: const BorderSide(color: AppColors.lightBorder),
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                _buildSearchTag(ctx, context, 'E-Commerce Mesh', '/workspace'),
                _buildSearchTag(ctx, context, 'PostgreSQL Schema', '/workspace'),
                _buildSearchTag(ctx, context, 'Credit Balance', '/billing'),
                _buildSearchTag(ctx, context, 'Render API Key', '/settings'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSearchTag(BuildContext sheetCtx, BuildContext navCtx, String label, String route) {
    return GestureDetector(
      onTap: () {
        Navigator.pop(sheetCtx);
        navCtx.go(route);
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: AppColors.lightSurfaceSubtle,
          borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
          border: Border.all(color: AppColors.lightBorder),
        ),
        child: Text(
          label,
          style: AppTextStyles.bodySmall(color: AppColors.lightTextPrimary),
        ),
      ),
    );
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
                              'Primary Workspace',
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
                            data: (u) => '${u.creditsRemaining}',
                            orElse: () => '420',
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
                    onPressed: () => _showSearchModal(context),
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
                        onPressed: () {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Swarm telemetry: All synthesis nodes operational.'),
                              duration: Duration(seconds: 1),
                            ),
                          );
                        },
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
