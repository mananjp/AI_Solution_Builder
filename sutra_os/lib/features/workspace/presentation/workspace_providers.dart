import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../auth/presentation/auth_controller.dart';
import '../data/workspace_repository.dart';
import '../domain/workspace_models.dart';

// ─── Active IDs ───────────────────────────────────────────────────────────────

class ActiveWorkspaceIdNotifier extends Notifier<String?> {
  @override
  String? build() => null;

  void set(String? id) {
    if (state == id) return;
    state = id;
    // A workspace switch invalidates the solution scoped to the old one.
    ref.read(activeSolutionIdProvider.notifier).set(null);
  }
}

final activeWorkspaceIdProvider =
    NotifierProvider<ActiveWorkspaceIdNotifier, String?>(
        ActiveWorkspaceIdNotifier.new);

class ActiveSolutionIdNotifier extends Notifier<String?> {
  @override
  String? build() => null;
  void set(String? id) => state = id;
}

final activeSolutionIdProvider =
    NotifierProvider<ActiveSolutionIdNotifier, String?>(
        ActiveSolutionIdNotifier.new);

/// Everything derived from one solution, so a create/delete refreshes all of
/// it with a single call.
void invalidateSolutionScoped(WidgetRef ref, String? solutionId) {
  ref.invalidate(solutionDetailProvider);
  if (solutionId != null) {
    ref.invalidate(mvpBuildsProvider(solutionId));
    ref.invalidate(workableModulesProvider(solutionId));
  }
}

void invalidateWorkspaceScoped(WidgetRef ref, String? workspaceId) {
  ref.invalidate(workspacesListProvider);
  if (workspaceId != null) {
    ref.invalidate(solutionsListProvider(workspaceId));
  }
}

// ─── Workspaces List ──────────────────────────────────────────────────────────

class WorkspacesListNotifier extends AsyncNotifier<List<WorkspaceModel>> {
  @override
  Future<List<WorkspaceModel>> build() async {
    // Only the auth *status* matters here. Watching the whole AuthState made
    // every field change (token, user, error message) re-trigger the fetch.
    final isAuthenticated = ref.watch(
      authControllerProvider.select((s) => s.isAuthenticated),
    );
    if (!isAuthenticated) return [];

    final repo = ref.read(workspaceRepositoryProvider);
    final workspaces = await repo.fetchWorkspaces();

    // Auto-select only when nothing is active or the active id is gone, so a
    // refresh never yanks the user off their current selection.
    final currentId = ref.read(activeWorkspaceIdProvider);
    final stillValid = workspaces.any((w) => w.id == currentId);
    if (workspaces.isNotEmpty && (currentId == null || !stillValid)) {
      ref.read(activeWorkspaceIdProvider.notifier).set(workspaces.first.id);
    } else if (workspaces.isEmpty) {
      ref.read(activeWorkspaceIdProvider.notifier).set(null);
    }

    return workspaces;
  }

  /// `invalidateSelf` keeps Riverpod's dependency tracking intact. Calling
  /// `build()` by hand re-ran the body outside a build context and re-registered
  /// the `ref.watch` on every pull-to-refresh.
  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }
}

final workspacesListProvider =
    AsyncNotifierProvider<WorkspacesListNotifier, List<WorkspaceModel>>(
        WorkspacesListNotifier.new);

// ─── Solutions List (keyed by workspaceId) ────────────────────────────────────

class SolutionsListNotifier
    extends FamilyAsyncNotifier<List<SolutionModel>, String> {
  @override
  Future<List<SolutionModel>> build(String arg) async {
    final isAuthenticated = ref.watch(
      authControllerProvider.select((s) => s.isAuthenticated),
    );
    if (!isAuthenticated) return [];

    final repo = ref.read(workspaceRepositoryProvider);
    final solutions = await repo.fetchSolutions(arg);

    final currentId = ref.read(activeSolutionIdProvider);
    final stillValid = solutions.any((s) => s.id == currentId);
    if (solutions.isNotEmpty && (currentId == null || !stillValid)) {
      ref.read(activeSolutionIdProvider.notifier).set(solutions.first.id);
    } else if (solutions.isEmpty) {
      ref.read(activeSolutionIdProvider.notifier).set(null);
    }

    return solutions;
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }
}

final solutionsListProvider = AsyncNotifierProvider.family<
    SolutionsListNotifier, List<SolutionModel>, String>(
  SolutionsListNotifier.new,
);

