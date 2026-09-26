import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';

final settingsRepositoryProvider = Provider<SettingsRepository>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return SettingsRepository(apiClient: apiClient);
});

class SettingsRepository {
  final ApiClient _apiClient;

  SettingsRepository({required ApiClient apiClient}) : _apiClient = apiClient;

  /// The API is write-only for deploy credentials: `UserResponse` has no
  /// `settings` field and `/auth/me/settings` accepts only PATCH/POST, with
  /// values stored encrypted. Tokens therefore can never be read back, and this
  /// returns an empty map rather than a set of blank strings that the screen
  /// would then treat as "the user cleared their keys".
  Future<Map<String, dynamic>> fetchSettings() async {
    return const {};
  }

  /// `PATCH /auth/me/settings` with `{github_token, render_api_key, vercel_token}`.
  Future<void> saveCredentials({
    String? githubToken,
    String? renderApiKey,
    String? vercelToken,
  }) async {
    final payload = <String, dynamic>{};
    if (githubToken != null && githubToken.trim().isNotEmpty) {
      payload['github_token'] = githubToken.trim();
    }
    if (renderApiKey != null && renderApiKey.trim().isNotEmpty) {
      payload['render_api_key'] = renderApiKey.trim();
    }
    if (vercelToken != null && vercelToken.trim().isNotEmpty) {
      payload['vercel_token'] = vercelToken.trim();
    }

    if (payload.isEmpty) {
      return;
    }

    // No silent retry against a second verb: a failure here has to be visible,
    // otherwise the user is told their keys were saved when they were not.
    await _apiClient.patch(ApiEndpoints.meSettings, data: payload);
  }
}

final userSettingsProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final repo = ref.watch(settingsRepositoryProvider);
  return await repo.fetchSettings();
});
