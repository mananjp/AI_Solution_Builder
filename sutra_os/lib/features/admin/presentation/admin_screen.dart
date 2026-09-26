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
import '../../auth/presentation/auth_controller.dart';
import '../data/admin_repository.dart';

class AdminScreen extends ConsumerWidget {
  const AdminScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authControllerProvider);
    final user = authState.user;
    final isAdmin = user?.isAdmin ?? false;

    // RBAC Guard: If not admin, display "Insufficient Permissions" (403 forbidden state)
    if (!isAdmin) {
      return Scaffold(
        backgroundColor: AppColors.lightBackground,
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.xxl),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    width: 64,
                    height: 64,
                    decoration: BoxDecoration(
                      color: AppColors.goldSubtle,
                      borderRadius: BorderRadius.circular(AppSpacing.radiusSm),
                      border: Border.all(color: AppColors.gold.withValues(alpha: 0.4)),
                    ),
                    child: const Icon(
                      Icons.shield_outlined,
                      color: AppColors.gold,
                      size: 32,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  Text(
                    'RBAC ENFORCEMENT • 403 FORBIDDEN',
                    style: AppTextStyles.smallCapsLabel(
                      fontSize: 10,
                      color: AppColors.goldDark,
                      letterSpacing: 2.4,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    'Admin Role Required',
                    style: AppTextStyles.serifHeading(
                      fontSize: 24,
                      color: AppColors.lightTextPrimary,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 380),
                    child: Text(
                      'You are currently signed in as "${user?.roleDisplayName ?? 'Guest Architect'}". This governance console is restricted exclusively to organization administrators.',
                      textAlign: TextAlign.center,
                      style: AppTextStyles.bodyMedium(
                        color: AppColors.lightTextSecondary,
                      ),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.xl),
                  SutraButton(
                    label: 'Return to Dashboard',
                    height: 42,
                    variant: SutraButtonVariant.primaryBlack,
                    onPressed: () => context.go('/dashboard'),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    }

    final statsAsync = ref.watch(adminStatsProvider);
    final usersAsync = ref.watch(adminUsersProvider);
    final auditLogsAsync = ref.watch(adminAuditLogsProvider);

    return Scaffold(
      backgroundColor: AppColors.lightBackground,
      body: SafeArea(
        child: RefreshIndicator(
          color: AppColors.blackButton,
          onRefresh: () async {
            ref.invalidate(adminStatsProvider);
            ref.invalidate(adminUsersProvider);
            ref.invalidate(adminAuditLogsProvider);
          },
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(
              parent: BouncingScrollPhysics(),
            ),
            slivers: [
              // Top Bar
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
                              'GOVERNANCE • SYSTEM ADMINISTRATION',
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
                              'Admin Console',
                              style: AppTextStyles.serifHeading(
                                fontSize: 22,
                                color: AppColors.lightTextPrimary,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      const StatusChip(
                        label: 'RBAC LEVEL',
                        statusText: 'ROOT ADMIN',
                      ),
                    ],
                  ),
                ),
              ),

              // Org-Wide Stat Cards Grid
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                  child: statsAsync.when(
                    data: (stats) => LayoutBuilder(
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
                              label: 'Total Users',
                              value: stats.totalUsers.toString(),
                              icon: Icons.people_outline,
                              iconColor: AppColors.gold,
                            ),
                            StatCard(
                              label: 'Workspaces',
                              value: stats.totalWorkspaces.toString(),
                              icon: Icons.folder_outlined,
                              iconColor: AppColors.lightTextSecondary,
                            ),
                            StatCard(
                              label: 'Total Solutions',
                              value: stats.totalSolutions.toString(),
                              icon: Icons.layers_outlined,
                              iconColor: AppColors.statusBlue,
                            ),
                            StatCard(
                              label: 'Credits Used',
                              value: stats.totalCreditsConsumed.toString(),
                              icon: Icons.bolt,
                              iconColor: AppColors.goldLight,
                            ),
                          ],
                        );
                      },
                    ),
                    loading: () => const Center(
                      child: Padding(
                        padding: EdgeInsets.all(AppSpacing.lg),
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: AppColors.blackButton,
                        ),
                      ),
                    ),
                    // A failed stats fetch rendered nothing at all, so the
                    // admin saw an empty grid with no indication of failure.
                    error: (_, __) => _adminErrorCard('Metrics unavailable'),
                  ),
                ),
              ),

              const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.xl)),

              // User Management Section
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'IDENTITY & ACCESS',
                        style: AppTextStyles.smallCapsLabel(
                          fontSize: 10,
                          color: AppColors.gold,
                          letterSpacing: 2.0,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        'Active Members & Tenants',
                        style: AppTextStyles.serifHeading(
                          fontSize: 18,
                          color: AppColors.lightTextPrimary,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.md),
                      usersAsync.when(
                        data: (users) {
                          if (users.isEmpty) {
                            return SutraCard(
                              padding: const EdgeInsets.all(AppSpacing.lg),
                              child: Text(
                                'No registered users found.',
                                style: AppTextStyles.bodySmall(
                                  color: AppColors.lightTextSecondary,
                                ),
                              ),
                            );
                          }
                          return SutraCard(
                            padding: const EdgeInsets.all(AppSpacing.md),
                            child: ListView.separated(
                              shrinkWrap: true,
                              physics: const NeverScrollableScrollPhysics(),
                              itemCount: users.length,
                              separatorBuilder: (_, __) => const Divider(
                                color: AppColors.lightBorder,
                                height: AppSpacing.md,
                              ),
                              itemBuilder: (context, index) {
                                final u = users[index];
                                return Row(
                                  children: [
                                    Container(
                                      width: 32,
                                      height: 32,
                                      decoration: BoxDecoration(
                                        color: AppColors.blackButton,
                                        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                                      ),
                                      alignment: Alignment.center,
                                      child: Text(
                                        u.email.isNotEmpty
                                            ? u.email[0].toUpperCase()
                                            : 'U',
                                        style: const TextStyle(
                                          color: Colors.white,
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
                                            u.email,
                                            style: AppTextStyles.bodyMedium(
                                              color: AppColors.lightTextPrimary,
                                              fontWeight: FontWeight.w600,
                                            ),
                                          ),
                                          Text(
                                            'Joined: ${u.createdAt}',
                                            style: AppTextStyles.bodySmall(
                                              color: AppColors.lightTextSecondary,
                                              fontSize: 11,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 8,
                                        vertical: 3,
                                      ),
                                      decoration: BoxDecoration(
                                        color: u.role == 'admin'
                                            ? AppColors.goldBadgeBg
                                            : AppColors.lightSurfaceSubtle,
                                        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                                        border: Border.all(
                                          color: u.role == 'admin'
                                              ? AppColors.gold
                                              : AppColors.lightBorder,
                                        ),
                                      ),
                                      child: Text(
                                        u.role.toUpperCase(),
                                        style: AppTextStyles.smallCapsLabel(
                                          fontSize: 9,
                                          color: u.role == 'admin'
                                              ? AppColors.goldDark
                                              : AppColors.lightTextSecondary,
                                          fontWeight: FontWeight.w700,
                                        ),
                                      ),
                                    ),
                                  ],
                                );
                              },
                            ),
                          );
                        },
                        loading: () => const Center(
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: AppColors.blackButton,
                          ),
                        ),
                        // This used to read "Organization members endpoint
                        // online." on failure, telling the admin the exact
                        // opposite of what happened.
                        error: (_, __) => _adminErrorCard('Members unavailable'),
                      ),
                    ],
                  ),
                ),
              ),

              const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.xl)),

              // Security Audit Logs Section
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'SECURITY & COMPLIANCE',
                        style: AppTextStyles.smallCapsLabel(
                          fontSize: 10,
                          color: AppColors.gold,
                          letterSpacing: 2.0,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        'Audit Trail',
                        style: AppTextStyles.serifHeading(
                          fontSize: 18,
                          color: AppColors.lightTextPrimary,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.md),
                      auditLogsAsync.when(
                        data: (logs) {
                          if (logs.isEmpty) {
                            return SutraCard(
                              padding: const EdgeInsets.all(AppSpacing.lg),
                              child: Text(
                                'No recent security alerts recorded.',
                                style: AppTextStyles.bodySmall(
                                  color: AppColors.lightTextSecondary,
                                ),
                              ),
                            );
                          }
                          return SutraCard(
                            padding: const EdgeInsets.all(AppSpacing.md),
                            child: ListView.separated(
                              shrinkWrap: true,
                              physics: const NeverScrollableScrollPhysics(),
                              itemCount: logs.length,
                              separatorBuilder: (_, __) => const Divider(
                                color: AppColors.lightBorder,
                                height: AppSpacing.md,
                              ),
                              itemBuilder: (context, index) {
                                final log = logs[index];
                                return Row(
                                  children: [
                                    const Icon(
                                      Icons.security,
                                      size: 16,
                                      color: AppColors.gold,
                                    ),
                                    const SizedBox(width: AppSpacing.md),
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            log.description ?? log.action,
                                            style: AppTextStyles.bodyMedium(
                                              color: AppColors.lightTextPrimary,
                                              fontWeight: FontWeight.w600,
                                            ),
                                          ),
                                          Text(
                                            '${log.action} • ${log.timestamp}',
                                            style: AppTextStyles.bodySmall(
                                              color: AppColors.lightTextSecondary,
                                              fontSize: 11,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                    Text(
                                      log.amountLabel,
                                      style: AppTextStyles.mono(
                                        fontSize: 10,
                                        color: log.amount < 0
                                            ? AppColors.statusErrorRed
                                            : AppColors.statusLiveGreen,
                                      ),
                                    ),
                                  ],
                                );
                              },
                            ),
                          );
                        },
                        loading: () => const Center(
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: AppColors.blackButton,
                          ),
                        ),
                        error: (_, __) =>
                            _adminErrorCard('Audit trail unavailable'),
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

  /// A neutral failure notice. Deliberately says nothing is known about the
  /// data rather than asserting the subsystem is healthy.
  Widget _adminErrorCard(String message) {
    return SutraCard(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Row(
        children: [
          const Icon(Icons.cloud_off_outlined,
              size: 16, color: AppColors.statusErrorRed),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              message,
              style: AppTextStyles.bodySmall(
                color: AppColors.lightTextSecondary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
