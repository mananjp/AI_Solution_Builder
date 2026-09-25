import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../domain/admin_models.dart';

final adminRepositoryProvider = Provider<AdminRepository>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return AdminRepository(apiClient: apiClient);
});

class AdminRepository {
  final ApiClient _apiClient;

  AdminRepository({required ApiClient apiClient}) : _apiClient = apiClient;

  Future<AdminStatsModel> fetchAdminStats() async {
    try {
      final response = await _apiClient.get('/api/v1/admin/stats');
      if (response.data is Map<String, dynamic>) {
        return AdminStatsModel.fromJson(response.data as Map<String, dynamic>);
      }
    } catch (_) {}
    return AdminStatsModel(
      totalUsers: 1,
      totalWorkspaces: 1,
      totalSolutions: 1,
      activeBuilds: 0,
      totalCreditsConsumed: 450,
    );
  }

  Future<List<AdminUserModel>> fetchAdminUsers() async {
    try {
      final response = await _apiClient.get('/api/v1/admin/users');
      final data = response.data;
      if (data is List) {
        return data
            .whereType<Map<String, dynamic>>()
            .map((item) => AdminUserModel.fromJson(item))
            .toList();
      }
    } catch (_) {}
    return [];
  }

  Future<List<AdminAuditLogModel>> fetchAuditLogs() async {
    try {
      final response = await _apiClient.get('/api/v1/admin/audit-logs');
      final data = response.data;
      if (data is List) {
        return data
            .whereType<Map<String, dynamic>>()
            .map((item) => AdminAuditLogModel.fromJson(item))
            .toList();
      }
    } catch (_) {}
    return [];
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
