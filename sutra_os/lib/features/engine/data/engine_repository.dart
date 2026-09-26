import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../core/network/json_utils.dart';
import '../domain/engine_models.dart';

final engineRepositoryProvider = Provider<EngineRepository>((ref) {
  return EngineRepository(apiClient: ref.watch(apiClientProvider));
});

class EngineRepository {
  final ApiClient _apiClient;

  EngineRepository({required ApiClient apiClient}) : _apiClient = apiClient;

  Future<EngineHealthModel> fetchHealth() async {
    final response = await _apiClient.get(ApiEndpoints.engineHealth);
    return EngineHealthModel.fromJson(asMap(response.data));
  }

  Future<EngineDiagnosisModel> diagnose() async {
    final response = await _apiClient.get(ApiEndpoints.engineDiagnose);
    return EngineDiagnosisModel.fromJson(asMap(response.data));
  }

  Future<SystemResourcesModel> fetchResources() async {
    final response = await _apiClient.get(ApiEndpoints.systemResources);
    return SystemResourcesModel.fromJson(asMap(response.data));
  }
}
