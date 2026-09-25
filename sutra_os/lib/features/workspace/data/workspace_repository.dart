import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../domain/workspace_models.dart';

final workspaceRepositoryProvider = Provider<WorkspaceRepository>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return WorkspaceRepository(apiClient: apiClient);
});

class WorkspaceRepository {
  final ApiClient _apiClient;

  WorkspaceRepository({required ApiClient apiClient}) : _apiClient = apiClient;

  Future<List<WorkspaceModel>> fetchWorkspaces() async {
    final response = await _apiClient.get(ApiEndpoints.workspaces);
    final data = response.data;
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map((item) => WorkspaceModel.fromJson(item))
          .toList();
    }
    return [];
  }

  Future<WorkspaceModel> createWorkspace({
    required String name,
    String? description,
  }) async {
    final response = await _apiClient.post(
      ApiEndpoints.workspaces,
      data: {
        'name': name.trim(),
        'description': description?.trim(),
      },
    );
    return WorkspaceModel.fromJson(response.data as Map<String, dynamic>);
  }

  Future<List<SolutionModel>> fetchSolutions(String workspaceId) async {
    final response = await _apiClient.get(
      ApiEndpoints.solutionsByWorkspace(workspaceId),
    );
    final data = response.data;
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map((item) => SolutionModel.fromJson(item))
          .toList();
    }
    return [];
  }

  Future<SolutionDetailModel> fetchSolutionDetail(String solutionId) async {
    final response = await _apiClient.get(
      ApiEndpoints.solution(solutionId),
    );
    return SolutionDetailModel.fromJson(response.data as Map<String, dynamic>);
  }

  Future<SolutionModel> createSolution({
    required String workspaceId,
    required String title,
    String? description,
  }) async {
    final response = await _apiClient.post(
      ApiEndpoints.solutions,
      data: {
        'workspace_id': workspaceId,
        'title': title.trim(),
        'description': description?.trim(),
      },
    );
    return SolutionModel.fromJson(response.data as Map<String, dynamic>);
  }

  Future<List<MVPTemplateModel>> fetchMvpTemplates() async {
    final response = await _apiClient.get(ApiEndpoints.mvpTemplates);
    final data = response.data;
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map((item) => MVPTemplateModel.fromJson(item))
          .toList();
    }
    return [];
  }

  Future<List<MVPBuildModel>> fetchMvpBuilds(String solutionId) async {
    final response = await _apiClient.get(ApiEndpoints.mvpBuilds(solutionId));
    final data = response.data;
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map((item) => MVPBuildModel.fromJson(item))
          .toList();
    }
    return [];
  }

  Future<Map<String, dynamic>> uploadUrl(String url) async {
    final response = await _apiClient.post(
      '/api/v1/upload/url',
      data: {'url': url.trim()},
    );
    if (response.data is Map<String, dynamic>) {
      return response.data as Map<String, dynamic>;
    }
    return {'status': 'success'};
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
    if (response.data is Map<String, dynamic>) {
      return response.data as Map<String, dynamic>;
    }
    return {'status': 'sent'};
  }

  Future<Map<String, dynamic>> uploadDocument({
    required String filename,
    List<int>? bytes,
    String? filePath,
  }) async {
    MultipartFile multipartFile;
    if (bytes != null) {
      multipartFile = MultipartFile.fromBytes(bytes, filename: filename);
    } else if (filePath != null) {
      multipartFile = await MultipartFile.fromFile(filePath, filename: filename);
    } else {
      throw ArgumentError('Either bytes or filePath must be provided');
    }

    final formData = FormData.fromMap({
      'file': multipartFile,
    });

    final response = await _apiClient.post(
      ApiEndpoints.uploadDocument,
      data: formData,
    );
    if (response.data is Map<String, dynamic>) {
      return response.data as Map<String, dynamic>;
    }
    return {'status': 'uploaded', 'filename': filename};
  }

  Future<Map<String, dynamic>> quickBuildMvp({
    required String workspaceId,
    required String prompt,
  }) async {
    final response = await _apiClient.post(
      ApiEndpoints.mvpQuickBuild,
      data: {
        'workspace_id': workspaceId,
        'prompt': prompt.trim(),
      },
    );
    if (response.data is Map<String, dynamic>) {
      return response.data as Map<String, dynamic>;
    }
    return {'status': 'dispatched'};
  }

  Future<Map<String, dynamic>> buildSolutionMvp(String solutionId) async {
    final response = await _apiClient.post(
      ApiEndpoints.mvpBuild(solutionId),
    );
    if (response.data is Map<String, dynamic>) {
      return response.data as Map<String, dynamic>;
    }
    return {'status': 'dispatched'};
  }

  Future<Map<String, dynamic>> fetchWorkableModules(String solutionId) async {
    try {
      final response = await _apiClient.get(ApiEndpoints.workableModules(solutionId));
      if (response.data is Map<String, dynamic>) {
        return response.data as Map<String, dynamic>;
      }
    } catch (_) {}
    return {};
  }
}
