import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../../../core/network/api_endpoints.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/utils/file_delivery.dart';
import '../data/workspace_repository.dart';
import '../domain/workspace_models.dart';
import 'workspace_providers.dart';

/// Build sandbox: browse the generated file tree, read a file's contents, and
/// open the running app in an embedded WebView.
///
/// The backend exposes `GET /mvp/builds/{id}/files/{path}` plus a `files[]`
/// list on the build payload, and `GET /mvp/builds/{id}/preview` which serves
/// the preview HTML. The Flutter app had no equivalent of the web app's
/// `/sandbox` route at all.
class SandboxScreen extends ConsumerStatefulWidget {
  const SandboxScreen({super.key});

  @override
  ConsumerState<SandboxScreen> createState() => _SandboxScreenState();
}

class _SandboxScreenState extends ConsumerState<SandboxScreen> {
  String? _buildId;
  bool _loadingFile = false;
  bool _readQueryArg = false;
  bool _downloading = false;
  bool _editing = false;
  PreviewDevice _device = PreviewDevice.desktop;
  String? _openFilePath;
  final _editorInput = TextEditingController();
  List<_EditorEntry> _editorLog = const [];

  /// Held across rebuilds on purpose. `buildStatusProvider` polls every few
  /// seconds, and a controller created inside build() would reload the preview
  /// page on every tick and leak a platform view each time.
  WebViewController? _preview;
  String? _previewUrl;
  String? _previewBuildId;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Arrives as `/sandbox?build=<buildId>`. This has to be
    // `didChangeDependencies`, not `initState`: GoRouterState is an inherited
    // widget and cannot be depended on before initState completes.
    if (_readQueryArg) return;
    _readQueryArg = true;
    final arg = GoRouterState.of(context).uri.queryParameters['build'];
    if (arg != null && arg.isNotEmpty) {
      _buildId = arg;
    }
  }

  @override
  void dispose() {
    // Dropping the reference releases the underlying platform view.
    _preview = null;
    _editorInput.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final buildId = _buildId;
    final buildsAsync = ref.watch(mvpBuildsProvider(
      ref.watch(effectiveSolutionIdProvider) ?? '',
    ));

    return DefaultTabController(
      length: 3,
      child: Scaffold(
        backgroundColor: AppColors.lightBackground,
        appBar: AppBar(
          backgroundColor: AppColors.lightSurface,
          surfaceTintColor: Colors.transparent,
          title: Text('Sandbox', style: AppTextStyles.serifHeading(fontSize: 20)),
          bottom: const TabBar(
            labelColor: AppColors.blackButton,
            unselectedLabelColor: AppColors.lightTextSecondary,
            indicatorColor: AppColors.gold,
            tabs: [
              Tab(text: 'FILES'),
              Tab(text: 'PREVIEW'),
              Tab(text: 'AI EDITOR'),
            ],
          ),
        ),
        body: buildId == null
            ? _buildPicker(buildsAsync)
            : TabBarView(
                children: [
                  _filesTab(buildId, buildsAsync),
                  _previewTab(buildId),
                  _aiEditorTab(buildId, buildsAsync),
                ],
              ),
      ),
    );
  }

  Widget _buildPicker(AsyncValue<List<MVPBuildModel>> buildsAsync) {
    return buildsAsync.when(
      loading: () =>
          const Center(child: CircularProgressIndicator(color: AppColors.gold)),
      error: (e, _) => Center(
        child: Text(
          '$e',
          style: AppTextStyles.bodySmall(color: AppColors.statusErrorRed),
        ),
      ),
      data: (builds) {
        final done = builds.where((b) => !isBuildInFlight(b)).toList();
        if (done.isEmpty) {
          return Center(
            child: Text(
              'No finished builds to inspect yet.',
              style: AppTextStyles.bodySmall(
                color: AppColors.lightTextSecondary,
              ),
            ),
          );
        }
        return ListView.builder(
          padding: const EdgeInsets.all(AppSpacing.md),
          itemCount: done.length,
          itemBuilder: (context, i) => ListTile(
            title: Text('Build #${done[i].buildNumber}'),
            subtitle: Text('${done[i].fileCount} files'),
            onTap: () => setState(() => _buildId = done[i].buildId),
          ),
        );
      },
    );
  }

  Widget _filesTab(String buildId, AsyncValue<List<MVPBuildModel>> buildsAsync) {
    return buildsAsync.maybeWhen(
      data: (builds) {
        if (builds.isEmpty) {
          return _sandboxMessage('This workspace has no builds yet.');
        }
        final matches =
            builds.where((b) => b.buildId == buildId).toList();
        final build = matches.isNotEmpty ? matches.first : builds.first;
        if (build.files.isEmpty) {
          return _sandboxMessage('This build reported no files.');
        }
        return Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.md,
                AppSpacing.sm,
                AppSpacing.md,
                0,
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      '${build.files.length} FILES',
                      style: AppTextStyles.smallCapsLabel(
                        fontSize: 9,
                        color: AppColors.lightTextMuted,
                      ),
                    ),
                  ),
                  TextButton.icon(
                    onPressed: _downloading
                        ? null
                        : () => _downloadZip(context, ref, build),
                    icon: _downloading
                        ? const SizedBox(
                            width: 12,
                            height: 12,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: AppColors.gold,
                            ),
                          )
                        : const Icon(Icons.download_outlined, size: 14),
                    label: Text(
                      'PROJECT ZIP',
                      style: AppTextStyles.smallCapsLabel(
                        fontSize: 9,
                        color: AppColors.gold,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: ListView.builder(
                itemCount: build.files.length,
                itemBuilder: (context, i) {
                  final file = build.files[i];
                  if (file.isDir) {
                    return ListTile(
                      dense: true,
                      leading: const Icon(Icons.folder_outlined, size: 18),
                      title: Text(
                        file.path,
                        style: AppTextStyles.mono(fontSize: 12),
                      ),
                    );
                  }
                  return ListTile(
                    dense: true,
                    leading: const Icon(Icons.description_outlined, size: 18),
                    title: Text(
                      file.path,
                      style: AppTextStyles.mono(fontSize: 12),
                    ),
                    trailing: Text(
                      '${file.size}B',
                      style: AppTextStyles.mono(
                        fontSize: 10,
                        color: AppColors.lightTextMuted,
                      ),
                    ),
                    onTap: () => _open(build.buildId, file.path),
                  );
                },
              ),
            ),
            if (_loadingFile)
              const LinearProgressIndicator(minHeight: 2, color: AppColors.gold),
          ],
        );
      },
      orElse: () => const Center(
        child: CircularProgressIndicator(color: AppColors.gold),
      ),
    );
  }

  Widget _sandboxMessage(String text) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Text(
          text,
          textAlign: TextAlign.center,
          style: AppTextStyles.bodySmall(
            color: AppColors.lightTextSecondary,
          ),
        ),
      ),
    );
  }

  Future<void> _open(String buildId, String path) async {
    setState(() {
      _loadingFile = true;
      // The AI editor uses the open file as its edit target.
      _openFilePath = path;
    });
    try {
      final body = await ref.read(workspaceRepositoryProvider).fetchBuildFile(
            buildId,
            path,
          );
      if (!mounted) return;
      await showSandboxFile(context, path, body);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Could not read $path: $e'),
          backgroundColor: AppColors.statusErrorRed,
        ),
      );
    } finally {
      if (mounted) setState(() => _loadingFile = false);
    }
  }

  Widget _previewTab(String buildId) {
    final liveAsync = ref.watch(buildStatusProvider(buildId));
    final build = liveAsync.valueOrNull;
    final url = build?.frontendUrl ??
        build?.renderServiceUrl ??
        // The backend's own preview route renders the app shell.
        '${ApiEndpoints.baseUrl}/api/v1/mvp/builds/$buildId/preview';

    if (build == null) {
      return const Center(child: CircularProgressIndicator(color: AppColors.gold));
    }

    if (url.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Text(
            isBuildInFlight(build)
                ? 'Preview appears once the build finishes.'
                : 'This build has no preview URL. Try deploying it.',
            textAlign: TextAlign.center,
            style: AppTextStyles.bodySmall(
              color: AppColors.lightTextSecondary,
            ),
          ),
        ),
      );
    }

    // Reuse the controller unless the build or target URL actually changed, so
    // the polling status stream does not restart the page.
    if (_previewUrl != url || _previewBuildId != buildId || _preview == null) {
      final controller = WebViewController()
        ..setJavaScriptMode(JavaScriptMode.unrestricted);
      _preview = controller;
      _previewUrl = url;
      _previewBuildId = buildId;
      controller.loadRequest(Uri.parse(url));
    }

    return Column(
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.sm,
            vertical: 4,
          ),
          color: AppColors.lightSurfaceSubtle,
          child: Row(
            children: [
              Expanded(
                child: Text(
                  url,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.mono(
                    fontSize: 9,
                    color: AppColors.lightTextMuted,
                  ),
                ),
              ),
              const SizedBox(width: AppSpacing.xs),
              // Desktop / mobile framing, matching the web sandbox toggle.
              _DeviceToggle(
                device: _device,
                onChanged: (d) => setState(() => _device = d),
              ),
            ],
          ),
        ),
        Expanded(
          child: Center(
            child: ConstrainedBox(
              constraints: BoxConstraints(
                maxWidth: _device == PreviewDevice.mobile ? 420 : double.infinity,
              ),
              child: WebViewWidget(controller: _preview!),
            ),
          ),
        ),
      ],
    );
  }

  /// `GET /mvp/builds/{id}/download` — the whole project as a ZIP.
  Future<void> _downloadZip(
    BuildContext context,
    WidgetRef ref,
    MVPBuildModel build,
  ) async {
    setState(() => _downloading = true);
    try {
      final bytes =
          await ref.read(workspaceRepositoryProvider).downloadBuild(build.buildId);
      final short = build.buildId.length >= 8
          ? build.buildId.substring(0, 8)
          : build.buildId;
      await FileDelivery.saveAndShare(
        bytes,
        'sandbox_build_$short.zip',
        subject: 'Sandbox build #$short',
      );
      ref.invalidate(mvpBuildsProvider);
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Download failed: $e'),
            backgroundColor: AppColors.statusErrorRed,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _downloading = false);
    }
  }

  /// `POST /mvp/builds/{id}/edit` — describe a change, get edited files back.
  Widget _aiEditorTab(
    String buildId,
    AsyncValue<List<MVPBuildModel>> buildsAsync,
  ) {
    final build = buildsAsync.valueOrNull?.isNotEmpty ?? false
        ? (buildsAsync.valueOrNull!.firstWhere(
              (b) => b.buildId == buildId,
              orElse: () => buildsAsync.valueOrNull!.first,
            ))
        : null;

    if (build == null) {
      return _sandboxMessage('Select a finished build first.');
    }
    if (isBuildInFlight(build)) {
      return _sandboxMessage('Wait for the build to finish before editing it.');
    }

    return Column(
      children: [
        Expanded(
          child: _editorLog.isEmpty
              ? _sandboxMessage(
                  'Describe a change and the agent rewrites the code. '
                  'For example: "switch the theme to dark and add a '
                  'settings page".',
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  itemCount: _editorLog.length,
                  itemBuilder: (context, i) {
                    final entry = _editorLog[i];
                    return Container(
                      margin: const EdgeInsets.only(bottom: AppSpacing.sm),
                      padding: const EdgeInsets.all(AppSpacing.sm),
                      decoration: BoxDecoration(
                        color: entry.isUser
                            ? AppColors.lightSurfaceSubtle
                            : AppColors.lightSurface,
                        borderRadius:
                            BorderRadius.circular(AppSpacing.radiusXs),
                        border: Border.all(color: AppColors.lightBorder),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            entry.isUser ? 'YOU' : 'AGENT',
                            style: AppTextStyles.smallCapsLabel(
                              fontSize: 8,
                              color: entry.isUser
                                  ? AppColors.gold
                                  : AppColors.lightTextMuted,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            entry.text,
                            style: AppTextStyles.mono(
                              fontSize: 11,
                              color: AppColors.lightTextPrimary,
                            ),
                          ),
                          if (entry.updatedFiles.isNotEmpty) ...[
                            const SizedBox(height: 4),
                            Text(
                              'UPDATED: ${entry.updatedFiles.join(', ')}',
                              style: AppTextStyles.mono(
                                fontSize: 9,
                                color: AppColors.statusLiveGreen,
                              ),
                            ),
                          ],
                        ],
                      ),
                    );
                  },
                ),
        ),
        if (_editing)
          const LinearProgressIndicator(minHeight: 2, color: AppColors.gold),
        Container(
          padding: const EdgeInsets.all(AppSpacing.sm),
          decoration: BoxDecoration(
            color: AppColors.lightSurface,
            border: Border(
              top: BorderSide(color: AppColors.lightBorder),
            ),
          ),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _editorInput,
                  style: AppTextStyles.mono(fontSize: 12),
                  minLines: 1,
                  maxLines: 4,
                  decoration: const InputDecoration(
                    hintText: 'Describe the change...',
                    isDense: true,
                  ),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              IconButton(
                onPressed: _editing ? null : () => _runEdit(build),
                icon: const Icon(Icons.send, size: 18),
                color: AppColors.gold,
              ),
            ],
          ),
        ),
      ],
    );
  }

  Future<void> _runEdit(MVPBuildModel build) async {
    final message = _editorInput.text.trim();
    if (message.isEmpty) return;
    _editorInput.clear();
    setState(() {
      _editing = true;
      _editorLog = [..._editorLog, _EditorEntry(message, isUser: true)];
    });

    try {
      final result = await ref
          .read(workspaceRepositoryProvider)
          .editBuildWithChat(
            build.buildId,
            message,
            activeFile: _openFilePath,
          );
      if (!mounted) return;
      setState(() {
        _editorLog = [
          ..._editorLog,
          _EditorEntry(
            result.message.isEmpty ? 'Done.' : result.message,
            isUser: false,
            updatedFiles: result.updatedFiles,
          ),
        ];
      });
      // The archive changed, so the file tree and preview are stale.
      ref.invalidate(mvpBuildsProvider);
      ref.invalidate(buildStatusProvider(build.buildId));
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _editorLog = [
          ..._editorLog,
          _EditorEntry('Edit failed: $e', isUser: false),
        ];
      });
    } finally {
      if (mounted) setState(() => _editing = false);
    }
  }
}

