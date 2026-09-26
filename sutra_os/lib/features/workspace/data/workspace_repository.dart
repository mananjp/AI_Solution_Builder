import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../core/network/api_exceptions.dart';
import '../../../core/network/json_utils.dart';
import '../domain/workspace_models.dart';

final workspaceRepositoryProvider = Provider<WorkspaceRepository>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return WorkspaceRepository(apiClient: apiClient);
});

class WorkspaceRepository {
  final ApiClient _apiClient;

  WorkspaceRepository({required ApiClient apiClient}) : _apiClient = apiClient;

  /// Endpoints wrap collections inconsistently: some return a bare list, some
  /// `{items: [...]}`. Normalise so the parser only sees a list.
  List<Map<String, dynamic>> _items(dynamic data) {
    if (data is List) return asList(data).map(asMap).toList();
    final map = asMap(data);
    final items = map['items'] ?? map['results'] ?? map['data'];
    return asList(items).map(asMap).toList();
  }

  Future<List<WorkspaceModel>> fetchWorkspaces() async {
    final response = await _apiClient.get(ApiEndpoints.workspaces);
    return _items(response.data).map(WorkspaceModel.fromJson).toList();
  }

  Future<WorkspaceModel> createWorkspace({
    required String name,
    String? description,
  }) async {
    final response = await _apiClient.post(
      ApiEndpoints.workspaces,
      data: {
        'name': name.trim(),
        if (description != null && description.trim().isNotEmpty)
          'description': description.trim(),
      },
    );
    return WorkspaceModel.fromJson(asMap(response.data));
  }

  Future<List<SolutionModel>> fetchSolutions(String workspaceId) async {
    final response = await _apiClient.get(
      ApiEndpoints.solutionsByWorkspace(workspaceId),
    );
    return _items(response.data).map(SolutionModel.fromJson).toList();
  }

  Future<SolutionDetailModel> fetchSolutionDetail(String solutionId) async {
    final response = await _apiClient.get(
      ApiEndpoints.solution(solutionId),
    );
    return SolutionDetailModel.fromJson(asMap(response.data));
  }

  Future<SolutionModel> createSolution({
    required String workspaceId,
    required String title,
    String? description,
  }) async {
    String targetWsId = workspaceId.trim();

    if (targetWsId.isEmpty) {
      final list = await fetchWorkspaces();
      if (list.isNotEmpty) {
        targetWsId = list.first.id;
      } else {
        final newWs = await createWorkspace(name: 'Primary Workspace');
        targetWsId = newWs.id;
      }
    }

    try {
      final response = await _apiClient.post(
        ApiEndpoints.solutions,
        data: {
          'workspace_id': targetWsId,
          'title': title.trim(),
          if (description != null && description.trim().isNotEmpty)
            'description': description.trim(),
        },
      );
      return SolutionModel.fromJson(asMap(response.data));
    } on ApiException catch (e) {
      if (e.statusCode == 404) {
        final list = await fetchWorkspaces();
        final validWs = list.isNotEmpty
            ? list.first
            : await createWorkspace(name: 'Primary Workspace');

        final retryResponse = await _apiClient.post(
          ApiEndpoints.solutions,
          data: {
            'workspace_id': validWs.id,
            'title': title.trim(),
            if (description != null && description.trim().isNotEmpty)
              'description': description.trim(),
          },
        );
        return SolutionModel.fromJson(asMap(retryResponse.data));
      }
      rethrow;
    }
  }

  Future<List<MVPTemplateModel>> fetchMvpTemplates() async {
    final response = await _apiClient.get(ApiEndpoints.mvpTemplates);
    return _items(response.data).map(MVPTemplateModel.fromJson).toList();
  }

  Future<List<MVPBuildModel>> fetchMvpBuilds(String solutionId) async {
    if (solutionId.trim().isEmpty) return const [];
    final response = await _apiClient.get(ApiEndpoints.mvpBuilds(solutionId));
    return _items(response.data).map(MVPBuildModel.fromJson).toList();
  }

