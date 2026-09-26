import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/widgets/masked_secret_field.dart';
import '../../../core/widgets/status_chip.dart';
import '../../../core/widgets/sutra_button.dart';
import '../../../core/widgets/sutra_card.dart';
import '../../auth/presentation/auth_controller.dart';
import '../data/settings_repository.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  final _githubController = TextEditingController();
  final _renderController = TextEditingController();
  bool _isSaving = false;

  @override
  void dispose() {
    _githubController.dispose();
    _renderController.dispose();
    super.dispose();
  }

  Future<void> _saveCredentials() async {
    final authState = ref.read(authControllerProvider);
    if (authState.user?.isGuest ?? false) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Guest accounts cannot save cloud credentials. Please register or sign in.'),
        ),
      );
      return;
    }

    setState(() => _isSaving = true);
    final repo = ref.read(settingsRepositoryProvider);

    try {
      await repo.saveCredentials(
        githubToken: _githubController.text,
        renderApiKey: _renderController.text,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Credentials securely encrypted & persisted.'),
          duration: Duration(seconds: 2),
        ),
      );
    } catch (e) {
      // Previously any failure still reported success.
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Could not save credentials: $e'),
          backgroundColor: AppColors.statusErrorRed,
          duration: const Duration(seconds: 3),
        ),
      );
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authControllerProvider);
    final user = authState.user;
    final isGuest = user?.isGuest ?? false;
    return Scaffold(
      backgroundColor: AppColors.lightBackground,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.lg,
            vertical: AppSpacing.md,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Top Bar
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'WORKSPACE • CLOUD INFRASTRUCTURE',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: AppTextStyles.smallCapsLabel(
                            fontSize: 10,
                            color: AppColors.lightTextSecondary,
                            letterSpacing: 1.5,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          'Deployer Settings',
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
                    label: 'PIPELINE',
                    statusText: 'CONFIGURED',
                  ),
                ],
              ),

              const SizedBox(height: AppSpacing.xl),

              // Main Credentials Form Card
              SutraCard(
                padding: const EdgeInsets.all(AppSpacing.xl),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(
                          child: Text(
                            'ONE-CLICK DEPLOYER CREDENTIALS',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: AppTextStyles.smallCapsLabel(
                              fontSize: 10,
                              color: AppColors.gold,
                              letterSpacing: 1.5,
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
                            'ENCRYPTED',
                            style: AppTextStyles.smallCapsLabel(
                              fontSize: 9,
                              color: AppColors.goldDark,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    Text(
                      'Automated Cloud Dispatch',
                      style: AppTextStyles.serifHeading(
                        fontSize: 20,
                        color: AppColors.lightTextPrimary,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      'Connect your GitHub and Render infrastructure keys to enable autonomous repository creation and microservice deployments.',
                      style: AppTextStyles.bodyMedium(
                        color: AppColors.lightTextSecondary,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.xl),

                    // GitHub PAT Field
                    MaskedSecretField(
                      label: 'GitHub Personal Access Token (PAT)',
                      controller: _githubController,
                      hintText: 'ghp_••••••••••••••••••••',
                    ),
                    const SizedBox(height: AppSpacing.md),

                    // Render API Key Field
                    MaskedSecretField(
                      label: 'Render API Key',
                      controller: _renderController,
                      hintText: 'rnd_••••••••••••••••••••',
                    ),
                    const SizedBox(height: AppSpacing.xl),

                    // Save Button
                    SutraButton(
                      label: _isSaving ? 'SAVING CREDENTIALS...' : 'Save Credentials',
                      height: 46,
                      width: double.infinity,
                      variant: SutraButtonVariant.primaryBlack,
                      isLoading: _isSaving,
                      onPressed: isGuest ? null : _saveCredentials,
                      icon: const Icon(Icons.check, size: 16, color: Colors.white),
                    ),

                    if (isGuest) ...[
                      const SizedBox(height: AppSpacing.md),
                      Container(
                        padding: const EdgeInsets.all(AppSpacing.sm),
                        decoration: BoxDecoration(
                          color: AppColors.goldSubtle,
                          borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.lock_outline, size: 16, color: AppColors.gold),
                            const SizedBox(width: AppSpacing.sm),
                            Expanded(
                              child: Text(
                                'Saving deployment credentials is restricted in Guest mode. Sign in to link live repositories.',
                                style: AppTextStyles.bodySmall(
                                  color: AppColors.lightTextPrimary,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ],
                ),
              ),

              const SizedBox(height: AppSpacing.xl),

              // Info Panel 1: How to Generate Tokens
              SutraCard(
                padding: const EdgeInsets.all(AppSpacing.xl),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'GUIDE',
                      style: AppTextStyles.smallCapsLabel(
                        fontSize: 10,
                        color: AppColors.gold,
                        letterSpacing: 2.0,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      'How to Generate Tokens',
                      style: AppTextStyles.serifHeading(
                        fontSize: 18,
                        color: AppColors.lightTextPrimary,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.md),
                    _buildStepItem(
                      number: '1',
                      title: 'GitHub Personal Access Token (PAT)',
                      description:
                          'In GitHub, open Settings > Developer settings > Personal access tokens > Tokens (classic). Click "Generate new token" and grant the full `repo` and `workflow` scopes.',
                    ),
                    const SizedBox(height: AppSpacing.md),
                    _buildStepItem(
                      number: '2',
                      title: 'Render API Key',
                      description:
                          'In your Render dashboard, click your profile avatar > Account Settings > API Keys. Create an API key with write access to deploy services autonomously.',
                    ),
                  ],
                ),
              ),

              const SizedBox(height: AppSpacing.md),

              // Info Panel 2: How the Deployer Works
              SutraCard(
                padding: const EdgeInsets.all(AppSpacing.xl),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'ARCHITECTURE & WORKFLOW',
                      style: AppTextStyles.smallCapsLabel(
                        fontSize: 10,
                        color: AppColors.gold,
                        letterSpacing: 2.0,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      'How the Deployer Works',
                      style: AppTextStyles.serifHeading(
                        fontSize: 18,
                        color: AppColors.lightTextPrimary,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.md),
                    _buildWorkflowBullet(
                      icon: Icons.code,
                      title: 'Deterministic Code Synthesis',
                      description:
                          'The multi-agent swarm compiles the verified domain specification into a full-stack monorepo featuring FastAPI REST routes, SQLAlchemy schemas, and a responsive frontend.',
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    _buildWorkflowBullet(
                      icon: Icons.alt_route,
                      title: 'Automated Git Orchestration',
                      description:
                          'Sutra commits the compiled solution cleanly into your designated GitHub repository, writing complete Dockerfiles, CI workflows, and database migration scripts.',
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    _buildWorkflowBullet(
                      icon: Icons.cloud_done_outlined,
                      title: 'Zero-Downtime Render Service Dispatch',
                      description:
                          'Using your Render API key, Sutra triggers a managed web service build connected to PostgreSQL, provisioning your live URL within minutes.',
                    ),
                  ],
                ),
              ),

              const SizedBox(height: AppSpacing.xxl),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStepItem({
    required String number,
    required String title,
    required String description,
  }) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 24,
          height: 24,
          decoration: BoxDecoration(
            color: AppColors.blackButton,
            borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
          ),
          alignment: Alignment.center,
          child: Text(
            number,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 11,
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
                title,
                style: AppTextStyles.bodyMedium(
                  color: AppColors.lightTextPrimary,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                description,
                style: AppTextStyles.bodySmall(
                  color: AppColors.lightTextSecondary,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildWorkflowBullet({
    required IconData icon,
    required String title,
    required String description,
  }) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 18, color: AppColors.gold),
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
              const SizedBox(height: 2),
              Text(
                description,
                style: AppTextStyles.bodySmall(
                  color: AppColors.lightTextSecondary,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
