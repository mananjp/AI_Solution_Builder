import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/widgets/prompt_dialog.dart';
import '../../../core/widgets/sutra_button.dart';
import '../../../core/widgets/sutra_card.dart';
import '../../../core/widgets/voice_input_button.dart';
import '../../workspace/data/workspace_repository.dart';
import '../../workspace/domain/workspace_models.dart';
import '../../workspace/presentation/workspace_providers.dart';
import '../application/chat_controller.dart';

/// Conversational build screen: the web app's `/chat`.
///
/// Streams `agent_start`, `capability`, `build_progress`, `message`, `error`
/// and `complete` from `POST /api/v1/opencode/chat` and shows the phase
/// progress bar, an honest simulation warning when the engine has no LLM
/// credentials, and a build button that requests a real MVP build.
class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final _appNameController = TextEditingController();
  bool _buildRequested = true;
  bool _uploading = false;
  String? _attachment;

  /// Extracted text from the attached URL/document, sent as
  /// `uploaded_context` so the backend can actually use it.
  String? _attachmentContext;

  Timer? _elapsedTimer;
  DateTime? _streamingSince;

  @override
  void dispose() {
    _controller.dispose();
    _appNameController.dispose();
    _scrollController.dispose();
    _elapsedTimer?.cancel();
    super.dispose();
  }

  /// The web header shows a live elapsed-seconds counter next to the build
  /// progress zone, so a long build never looks frozen.
  void _syncElapsedTimer(bool streaming) {
    if (streaming && _streamingSince == null) {
      _streamingSince = DateTime.now();
      _elapsedTimer ??= Timer.periodic(const Duration(seconds: 1), (_) {
        if (mounted) setState(() {});
      });
    } else if (!streaming) {
      _streamingSince = null;
      _elapsedTimer?.cancel();
      _elapsedTimer = null;
    }
  }

  int get _elapsedSeconds => _streamingSince == null
      ? 0
      : DateTime.now().difference(_streamingSince!).inSeconds;

  @override
  Widget build(BuildContext context) {
    final chat = ref.watch(chatControllerProvider);
    _syncElapsedTimer(chat.isStreaming);

    ref.listen(chatControllerProvider, (previous, next) {
      if (next.transcript.length != previous?.transcript.length ||
          next.isStreaming != previous?.isStreaming) {
        _scrollToEnd();
      }
    });

    final solutionId =
        chat.solutionId ?? ref.watch(effectiveSolutionIdProvider);
    final buildsAsync =
        solutionId == null ? null : ref.watch(mvpBuildsProvider(solutionId));

    return Scaffold(
      backgroundColor: AppColors.lightBackground,
      appBar: AppBar(
        backgroundColor: AppColors.lightSurface,
        surfaceTintColor: Colors.transparent,
        title: Text('Build Chat', style: AppTextStyles.serifHeading(fontSize: 20)),
        actions: [
          if (chat.isStreaming)
            Padding(
              padding: const EdgeInsets.only(right: AppSpacing.sm),
              child: Center(
                child: Text(
                  _formatElapsed(_elapsedSeconds),
                  style: AppTextStyles.mono(
                    fontSize: 11,
                    color: AppColors.gold,
                  ),
                ),
              ),
            ),
          if (chat.isStreaming)
            IconButton(
              tooltip: 'Stop',
              onPressed: () =>
                  ref.read(chatControllerProvider.notifier).stop(),
              icon: const Icon(Icons.stop_circle_outlined),
            ),
        ],
      ),
      body: Column(
        children: [
          if (buildsAsync != null && buildsAsync.valueOrNull != null)
            _ArtifactsZone(
              builds: buildsAsync.valueOrNull!,
              solutionId: solutionId!,
            ),
          Expanded(
            child: chat.transcript.isEmpty
                ? _emptyState(chat)
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.all(AppSpacing.md),
                    itemCount: chat.transcript.length + 1,
                    itemBuilder: (context, index) {
                      if (index == chat.transcript.length) {
                        return Column(
                          children: [
                            if (chat.capability != null)
                              _CapabilityBanner(capability: chat.capability!),
                            if (chat.error != null)
                              _ErrorBanner(message: chat.error!),
                            if (chat.isStreaming || chat.progress.active)
                              _ProgressPanel(progress: chat.progress),
                          ],
                        );
                      }
                      return _MessageBubble(message: chat.transcript[index]);
                    },
                  ),
          ),
          _composer(chat),
        ],
      ),
    );
  }

  static String _formatElapsed(int seconds) {
    final m = (seconds ~/ 60).toString().padLeft(2, '0');
    final s = (seconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  Widget _emptyState(ChatState chat) {
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: [
        const SizedBox(height: AppSpacing.xxl),
        Icon(
          chat.capability?.simulation == true
              ? Icons.science_outlined
              : Icons.auto_awesome_outlined,
          size: 40,
          color: AppColors.gold,
        ),
        const SizedBox(height: AppSpacing.md),
        Center(
          child: Text(
            'Describe the app you want',
            style: AppTextStyles.serifHeading(fontSize: 20),
          ),
        ),
        const SizedBox(height: AppSpacing.xs),
        Center(
          child: Text(
            'The engine streams its plan and synthesizes the blueprint as it works.',
            textAlign: TextAlign.center,
            style: AppTextStyles.bodySmall(
              color: AppColors.lightTextSecondary,
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.lg),
        if (chat.capability != null)
          _CapabilityBanner(capability: chat.capability!),
      ],
    );
  }

  Widget _composer(ChatState chat) {
    return Container(
      padding: EdgeInsets.fromLTRB(
        AppSpacing.md,
        AppSpacing.sm,
        AppSpacing.md,
        AppSpacing.sm + MediaQuery.of(context).padding.bottom,
      ),
      decoration: const BoxDecoration(
        color: AppColors.lightSurface,
        border: Border(top: BorderSide(color: AppColors.lightBorder)),
      ),
      child: Column(
        children: [
          if (_attachment != null)
            Container(
              width: double.infinity,
              margin: const EdgeInsets.only(bottom: AppSpacing.xs),
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.sm,
                vertical: 5,
              ),
              decoration: BoxDecoration(
                color: AppColors.goldSubtle,
                borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                border: Border.all(color: AppColors.gold.withValues(alpha: 0.3)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.description_outlined,
                      size: 13, color: AppColors.gold),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      _attachment!,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppTextStyles.mono(
                        fontSize: 10,
                        color: AppColors.goldDark,
                      ),
                    ),
                  ),
                  GestureDetector(
                    onTap: () => setState(() {
                      _attachment = null;
                      _attachmentContext = null;
                    }),
                    child: const Icon(Icons.close, size: 13, color: AppColors.gold),
                  ),

                ],
              ),
            ),
          Row(
            children: [
              IconButton(
                tooltip: 'Attach context',
                onPressed: _uploading ? null : _attachContext,
                icon: const Icon(Icons.attach_file, size: 18),
                color: AppColors.lightTextSecondary,
              ),
              VoiceInputButton(
                disabled: chat.isStreaming || _uploading,
                onTranscribed: (text, lang) {
                  final cur = _controller.text.trim();
                  setState(() {
                    _controller.text = cur.isEmpty ? text : '$cur\n$text';
                  });
                },
              ),
              const SizedBox(width: AppSpacing.xs),
              Expanded(
                child: TextField(
                  controller: _controller,
                  enabled: !chat.isStreaming,
                  minLines: 1,
                  maxLines: 4,
                  textInputAction: TextInputAction.send,
                  onSubmitted: (_) => _send(),
                  decoration: const InputDecoration(
                    hintText: 'e.g. A clinic appointment booking app with reminders',
                    isDense: true,
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              SutraButton(
                label: chat.isStreaming ? '...' : 'Send',
                height: 42,
                width: 76,
                onPressed: chat.isStreaming ? null : _send,
              ),
            ],
          ),
          Row(
            children: [
              Checkbox(
                value: _buildRequested,
                onChanged: chat.isStreaming
                    ? null
                    : (v) => setState(() => _buildRequested = v ?? true),
                activeColor: AppColors.blackButton,
                visualDensity: VisualDensity.compact,
              ),
              // Flexible, or this label overflows on narrow phones.
              Expanded(
                child: Text(
                  _buildRequested
                      ? 'Will generate blueprint + build archive'
                      : 'Chat only (no build)',
                  style: AppTextStyles.bodySmall(
                    fontSize: 11,
                    color: AppColors.lightTextSecondary,
                  ),
                ),
              ),
            ],
          ),
          // The web composer only asks for a name once a build is requested,
          // because `app_name` is only read on the build path.
          if (_buildRequested) ...[
            const SizedBox(height: AppSpacing.xs),
            TextField(
              controller: _appNameController,
              enabled: !chat.isStreaming,
              style: AppTextStyles.mono(fontSize: 12),
              decoration: const InputDecoration(
                labelText: 'App name (optional)',
                isDense: true,
                prefixIcon: Icon(Icons.badge_outlined, size: 16),
              ),
            ),
          ],
        ],
      ),
    );
  }

  /// `POST /upload/url` or `POST /upload/document` — parsed and handed to the
  /// agent as context for the next turn.
  Future<void> _attachContext() async {
    final choice = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: AppColors.lightSurface,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.link, color: AppColors.gold),
              title: const Text('Share a URL'),
              onTap: () => Navigator.of(ctx).pop('url'),
            ),
            ListTile(
              leading: const Icon(Icons.note_add_outlined, color: AppColors.gold),
              title: const Text('Paste document text'),
              onTap: () => Navigator.of(ctx).pop('text'),
            ),
          ],
        ),
      ),
    );
    if (choice == null || !mounted) return;

    if (choice == 'url') {
      final url = await showPromptDialog(
        context: context,
        title: 'Share a URL',
        labelText: 'https://',
        confirmLabel: 'Attach',
        cancelLabel: 'Cancel',
      );
      if (url == null || url.isEmpty || !mounted) return;
      // Captured before the upload so the snackbar never touches a stale
      // context if the user leaves the screen mid-request.
      final messenger = ScaffoldMessenger.of(context);
      setState(() => _uploading = true);
      try {
        final result = await ref
            .read(workspaceRepositoryProvider)
            .uploadUrl(url);
        if (mounted) {
          setState(() {
            _attachment = url;
            _attachmentContext = _extractedText(result);
          });
        }
      } catch (e) {
        if (mounted) {
          _toast(messenger, 'Could not read that URL: $e', isError: true);
        }
      } finally {
        if (mounted) setState(() => _uploading = false);
      }
    } else {
      final text = await showPromptDialog(
        context: context,
        title: 'Document context',
        hintText: 'Paste requirements, notes or specs',
        confirmLabel: 'Attach',
        cancelLabel: 'Cancel',
        maxLines: 6,
      );
      if (text == null || text.isEmpty || !mounted) return;
      final messenger = ScaffoldMessenger.of(context);
      setState(() => _uploading = true);
      try {
        final result = await ref.read(workspaceRepositoryProvider).uploadDocument(
              filename: 'pasted-context.txt',
              bytes: utf8.encode(text),
            );
        if (mounted) {
          setState(() {
            _attachment = 'pasted-context.txt';
            // Prefer what the parser extracted, fall back to the raw paste.
            final parsed = _extractedText(result);
            _attachmentContext = parsed.isEmpty ? text : parsed;
          });
        }
      } catch (e) {

        if (mounted) {
          _toast(messenger, 'Upload failed: $e', isError: true);
        }

      } finally {
        if (mounted) setState(() => _uploading = false);
      }
    }
  }

  void _toast(ScaffoldMessengerState messenger, String message,
      {bool isError = false}) {
    messenger
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(message),
          backgroundColor: isError ? AppColors.statusErrorRed : null,
        ),
      );
  }

  /// The upload endpoints return the parsed body as `extracted_text`; the audio
  /// route uses `extracted_context`. The web client reads the same values.
  static String _extractedText(Map<String, dynamic> result) {
    final value = result['extracted_text'] ??
        result['extracted_context'] ??
        result['text'];
    return value is String ? value.trim() : '';
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    _controller.clear();
    _scrollToEnd();
    final context = _attachmentContext;
    await ref.read(chatControllerProvider.notifier).send(
          text,
          buildRequested: _buildRequested,
          appName: _appNameController.text.trim().isEmpty
              ? null
              : _appNameController.text.trim(),
          uploadedContext:
              (context == null || context.isEmpty) ? null : context,
        );
    _scrollToEnd();
  }


  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOut,
      );
    });
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.message});

  final ChatMessage message;

  @override
  Widget build(BuildContext context) {
    switch (message.role) {
      case ChatRole.user:
        return Align(
          alignment: Alignment.centerRight,
          child: Container(
            margin: const EdgeInsets.only(bottom: AppSpacing.sm),
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.md,
              vertical: AppSpacing.sm,
            ),
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.78,
            ),
            decoration: BoxDecoration(
              color: AppColors.blackButton,
              borderRadius: BorderRadius.circular(AppSpacing.radiusSm),
            ),
            child: Text(
              message.text,
              style: AppTextStyles.bodySmall(
                color: AppColors.blackButtonText,
              ),
            ),
          ),
        );

      case ChatRole.system:
        return Padding(
          padding: const EdgeInsets.only(bottom: AppSpacing.sm),
          child: Row(
            children: [
              const Icon(Icons.bolt_outlined, size: 14, color: AppColors.gold),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  message.text,
                style: AppTextStyles.bodySmall(
                  fontSize: 11,
                  color: AppColors.lightTextMuted,
                ).copyWith(fontStyle: FontStyle.italic),

                ),
              ),
            ],
          ),
        );

      case ChatRole.assistant:
        return Padding(
          padding: const EdgeInsets.only(bottom: AppSpacing.sm),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                margin: const EdgeInsets.only(top: 2),
                padding: const EdgeInsets.all(4),
                decoration: BoxDecoration(
                  color: AppColors.goldSubtle,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: const Icon(Icons.auto_awesome,
                    size: 12, color: AppColors.goldDark),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(AppSpacing.sm),
                  decoration: BoxDecoration(
                    color: AppColors.lightSurface,
                    borderRadius: BorderRadius.circular(AppSpacing.radiusSm),
                    border: Border.all(color: AppColors.lightBorder),
                  ),
                  child: SelectableText(
                    message.text,
                    style: AppTextStyles.bodySmall(
                      color: AppColors.lightTextPrimary,
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
    }
  }
}

class _ProgressPanel extends StatelessWidget {
  const _ProgressPanel({required this.progress});

  final BuildProgress progress;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: SutraCard(
        padding: const EdgeInsets.all(AppSpacing.sm),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    (progress.phase ?? 'working').toUpperCase(),
                    style: AppTextStyles.smallCapsLabel(
                      fontSize: 9,
                      color: AppColors.gold,
                      letterSpacing: 1.4,
                    ),
                  ),
                ),
                if (progress.totalSteps != null)
                  Text(
                    '${progress.step ?? 0}/${progress.totalSteps}',
                    style: AppTextStyles.mono(
                      fontSize: 10,
                      color: AppColors.lightTextMuted,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 6),
            ClipRRect(
              borderRadius: BorderRadius.circular(3),
              child: LinearProgressIndicator(
                value: progress.active ? progress.fraction : null,
                minHeight: 5,
                backgroundColor: AppColors.lightSurfaceSubtle,
                valueColor: const AlwaysStoppedAnimation(AppColors.gold),
              ),
            ),
            if (progress.message != null) ...[
              const SizedBox(height: 6),
              Text(
                progress.message!,
                style: AppTextStyles.bodySmall(
                  fontSize: 11,
                  color: AppColors.lightTextSecondary,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _CapabilityBanner extends StatelessWidget {
  const _CapabilityBanner({required this.capability});

  final ChatCapability capability;

  @override
  Widget build(BuildContext context) {
    if (!capability.simulation) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.sm),
        decoration: BoxDecoration(
          color: AppColors.goldSubtle,
          borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
          border: Border.all(color: AppColors.gold.withValues(alpha: 0.4)),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.warning_amber_rounded,
                size: 16, color: AppColors.goldDark),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                'Simulation mode: the engine has no LLM credentials configured '
                '(provider=${capability.llmProvider ?? 'unknown'}). Output is '
                'template-generated, not model-written.',
                style: AppTextStyles.bodySmall(
                  fontSize: 11,
                  color: AppColors.goldDark,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.sm),
        decoration: BoxDecoration(
          color: AppColors.statusErrorRed.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.error_outline,
                size: 16, color: AppColors.statusErrorRed),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                message,
                style: AppTextStyles.bodySmall(
                  fontSize: 11,
                  color: AppColors.statusErrorRed,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Zone 3 of the web chat page: the builds produced in this session, tappable
/// through to the blueprint or the sandbox.
class _ArtifactsZone extends StatelessWidget {
  const _ArtifactsZone({required this.builds, required this.solutionId});

  final List<MVPBuildModel> builds;
  final String solutionId;

  @override
  Widget build(BuildContext context) {
    if (builds.isEmpty) return const SizedBox.shrink();
    final recent = builds.take(3).toList();
    return Container(
      width: double.infinity,
      color: AppColors.lightSurfaceSubtle,
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.md,
        AppSpacing.sm,
        AppSpacing.md,
        AppSpacing.sm,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                'BUILD ARTIFACTS',
                style: AppTextStyles.smallCapsLabel(
                  fontSize: 9,
                  color: AppColors.lightTextMuted,
                ),
              ),
              const Spacer(),
              GestureDetector(
                onTap: () => context.go('/builds'),
                child: Text(
                  'BLUEPRINT',
                  style: AppTextStyles.smallCapsLabel(
                    fontSize: 9,
                    color: AppColors.gold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 5),
          SizedBox(
            height: 34,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: recent.length,
              separatorBuilder: (_, __) => const SizedBox(width: 6),
              itemBuilder: (context, i) {
                final b = recent[i];
                final done = !isBuildInFlight(b);
                return GestureDetector(
                  onTap: done
                      ? () => context.go(
                            '/sandbox?build=${Uri.encodeComponent(b.buildId)}',
                          )
                      : null,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 9,
                      vertical: 5,
                    ),
                    decoration: BoxDecoration(
                      color: AppColors.lightSurface,
                      borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                      border: Border.all(color: AppColors.lightBorder),
                    ),
                    child: Row(
                      children: [
                        Text(
                          '#${b.buildNumber}',
                          style: AppTextStyles.mono(
                            fontSize: 10,
                            color: done
                                ? AppColors.lightTextPrimary
                                : AppColors.gold,
                          ),
                        ),
                        const SizedBox(width: 6),
                        Text(
                          b.statusLabel,
                          style: AppTextStyles.smallCapsLabel(
                            fontSize: 8,
                            color: b.isFailed
                                ? AppColors.statusErrorRed
                                : done
                                    ? AppColors.statusLiveGreen
                                    : AppColors.gold,
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}