  Future<Map<String, dynamic>> uploadUrl(String url) async {
    final response = await _apiClient.post(
      ApiEndpoints.uploadUrl,
      data: {'url': url.trim()},
    );
    return asMap(response.data);
  }

  Future<Map<String, dynamic>> sendChatMessage({
    required String solutionId,
    required String message,
  }) async {
    final response = await _apiClient.post(
      ApiEndpoints.chatSend,
      data: {
        'solution_id': solutionId,
        'message': message.trim(),
      },
    );
    return asMap(response.data);
  }

  Future<Map<String, dynamic>> uploadDocument({
    required String filename,
    List<int>? bytes,
    String? filePath,
  }) async {
    final MultipartFile multipartFile;
    if (bytes != null) {
      multipartFile = MultipartFile.fromBytes(bytes, filename: filename);
    } else if (filePath != null) {
      multipartFile = await MultipartFile.fromFile(filePath, filename: filename);
    } else {
      throw ArgumentError('Either bytes or filePath must be provided');
    }

    final response = await _apiClient.post(
      ApiEndpoints.uploadDocument,
      data: FormData.fromMap({'file': multipartFile}),
      options: Options(contentType: 'multipart/form-data'),
    );
    return asMap(response.data);
  }

  /// `POST /upload/audio` transcribes a voice note. The backend accepts
  /// wav/mp3/m4a/ogg/webm/flac up to 25MB and replies with
  /// `{extracted_context, character_count, ...}`.
  Future<Map<String, dynamic>> uploadAudio({
    required String filename,
    String? filePath,
    List<int>? bytes,
    String? language,
  }) async {
    final MultipartFile multipartFile;
    if (bytes != null) {
      multipartFile = MultipartFile.fromBytes(bytes, filename: filename);
    } else if (filePath != null) {
      multipartFile = await MultipartFile.fromFile(filePath, filename: filename);
    } else {
      throw ArgumentError('Either bytes or filePath must be provided');
    }

    final response = await _apiClient.post(
      ApiEndpoints.uploadAudio,
      data: FormData.fromMap({
        'file': multipartFile,
        if (language != null && language.isNotEmpty) 'language': language,
      }),
      options: Options(contentType: 'multipart/form-data'),
    );
    return asMap(response.data);
  }

  /// `POST /mvp/quick-build` expects `{template, app_name?, config?}` — the
  /// backend creates its own workspace. The old `{workspace_id, prompt}` body
  /// was silently ignored, so nothing was ever templated.
  Future<MVPBuildModel> quickBuildMvp({
    required String template,
    String? appName,
  }) async {
    final response = await _apiClient.post(
      ApiEndpoints.mvpQuickBuild,
      data: {
        'template': template,
        if (appName != null && appName.isNotEmpty) 'app_name': appName,
      },
    );
    return MVPBuildModel.fromJson(asMap(response.data));
  }

  Future<MVPBuildModel> buildSolutionMvp(String solutionId) async {
    final response = await _apiClient.post(
      ApiEndpoints.mvpBuild(solutionId),
    );
    return MVPBuildModel.fromJson(asMap(response.data));
  }

  Future<MVPBuildModel> fetchBuildStatus(String buildId) async {
    final response = await _apiClient.get(ApiEndpoints.mvpBuildStatus(buildId));
    return MVPBuildModel.fromJson(asMap(response.data));
  }

  Future<Uint8List> downloadBuild(String buildId) async {
    return _apiClient.download(ApiEndpoints.mvpDownload(buildId));
  }

  Future<String> fetchBuildFile(String buildId, String path) async {
    final response = await _apiClient.get<List<int>>(
      ApiEndpoints.mvpBuildFile(buildId, path),
      options: Options(responseType: ResponseType.bytes),
    );
    final data = response.data;
    if (data == null) return '';
    return utf8.decode(data, allowMalformed: true);
  }