enum PreviewDevice { desktop, mobile }

class _EditorEntry {
  const _EditorEntry(
    this.text, {
    required this.isUser,
    this.updatedFiles = const [],
  });

  final String text;
  final bool isUser;
  final List<String> updatedFiles;
}

class _DeviceToggle extends StatelessWidget {
  const _DeviceToggle({required this.device, required this.onChanged});

  final PreviewDevice device;
  final ValueChanged<PreviewDevice> onChanged;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        _DeviceButton(
          icon: Icons.desktop_windows_outlined,
          tooltip: 'Desktop',
          selected: device == PreviewDevice.desktop,
          onTap: () => onChanged(PreviewDevice.desktop),
        ),
        _DeviceButton(
          icon: Icons.phone_iphone,
          tooltip: 'Mobile',
          selected: device == PreviewDevice.mobile,
          onTap: () => onChanged(PreviewDevice.mobile),
        ),
      ],
    );
  }
}

class _DeviceButton extends StatelessWidget {
  const _DeviceButton({
    required this.icon,
    required this.tooltip,
    required this.selected,
    required this.onTap,
  });

  final IconData icon;
  final String tooltip;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(3),
          child: Icon(
            icon,
            size: 14,
            color: selected
                ? AppColors.gold
                : AppColors.lightTextMuted,
          ),
        ),
      ),
    );
  }
}

/// Read-only viewer for the selected file, shown as a bottom sheet so the file
/// list stays navigable.
Future<void> showSandboxFile(BuildContext context, String path, String body) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: AppColors.lightSurface,
    shape: const RoundedRectangleBorder(
      borderRadius:
          BorderRadius.vertical(top: Radius.circular(AppSpacing.radiusMd)),
    ),
    builder: (ctx) => DraggableScrollableSheet(
      initialChildSize: 0.7,
      maxChildSize: 0.95,
      expand: false,
      builder: (ctx, controller) => Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(path, style: AppTextStyles.mono(fontSize: 12)),
            const SizedBox(height: AppSpacing.sm),
            Expanded(
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(AppSpacing.sm),
                decoration: BoxDecoration(
                  color: AppColors.darkBackground,
                  borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                ),
                child: SingleChildScrollView(
                  controller: controller,
                  child: SelectableText(
                    body,
                    style: AppTextStyles.mono(
                      fontSize: 10,
                      color: AppColors.darkTextPrimary,
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    ),
  );
}