/// The solutions of the currently selected workspace.
///
/// [solutionsListProvider] is a family, so it only runs when something observes
/// a specific instance. Nothing used to, which meant [activeSolutionId] was
/// never populated and a returning user could not reopen an existing blueprint —
/// creating one was the only path into the workspace. Watching this bridges the
/// active workspace to its solution list.
final activeSolutionsProvider = FutureProvider<List<SolutionModel>>((ref) async {
  final workspaceId = ref.watch(activeWorkspaceIdProvider);
  if (workspaceId == null) return const [];
  return ref.watch(solutionsListProvider(workspaceId).future);
});

/// The solution to show in a solution-scoped screen (Builds, Blueprint, Live App).
///
/// The auto-select in [solutionsListProvider] only runs while that provider is
/// being watched, so a screen that merely reads `activeSolutionIdProvider`
/// would stay null and claim the user has no blueprint. Watching the list here
/// keeps the auto-select alive and falls back to the newest solution.
final effectiveSolutionIdProvider = Provider<String?>((ref) {
  // Watch the workspace list first: its body auto-selects the active workspace,
  // which is the root of the whole chain. Without this the workspace id stays
  // null and every solution-scoped screen reports an empty workspace.
  ref.watch(workspacesListProvider);
  final active = ref.watch(activeSolutionIdProvider);
  if (active != null) return active;
  return ref.watch(activeSolutionsProvider).valueOrNull?.firstOrNull?.id;
});

// ─── Solution Detail ──────────────────────────────────────────────────────────

class SolutionDetailNotifier
    extends FamilyAsyncNotifier<SolutionDetailModel, String> {
  @override
  Future<SolutionDetailModel> build(String arg) async {
    final isAuthenticated = ref.watch(
      authControllerProvider.select((s) => s.isAuthenticated),
    );
    if (!isAuthenticated) {
      throw StateError('Solution detail requested without a session.');
    }

    final repo = ref.read(workspaceRepositoryProvider);
    return await repo.fetchSolutionDetail(arg);
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }
}

final solutionDetailProvider = AsyncNotifierProvider.family<
    SolutionDetailNotifier, SolutionDetailModel, String>(
    SolutionDetailNotifier.new);

// ─── MVP Templates ────────────────────────────────────────────────────────────

final mvpTemplatesProvider = FutureProvider<List<MVPTemplateModel>>((ref) async {
  final repo = ref.watch(workspaceRepositoryProvider);
  return await repo.fetchMvpTemplates();
});

// ─── MVP Builds ───────────────────────────────────────────────────────────────

class MvpBuildsNotifier
    extends FamilyAsyncNotifier<List<MVPBuildModel>, String> {
  @override
  Future<List<MVPBuildModel>> build(String arg) async {
    final repo = ref.read(workspaceRepositoryProvider);
    return await repo.fetchMvpBuilds(arg);
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }
}

final mvpBuildsProvider = AsyncNotifierProvider.family<MvpBuildsNotifier,
    List<MVPBuildModel>, String>(MvpBuildsNotifier.new);

/// A build whose job is still running, so the UI knows to keep polling.
bool isBuildInFlight(MVPBuildModel build) => const {
      'queued',
      'pending',
      'building',
      'running',
    }.contains(build.status.toLowerCase());

/// One build's live status, refreshed every 3s only while it is still running.
///
/// The web app re-arms a 3s `setInterval` for any build in
/// `queued|pending|building` and stops when the build settles. Fetching once
/// would leave the progress bar frozen at whatever it read at mount time.
final buildStatusProvider =
    StreamProvider.family.autoDispose<MVPBuildModel, String>((ref, buildId) async* {
  if (buildId.trim().isEmpty) return;
  final repo = ref.read(workspaceRepositoryProvider);
  var settled = false;
  var first = true;

  while (!settled) {
    MVPBuildModel build;
    try {
      build = await repo.fetchBuildStatus(buildId);
    } catch (_) {
      if (first) rethrow;
      // A transient poll failure should not kill the stream; retry shortly.
      await Future<void>.delayed(const Duration(seconds: 3));
      continue;
    }
    first = false;
    yield build;
    settled = !isBuildInFlight(build);
    if (!settled) {
      await Future<void>.delayed(const Duration(seconds: 3));
    }
  }
});

// ─── Workable Modules ─────────────────────────────────────────────────────────

final workableModulesProvider =
    FutureProvider.family<Map<String, dynamic>, String>((ref, solutionId) async {
  final repo = ref.watch(workspaceRepositoryProvider);
  return await repo.fetchWorkableModules(solutionId);
});