  Future<void> deleteBuild(String buildId) async {
    await _apiClient.delete(ApiEndpoints.mvpDeleteBuild(buildId));
  }

  Future<Map<String, dynamic>> configureBuild(
    String buildId, {
    String? appName,
    Map<String, dynamic>? env,
  }) async {
    final response = await _apiClient.post(
      ApiEndpoints.mvpConfigure(buildId),
      data: {
        if (appName != null && appName.isNotEmpty) 'app_name': appName,
        if (env != null && env.isNotEmpty) 'env': env,
      },
    );
    return asMap(response.data);
  }

  Future<MVPEnvPlanModel> fetchEnvPlan(String buildId) async {
    final response = await _apiClient.get(ApiEndpoints.mvpEnvPlan(buildId));
    return MVPEnvPlanModel.fromJson(asMap(response.data));
  }

  /// Pushes a finished build to GitHub (+ Render blueprint).
  ///
  /// `repo_name` is required by the backend and must match
  /// `^[A-Za-z0-9_.-]+$`. The previous signature sent `app_name`, which the
  /// endpoint never reads.
  Future<MVPDeployResultModel> deployBuild(
    String buildId, {
    required String repoName,
    String description = '',
    bool isPrivate = false,
    bool force = false,
    Map<String, dynamic>? env,
  }) async {
    final response = await _apiClient.post(
      ApiEndpoints.mvpDeploy(buildId),
      data: {
        'repo_name': repoName,
        'description': description,
        'private': isPrivate,
        'force': force,
        if (env != null && env.isNotEmpty) 'env': env,
      },
    );
    return MVPDeployResultModel.fromJson(asMap(response.data));
  }

  /// Real Render deploy state. Never inferred from the request succeeding.
  Future<MVPDeployStatusModel> fetchDeployStatus(String buildId) async {
    final response =
        await _apiClient.get(ApiEndpoints.mvpDeployStatus(buildId));
    return MVPDeployStatusModel.fromJson(asMap(response.data));
  }

  /// `POST /mvp/builds/{id}/edit` — natural-language code edit used by the
  /// sandbox AI editor panel.
  Future<MVPChatEditModel> editBuildWithChat(
    String buildId,
    String message, {
    String? activeFile,
  }) async {
    final response = await _apiClient.post(
      ApiEndpoints.mvpEdit(buildId),
      data: {
        'message': message,
        if (activeFile != null && activeFile.isNotEmpty)
          'active_file': activeFile,
      },
    );
    return MVPChatEditModel.fromJson(asMap(response.data));
  }

  Future<Map<String, dynamic>> destroyPreview(String buildId) async {
    final response =
        await _apiClient.post(ApiEndpoints.mvpPreviewDestroy(buildId));
    return asMap(response.data);
  }

  // ─── Solution review ──────────────────────────────────────────────────────

  Future<Map<String, dynamic>> approveSolution(String solutionId) async {
    final response =
        await _apiClient.post(ApiEndpoints.solutionApprove(solutionId));
    return asMap(response.data);
  }

  Future<Map<String, dynamic>> requestSolutionChanges(
    String solutionId,
    String comments,
  ) async {
    final response = await _apiClient.post(
      ApiEndpoints.solutionRequestChanges(solutionId),
      data: {'comments': comments},
    );
    return asMap(response.data);
  }

  Future<Map<String, dynamic>> fetchSolutionDecisions(String solutionId) async {
    final response =
        await _apiClient.get(ApiEndpoints.solutionDecisions(solutionId));
    return asMap(response.data);
  }

