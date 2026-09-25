import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';

final settingsRepositoryProvider = Provider<SettingsRepository>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return SettingsRepository(apiClient: apiClient);
});

class SettingsRepository {
  final ApiClient _apiClient;

  SettingsRepository({required ApiClient apiClient}) : _apiClient = apiClient;

  Future<Map<String, dynamic>> fetchSettings() async {
    try {
      final response = await _apiClient.get('/api/v1/auth/me');
      if (response.data is Map<String, dynamic>) {
        final data = response.data as Map<String, dynamic>;
        final settings = data['settings'];
        if (settings is Map<String, dynamic>) {
          return settings;
        }
      }
    } catch (_) {}
    return {
      'github_token': '',
      'render_api_key': '',
      'vercel_token': '',
    };
  }

  Future<bool> saveCredentials({
    String? githubToken,
    String? renderApiKey,
    String? vercelToken,
  }) async {
    final payload = <String, dynamic>{};
    if (githubToken != null && githubToken.isNotEmpty) {
      payload['github_token'] = githubToken.trim();
    }
    if (renderApiKey != null && renderApiKey.isNotEmpty) {
      payload['render_api_key'] = renderApiKey.trim();
    }
    if (vercelToken != null && vercelToken.isNotEmpty) {
      payload['vercel_token'] = vercelToken.trim();
    }

    try {
      await _apiClient.patch('/api/v1/auth/me/settings', data: payload);
      return true;
    } catch (_) {
      // Also try post if patch differs
      try {
        await _apiClient.post('/api/v1/auth/me/settings', data: payload);
        return true;
      } catch (_) {
        return false;
      }
    }
  }
}

final userSettingsProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final repo = ref.watch(settingsRepositoryProvider);
  return await repo.fetchSettings();
});
