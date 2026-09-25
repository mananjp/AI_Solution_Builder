import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/workspace_repository.dart';
import '../domain/workspace_models.dart';

class ActiveWorkspaceIdNotifier extends Notifier<String?> {
  @override
  String? build() => null;
  void set(String? id) => state = id;
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

final workspacesListProvider = FutureProvider<List<WorkspaceModel>>((ref) async {
  final repo = ref.watch(workspaceRepositoryProvider);
  final workspaces = await repo.fetchWorkspaces();
  if (workspaces.isNotEmpty && ref.read(activeWorkspaceIdProvider) == null) {
    ref.read(activeWorkspaceIdProvider.notifier).set(workspaces.first.id);
  }
  return workspaces;
});

final solutionsListProvider =
    FutureProvider.family<List<SolutionModel>, String>((ref, workspaceId) async {
  final repo = ref.watch(workspaceRepositoryProvider);
  final solutions = await repo.fetchSolutions(workspaceId);
  if (solutions.isNotEmpty && ref.read(activeSolutionIdProvider) == null) {
    ref.read(activeSolutionIdProvider.notifier).set(solutions.first.id);
  }
  return solutions;
});

final solutionDetailProvider =
    FutureProvider.family<SolutionDetailModel, String>((ref, solutionId) async {
  final repo = ref.watch(workspaceRepositoryProvider);
  return await repo.fetchSolutionDetail(solutionId);
});

final mvpTemplatesProvider = FutureProvider<List<MVPTemplateModel>>((ref) async {
  final repo = ref.watch(workspaceRepositoryProvider);
  return await repo.fetchMvpTemplates();
});

final mvpBuildsProvider =
    FutureProvider.family<List<MVPBuildModel>, String>((ref, solutionId) async {
  final repo = ref.watch(workspaceRepositoryProvider);
  return await repo.fetchMvpBuilds(solutionId);
});

final workableModulesProvider =
    FutureProvider.family<Map<String, dynamic>, String>((ref, solutionId) async {
  final repo = ref.watch(workspaceRepositoryProvider);
  return await repo.fetchWorkableModules(solutionId);
});