  /// `dry_run: true` previews the blast radius without spending credits.
  Future<Map<String, dynamic>> regenerateArtifacts(
    String solutionId, {
    required List<String> targets,
    required String feedback,
    bool cascade = true,
    bool dryRun = true,
  }) async {
    final response = await _apiClient.post(
      ApiEndpoints.solutionRegenerate(solutionId),
      data: {
        'targets': targets,
        'feedback': feedback,
        'cascade': cascade,
        'dry_run': dryRun,
      },
    );
    return asMap(response.data);
  }

  /// `GET /artifacts/{artifactId}/explain` — decision log behind an artifact.
  Future<ExplainabilityModel> fetchExplainability(String artifactId) async {
    final response = await _apiClient.get(ApiEndpoints.artifactExplain(artifactId));
    return ExplainabilityModel.fromJson(asMap(response.data));
  }

  Future<List<ArtifactModel>> fetchArtifactHistory(
    String solutionId,
    String artifactType,
  ) async {
    final response = await _apiClient.get(
      ApiEndpoints.artifactHistory(solutionId, artifactType),
    );
    return asList(response.data)
        .map(asMap)
        .map(ArtifactModel.fromJson)
        .toList();
  }

  Future<Map<String, dynamic>> regenerateArtifact({
    required String solutionId,
    required String artifactType,
    required String userFeedback,
  }) async {
    final response = await _apiClient.post(
      ApiEndpoints.artifactRegenerate,
      data: {
        'solution_id': solutionId,
        'artifact_type': artifactType,
        'user_feedback': userFeedback,
      },
    );
    return asMap(response.data);
  }

  /// `format` is one of `json`, `markdown`, `zip`.
  Future<Uint8List> exportArtifacts(
    String solutionId,
    String format,
  ) async {
    return _apiClient.download(ApiEndpoints.exportArtifact(solutionId, format));
  }

  // ─── Workable systems ─────────────────────────────────────────────────────

  Future<Map<String, dynamic>> provisionWorkable(String solutionId) async {
    final response = await _apiClient.post(
      ApiEndpoints.workableProvision(solutionId),
      data: {},
    );
    return asMap(response.data);
  }

  Future<Map<String, dynamic>> seedWorkable(String solutionId, {int rows = 5}) async {
    final response = await _apiClient.post(ApiEndpoints.workableSeed(solutionId, rows: rows));
    return asMap(response.data);
  }

  Future<List<WorkableRecordModel>> fetchWorkableRecords(
    String solutionId,
    String moduleName,
    String entity,
  ) async {
    final response = await _apiClient.get(
      ApiEndpoints.workableRecords(solutionId, moduleName, entity),
    );
    return asList(response.data)
        .map(asMap)
        .map(WorkableRecordModel.fromJson)
        .toList();
  }

  Future<WorkableRecordModel> createWorkableRecord(
    String solutionId,
    String moduleName,
    String entity,
    Map<String, dynamic> record,
  ) async {
    final response = await _apiClient.post(
      ApiEndpoints.workableRecords(solutionId, moduleName, entity),
      data: record,
    );
    return WorkableRecordModel.fromJson(asMap(response.data));
  }

  /// Partial update via `PATCH /{solution}/{module}/{entity}/{row_id}`.
  Future<WorkableRecordModel> updateWorkableRecord(
    String solutionId,
    String moduleName,
    String entity,
    String rowId,
    Map<String, dynamic> record,
  ) async {
    final response = await _apiClient.patch(
      ApiEndpoints.workableRecord(solutionId, moduleName, entity, rowId),
      data: record,
    );
    return WorkableRecordModel.fromJson(asMap(response.data));
  }

  Future<void> deleteWorkableRecord(
    String solutionId,
    String moduleName,
    String entity,
    String rowId,
  ) async {
    await _apiClient.delete(
      ApiEndpoints.workableRecord(solutionId, moduleName, entity, rowId),
    );
  }

  Future<Map<String, dynamic>> fetchWorkableModules(String solutionId) async {
    final response = await _apiClient.get(
      ApiEndpoints.workableModules(solutionId),
    );
    return asMap(response.data);
  }
}
