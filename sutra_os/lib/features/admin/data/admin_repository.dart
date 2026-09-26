import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../core/network/json_utils.dart';
import '../domain/admin_models.dart';

final adminRepositoryProvider = Provider<AdminRepository>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return AdminRepository(apiClient: apiClient);
});

class AdminRepository {
  final ApiClient _apiClient;

  AdminRepository({required ApiClient apiClient}) : _apiClient = apiClient;

  /// Errors propagate instead of resolving to invented figures, so a failed
  /// admin fetch shows as an error state rather than plausible-looking numbers.
  Future<AdminStatsModel> fetchAdminStats() async {
    final response = await _apiClient.get(ApiEndpoints.adminStats);
    return AdminStatsModel.fromJson(asMap(response.data));
  }

  Future<List<AdminUserModel>> fetchAdminUsers() async {
    final response = await _apiClient.get(ApiEndpoints.adminUsers);
    return asList(response.data).map(asMap).map(AdminUserModel.fromJson).toList();
  }

  Future<List<AdminAuditLogModel>> fetchAuditLogs() async {
    final response = await _apiClient.get(ApiEndpoints.adminAuditLogs);
    return asList(response.data).map(asMap).map(AdminAuditLogModel.fromJson).toList();
  }
}

final adminStatsProvider = FutureProvider<AdminStatsModel>((ref) async {
  final repo = ref.watch(adminRepositoryProvider);
  return await repo.fetchAdminStats();
});

final adminUsersProvider = FutureProvider<List<AdminUserModel>>((ref) async {
  final repo = ref.watch(adminRepositoryProvider);
  return await repo.fetchAdminUsers();
});

final adminAuditLogsProvider = FutureProvider<List<AdminAuditLogModel>>((ref) async {
  final repo = ref.watch(adminRepositoryProvider);
  return await repo.fetchAuditLogs();
});
