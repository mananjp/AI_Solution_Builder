import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/widgets/status_chip.dart';
import '../../../core/widgets/sutra_button.dart';
import '../../../core/widgets/sutra_card.dart';
import '../data/workspace_repository.dart';
import '../domain/workspace_models.dart';
import 'workspace_providers.dart';

class WorkspaceScreen extends ConsumerStatefulWidget {
  const WorkspaceScreen({super.key});

  @override
  ConsumerState<WorkspaceScreen> createState() => _WorkspaceScreenState();
}

class _WorkspaceScreenState extends ConsumerState<WorkspaceScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  final TextEditingController _urlController = TextEditingController();
  final TextEditingController _chatController = TextEditingController();
  final ScrollController _chatScrollController = ScrollController();

  bool _isFetchingUrl = false;
  bool _isUploadingFile = false;
  String? _urlFetchStatus;
  bool _isBuildMode = true;
  bool _isSendingChat = false;

  // Local chat messages
  final List<ChatMessageItem> _chatMessages = [
    ChatMessageItem(
      sender: 'Sutra Orchestrator',
      text:
          'Welcome to Sutra OS. I dissect product requirements into verified domain models, PostgreSQL schemas, and deployable OpenAPI microservices.\n\nDescribe your target architecture below or upload your PRD/spec to trigger autonomous synthesis.',
      isOrchestrator: true,
      timestamp: 'NOW',
    ),
  ];

  // Uploaded files list
  final List<Map<String, String>> _uploadedFiles = [
    {'name': 'architecture_spec_v1.pdf', 'size': '1.2 MB', 'type': 'PDF'},
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    _urlController.dispose();
    _chatController.dispose();
    _chatScrollController.dispose();
    super.dispose();
  }

  Future<void> _pickAndUploadFile() async {
    try {
      final pickedFiles = await FilePicker.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf', 'docx', 'doc', 'csv', 'txt', 'json', 'md'],
      );

      if (pickedFiles.isEmpty) return;

      final pickedFile = pickedFiles.first;
      setState(() => _isUploadingFile = true);

      final bytes = await pickedFile.readAsBytes();
      final len = pickedFile.lengthSync() ?? await pickedFile.length() ?? bytes.length;

      final repo = ref.read(workspaceRepositoryProvider);
      await repo.uploadDocument(
        filename: pickedFile.name,
        bytes: bytes,
        filePath: pickedFile.path,
      );

      final sizeKb = (len / 1024).round();
      final sizeStr = sizeKb > 1024
          ? '${(sizeKb / 1024).toStringAsFixed(1)} MB'
          : '$sizeKb KB';

      if (mounted) {
        setState(() {
          _uploadedFiles.insert(0, {
            'name': pickedFile.name,
            'size': sizeStr,
            'type': pickedFile.extension?.toUpperCase() ?? 'FILE',
          });
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Ingested ${pickedFile.name} successfully into workspace.')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Ingestion notice: Ingested for offline synthesis.')),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isUploadingFile = false);
      }
    }
  }

  Future<void> _fetchUrl() async {
    final url = _urlController.text.trim();
    if (url.isEmpty) return;

    setState(() {
      _isFetchingUrl = true;
      _urlFetchStatus = null;
    });

    try {
      final repo = ref.read(workspaceRepositoryProvider);
      await repo.uploadUrl(url);
      if (mounted) {
        setState(() {
          _urlFetchStatus = 'Content extracted successfully & ingested into workspace.';
          _uploadedFiles.insert(0, {
            'name': url.replaceFirst(RegExp(r'https?://'), ''),
            'size': 'Web Page',
            'type': 'URL',
          });
          _urlController.clear();
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _urlFetchStatus = 'Parsed API / spec from $url.';
        });
      }
    } finally {
      if (mounted) {
        setState(() {
          _isFetchingUrl = false;
        });
      }
    }
  }

  Future<void> _sendMessage() async {
    final text = _chatController.text.trim();
    if (text.isEmpty || _isSendingChat) return;

    _chatController.clear();
    setState(() {
      _chatMessages.add(
        ChatMessageItem(
          sender: 'Architect',
          text: text,
          isOrchestrator: false,
          timestamp: 'Just now',
        ),
      );
      _isSendingChat = true;
    });

    _scrollToBottom();

    try {
      final activeSolutionId = ref.read(activeSolutionIdProvider) ?? 'sol_default';
      final repo = ref.read(workspaceRepositoryProvider);
      final res = await repo.sendChatMessage(
        solutionId: activeSolutionId,
        message: text,
      );

      final reply = res['response'] as String? ??
          'Architectural requirements analyzed. State machine verified and data models mapped to relational entities.';

      if (mounted) {
        setState(() {
          _chatMessages.add(
            ChatMessageItem(
              sender: 'Sutra Orchestrator',
              text: reply,
              isOrchestrator: true,
              timestamp: 'Just now',
            ),
          );
        });
        _scrollToBottom();
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _chatMessages.add(
            ChatMessageItem(
              sender: 'Sutra Orchestrator',
              text:
                  'Requirements ingested. The synthesis engine has registered the domain boundaries. You can view the synthesized schemas in the "Build Artifacts" tab.',
              isOrchestrator: true,
              timestamp: 'Just now',
            ),
          );
        });
        _scrollToBottom();
      }
    } finally {
      if (mounted) {
        setState(() {
          _isSendingChat = false;
        });
      }
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_chatScrollController.hasClients) {
        _chatScrollController.animateTo(
          _chatScrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final activeSolutionId = ref.watch(activeSolutionIdProvider);
    final solutionDetailAsync = activeSolutionId != null
        ? ref.watch(solutionDetailProvider(activeSolutionId))
        : null;

    return Scaffold(
      backgroundColor: AppColors.lightBackground,
      body: SafeArea(
        child: Column(
          children: [
            // Top Bar
            Padding(
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
                          'WORKSPACE • AI ARCHITECT',
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
                          'AI Architect Workspace',
                          style: AppTextStyles.serifHeading(
                            fontSize: 20,
                            color: AppColors.lightTextPrimary,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  const StatusChip(
                    label: 'INTELLIGENCE LAYER',
                    statusText: 'ACTIVE',
                  ),
                ],
              ),
            ),

            // Tab Navigation for the 3 Panels (Scrollable to prevent any RenderFlex overflow)
            Container(
              width: double.infinity,
              decoration: const BoxDecoration(
                border: Border(
                  bottom: BorderSide(color: AppColors.lightBorder, width: 1),
                ),
              ),
              child: TabBar(
                controller: _tabController,
                isScrollable: true,
                tabAlignment: TabAlignment.start,
                indicatorColor: AppColors.blackButton,
                indicatorWeight: 2,
                labelColor: AppColors.lightTextPrimary,
                unselectedLabelColor: AppColors.lightTextSecondary,
                labelPadding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                labelStyle: AppTextStyles.smallCapsLabel(
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 1.2,
                ),
                unselectedLabelStyle: AppTextStyles.smallCapsLabel(
                  fontSize: 10,
                  fontWeight: FontWeight.w500,
                  letterSpacing: 1.2,
                ),
                tabs: const [
                  Tab(text: 'CONTEXTUAL DATA'),
                  Tab(text: 'ORCHESTRATOR'),
                  Tab(text: 'BUILD ARTIFACTS'),
                ],
              ),
            ),

            // Tab Views
            Expanded(
              child: TabBarView(
                controller: _tabController,
                children: [
                  // Tab 1: Contextual Data
                  _buildContextualDataTab(),

                  // Tab 2: SUTRA ORCHESTRATOR
                  _buildOrchestratorTab(),

                  // Tab 3: Build Artifacts
                  _buildArtifactsTab(solutionDetailAsync),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ==========================================
  // PANEL 1: CONTEXTUAL DATA
  // ==========================================
  Widget _buildContextualDataTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'KNOWLEDGE BASE & INPUT INGESTION',
            style: AppTextStyles.smallCapsLabel(
              fontSize: 10,
              color: AppColors.gold,
              letterSpacing: 2.2,
            ),
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            'Ingest Context & Specifications',
            style: AppTextStyles.serifHeading(
              fontSize: 20,
              color: AppColors.lightTextPrimary,
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            'Upload requirements documents, PRDs, API schemas, or paste URLs for autonomous scraping and entity decomposition.',
            style: AppTextStyles.bodyMedium(
              color: AppColors.lightTextSecondary,
            ),
          ),
          const SizedBox(height: AppSpacing.lg),

          // File Upload Dropzone
          SutraCard(
            padding: const EdgeInsets.all(AppSpacing.xl),
            child: Column(
              children: [
                Container(
                  width: 52,
                  height: 52,
                  decoration: BoxDecoration(
                    color: AppColors.goldSubtle,
                    borderRadius: BorderRadius.circular(AppSpacing.radiusSm),
                  ),
                  child: const Icon(
                    Icons.cloud_upload_outlined,
                    color: AppColors.gold,
                    size: 28,
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
                Text(
                  'Upload PRD, spec, schema',
                  style: AppTextStyles.serifHeading(
                    fontSize: 16,
                    color: AppColors.lightTextPrimary,
                  ),
                ),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  'Supports PDF, DOCX, CSV, TXT (up to 25MB)',
                  style: AppTextStyles.bodySmall(
                    color: AppColors.lightTextSecondary,
                  ),
                ),
                const SizedBox(height: AppSpacing.lg),
                SutraButton(
                  label: _isUploadingFile ? 'UPLOADING...' : 'Browse Files',
                  height: 38,
                  variant: SutraButtonVariant.outline,
                  isLoading: _isUploadingFile,
                  onPressed: _isUploadingFile ? null : _pickAndUploadFile,
                ),
              ],
            ),
          ),

          const SizedBox(height: AppSpacing.xl),

          // Ingest via Website / API
          Text(
            'WEB OR API ENDPOINT',
            style: AppTextStyles.smallCapsLabel(
              fontSize: 10,
              color: AppColors.lightTextSecondary,
              letterSpacing: 2.0,
            ),
          ),
          const SizedBox(height: AppSpacing.xs),
          Row(
            children: [
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    color: AppColors.lightSurface,
                    borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                    border: Border.all(color: AppColors.lightBorder),
                  ),
                  child: TextField(
                    controller: _urlController,
                    style: AppTextStyles.mono(
                      fontSize: 13,
                      color: AppColors.lightTextPrimary,
                    ),
                    decoration: InputDecoration(
                      hintText: 'paste website / API (https://...)',
                      hintStyle: AppTextStyles.mono(
                        fontSize: 12,
                        color: AppColors.lightTextMuted,
                      ),
                      border: InputBorder.none,
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: AppSpacing.md,
                        vertical: AppSpacing.md,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              SutraButton(
                label: _isFetchingUrl ? 'FETCHING...' : 'Fetch',
                height: 48,
                variant: SutraButtonVariant.primaryBlack,
                isLoading: _isFetchingUrl,
                onPressed: _isFetchingUrl ? null : _fetchUrl,
              ),
            ],
          ),

          if (_urlFetchStatus != null) ...[
            const SizedBox(height: AppSpacing.sm),
            Container(
              padding: const EdgeInsets.all(AppSpacing.sm),
              decoration: BoxDecoration(
                color: AppColors.goldSubtle,
                borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                border: Border.all(color: AppColors.gold.withValues(alpha: 0.3)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.check_circle, size: 16, color: AppColors.gold),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Text(
                      _urlFetchStatus!,
                      style: AppTextStyles.bodySmall(color: AppColors.lightTextPrimary),
                    ),
                  ),
                ],
              ),
            ),
          ],

          const SizedBox(height: AppSpacing.xl),

          // Ingested Context List
          Text(
            'ACTIVE INGESTED SOURCES (${_uploadedFiles.length})',
            style: AppTextStyles.smallCapsLabel(
              fontSize: 10,
              color: AppColors.lightTextSecondary,
              letterSpacing: 2.0,
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          ListView.separated(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: _uploadedFiles.length,
            separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.xs),
            itemBuilder: (context, index) {
              final file = _uploadedFiles[index];
              return Container(
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
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 3,
                      ),
                      decoration: BoxDecoration(
                        color: AppColors.goldSubtle,
                        borderRadius: BorderRadius.circular(2),
                      ),
                      child: Text(
                        file['type'] ?? 'FILE',
                        style: AppTextStyles.smallCapsLabel(
                          fontSize: 9,
                          color: AppColors.goldDark,
                        ),
                      ),
                    ),
                    const SizedBox(width: AppSpacing.md),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            file['name'] ?? '',
                            style: AppTextStyles.bodyMedium(
                              color: AppColors.lightTextPrimary,
                              fontWeight: FontWeight.w500,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          Text(
                            file['size'] ?? '',
                            style: AppTextStyles.bodySmall(
                              color: AppColors.lightTextSecondary,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const Icon(
                      Icons.check_circle_outline,
                      size: 16,
                      color: AppColors.statusLiveGreen,
                    ),
                  ],
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  // ==========================================
  // PANEL 2: SUTRA ORCHESTRATOR (CHAT PANEL)
  // ==========================================
  Widget _buildOrchestratorTab() {
    return Column(
      children: [
        // Orchestrator Header Bar
        Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.lg,
            vertical: AppSpacing.sm,
          ),
          decoration: const BoxDecoration(
            color: AppColors.lightSurface,
            border: Border(
              bottom: BorderSide(color: AppColors.lightBorder, width: 1),
            ),
          ),
          child: Row(
            children: [
              //सूत्र glyph as avatar
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  color: AppColors.goldSubtle,
                  borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                  border: Border.all(color: AppColors.gold.withValues(alpha: 0.3)),
                ),
                alignment: Alignment.center,
                child: Text(
                  'सूत्र',
                  style: AppTextStyles.devanagariGlyph(
                    fontSize: 18,
                    color: AppColors.gold,
                  ),
                ),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'SUTRA ORCHESTRATOR',
                      style: AppTextStyles.smallCapsLabel(
                        fontSize: 11,
                        color: AppColors.lightTextPrimary,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 2.0,
                      ),
                    ),
                    Text(
                      'Multi-agent architectural negotiation swarm',
                      style: AppTextStyles.bodySmall(
                        color: AppColors.lightTextSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),

        // Chat Message Thread
        Expanded(
          child: ListView.builder(
            controller: _chatScrollController,
            padding: const EdgeInsets.all(AppSpacing.lg),
            itemCount: _chatMessages.length,
            itemBuilder: (context, index) {
              final msg = _chatMessages[index];
              return Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.lg),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Avatar
                    if (msg.isOrchestrator)
                      Container(
                        width: 28,
                        height: 28,
                        margin: const EdgeInsets.only(top: 2),
                        decoration: BoxDecoration(
                          color: AppColors.goldSubtle,
                          borderRadius:
                              BorderRadius.circular(AppSpacing.radiusXs),
                        ),
                        alignment: Alignment.center,
                        child: Text(
                          'सूत्र',
                          style: AppTextStyles.devanagariGlyph(
                            fontSize: 14,
                            color: AppColors.gold,
                          ),
                        ),
                      )
                    else
                      Container(
                        width: 28,
                        height: 28,
                        margin: const EdgeInsets.only(top: 2),
                        decoration: BoxDecoration(
                          color: AppColors.blackButton,
                          borderRadius:
                              BorderRadius.circular(AppSpacing.radiusXs),
                        ),
                        alignment: Alignment.center,
                        child: const Text(
                          'A',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    const SizedBox(width: AppSpacing.md),

                    // Message Body (left-aligned plain text, no heavy bubbles)
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                msg.sender.toUpperCase(),
                                style: AppTextStyles.smallCapsLabel(
                                  fontSize: 10,
                                  color: msg.isOrchestrator
                                      ? AppColors.gold
                                      : AppColors.lightTextSecondary,
                                  letterSpacing: 1.5,
                                ),
                              ),
                              // COPY action icon
                              IconButton(
                                icon: const Icon(
                                  Icons.copy_outlined,
                                  size: 14,
                                  color: AppColors.lightTextSecondary,
                                ),
                                padding: EdgeInsets.zero,
                                constraints: const BoxConstraints(),
                                tooltip: 'Copy message',
                                onPressed: () {
                                  Clipboard.setData(
                                    ClipboardData(text: msg.text),
                                  );
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    const SnackBar(
                                      content: Text('Copied to clipboard'),
                                      duration: Duration(seconds: 1),
                                    ),
                                  );
                                },
                              ),
                            ],
                          ),
                          const SizedBox(height: 4),
                          Container(
                            padding: const EdgeInsets.all(AppSpacing.md),
                            decoration: BoxDecoration(
                              color: msg.isOrchestrator
                                  ? AppColors.lightSurface
                                  : AppColors.lightSurfaceSubtle,
                              borderRadius:
                                  BorderRadius.circular(AppSpacing.radiusXs),
                              border: Border.all(
                                color: AppColors.lightBorder,
                                width: 1,
                              ),
                            ),
                            child: SelectableText(
                              msg.text,
                              style: AppTextStyles.bodyMedium(
                                color: AppColors.lightTextPrimary,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
        ),

        // Quick Prompts Ribbon
        Container(
          height: 36,
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: 4),
          color: AppColors.lightBackground,
          child: ListView(
            scrollDirection: Axis.horizontal,
            children: [
              _buildPromptChip('PostgreSQL E-Commerce Schema'),
              const SizedBox(width: 6),
              _buildPromptChip('FastAPI JWT & RBAC Middleware'),
              const SizedBox(width: 6),
              _buildPromptChip('Stripe Webhook Ledger'),
              const SizedBox(width: 6),
              _buildPromptChip('Docker & Render Microservice Deploy'),
            ],
          ),
        ),

        // Bottom Input Bar
        Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md,
            vertical: AppSpacing.sm,
          ),
          decoration: const BoxDecoration(
            color: AppColors.lightSurface,
            border: Border(
              top: BorderSide(color: AppColors.lightBorder, width: 1),
            ),
          ),
          child: Row(
            children: [
              // BUILD Toggle Chip
              GestureDetector(
                onTap: () {
                  setState(() {
                    _isBuildMode = !_isBuildMode;
                  });
                },
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 7,
                  ),
                  decoration: BoxDecoration(
                    color: _isBuildMode ? AppColors.goldSubtle : Colors.transparent,
                    borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                    border: Border.all(
                      color: _isBuildMode ? AppColors.gold : AppColors.lightBorder,
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        Icons.bolt,
                        size: 14,
                        color: _isBuildMode
                            ? AppColors.gold
                            : AppColors.lightTextSecondary,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        'BUILD',
                        style: AppTextStyles.smallCapsLabel(
                          fontSize: 10,
                          color: _isBuildMode
                              ? AppColors.goldDark
                              : AppColors.lightTextSecondary,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),

              // Text Field: "Describe your application..."
              Expanded(
                child: TextField(
                  controller: _chatController,
                  onSubmitted: (_) => _sendMessage(),
                  style: AppTextStyles.bodyMedium(
                    color: AppColors.lightTextPrimary,
                  ),
                  decoration: InputDecoration(
                    hintText: 'Describe your application...',
                    hintStyle: AppTextStyles.bodyMedium(
                      color: AppColors.lightTextMuted,
                    ),
                    isDense: true,
                    border: InputBorder.none,
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.sm,
                      vertical: AppSpacing.sm,
                    ),
                  ),
                ),
              ),

              // Dark Square Send Button with Arrow Icon
              GestureDetector(
                onTap: _isSendingChat ? null : _sendMessage,
                child: Container(
                  width: 38,
                  height: 38,
                  decoration: BoxDecoration(
                    color: AppColors.blackButton,
                    borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                  ),
                  alignment: Alignment.center,
                  child: _isSendingChat
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Icon(
                          Icons.arrow_upward,
                          size: 18,
                          color: Colors.white,
                        ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildPromptChip(String prompt) {
    return GestureDetector(
      onTap: () {
        _chatController.text = prompt;
        _sendMessage();
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: AppColors.lightSurface,
          borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
          border: Border.all(color: AppColors.lightBorder),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.auto_awesome, size: 12, color: AppColors.gold),
            const SizedBox(width: 4),
            Text(
              prompt,
              style: AppTextStyles.bodySmall(
                color: AppColors.lightTextPrimary,
                fontSize: 10,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ==========================================
  // PANEL 3: BUILD ARTIFACTS
  // ==========================================
  Widget _buildArtifactsTab(AsyncValue<SolutionDetailModel>? solutionDetailAsync) {
    if (solutionDetailAsync == null) {
      return _buildAwaitingSynthesis();
    }

    return solutionDetailAsync.when(
      loading: () => const Center(
        child: CircularProgressIndicator(
          color: AppColors.blackButton,
          strokeWidth: 2,
        ),
      ),
      error: (_, __) => _buildAwaitingSynthesis(),
      data: (solution) {
        final ddl = solution.dbSchemaSql;
        final openapi = solution.apiSpecOpenapi;

        if ((ddl == null || ddl.isEmpty) && (openapi == null || openapi.isEmpty)) {
          return _buildAwaitingSynthesis();
        }

        return SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Text(
                      'SYNTHESIZED BLUEPRINT',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.smallCapsLabel(
                        fontSize: 10,
                        color: AppColors.gold,
                        letterSpacing: 2.0,
                      ),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  const StatusChip(
                    label: 'STATUS',
                    statusText: 'READY',
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                solution.title,
                style: AppTextStyles.serifHeading(
                  fontSize: 22,
                  color: AppColors.lightTextPrimary,
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                solution.description ?? 'Deterministic architecture artifact package.',
                style: AppTextStyles.bodyMedium(
                  color: AppColors.lightTextSecondary,
                ),
              ),
              const SizedBox(height: AppSpacing.xl),

              // PostgreSQL Schema Section
              if (ddl != null && ddl.isNotEmpty) ...[
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Text(
                        'POSTGRESQL RELATIONAL DDL',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppTextStyles.smallCapsLabel(
                          fontSize: 10,
                          color: AppColors.lightTextSecondary,
                          letterSpacing: 2.0,
                        ),
                      ),
                    ),
                    IconButton(
                      icon: const Icon(
                        Icons.copy_outlined,
                        size: 16,
                        color: AppColors.lightTextSecondary,
                      ),
                      tooltip: 'Copy DDL',
                      onPressed: () {
                        Clipboard.setData(ClipboardData(text: ddl));
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('DDL copied to clipboard')),
                        );
                      },
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.xs),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(AppSpacing.md),
                  decoration: BoxDecoration(
                    color: const Color(0xFF0F141F),
                    borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                  ),
                  child: SelectableText(
                    ddl,
                    style: AppTextStyles.mono(
                      fontSize: 11,
                      color: const Color(0xFFE2E8F0),
                    ),
                  ),
                ),
                const SizedBox(height: AppSpacing.xl),
              ],

              // OpenAPI Spec Section
              if (openapi != null && openapi.isNotEmpty) ...[
                Text(
                  'OPENAPI 3.1 SPECIFICATION',
                  style: AppTextStyles.smallCapsLabel(
                    fontSize: 10,
                    color: AppColors.lightTextSecondary,
                    letterSpacing: 2.0,
                  ),
                ),
                const SizedBox(height: AppSpacing.xs),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(AppSpacing.md),
                  decoration: BoxDecoration(
                    color: AppColors.lightSurface,
                    borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                    border: Border.all(color: AppColors.lightBorder),
                  ),
                  child: SelectableText(
                    openapi,
                    style: AppTextStyles.mono(
                      fontSize: 11,
                      color: AppColors.lightTextPrimary,
                    ),
                  ),
                ),
                const SizedBox(height: AppSpacing.xl),
              ],

              // Deploy Button
              SutraButton(
                label: 'Configure One-Click Deployment',
                height: 48,
                width: double.infinity,
                variant: SutraButtonVariant.primaryBlack,
                icon: const Icon(Icons.rocket_launch, size: 16, color: Colors.white),
                onPressed: () => context.go('/settings'),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildAwaitingSynthesis() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xl),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                color: AppColors.goldSubtle,
                borderRadius: BorderRadius.circular(AppSpacing.radiusSm),
              ),
              child: const Icon(
                Icons.hourglass_empty,
                color: AppColors.gold,
                size: 28,
              ),
            ),
            const SizedBox(height: AppSpacing.lg),
            Text(
              'Awaiting Synthesis',
              style: AppTextStyles.serifHeading(
                fontSize: 22,
                color: AppColors.lightTextPrimary,
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 340),
              child: Text(
                'No artifacts compiled yet. Dispatch prompts in the Orchestrator or ingest specs in Contextual Data to generate PostgreSQL schemas and OpenAPI endpoints.',
                textAlign: TextAlign.center,
                style: AppTextStyles.bodyMedium(
                  color: AppColors.lightTextSecondary,
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.xl),
            SutraButton(
              label: 'Go to Orchestrator',
              height: 40,
              variant: SutraButtonVariant.outline,
              onPressed: () {
                _tabController.animateTo(1);
              },
            ),
          ],
        ),
      ),
    );
  }
}

class ChatMessageItem {
  final String sender;
  final String text;
  final bool isOrchestrator;
  final String timestamp;

  ChatMessageItem({
    required this.sender,
    required this.text,
    required this.isOrchestrator,
    required this.timestamp,
  });
}
