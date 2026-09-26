import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../core/network/api_exceptions.dart';
import '../../../core/network/json_utils.dart';
import '../../../core/storage/secure_storage_service.dart';
import '../domain/user_model.dart';

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  final storage = ref.watch(secureStorageServiceProvider);
  return AuthRepository(apiClient: apiClient, storage: storage);
});

class AuthRepository {
  final ApiClient _apiClient;
  final SecureStorageService _storage;

  AuthRepository({
    required ApiClient apiClient,
    required SecureStorageService storage,
  })  : _apiClient = apiClient,
        _storage = storage;

  /// Persists the token and primes the client cache so the very next request
  /// already carries the Authorization header.
  Future<String> _persistToken(dynamic raw) async {
    final token = asStringOrNull(raw);
    if (token == null) {
      throw ApiException(
        message: 'Sign-in succeeded but the server returned no access token.',
        statusCode: null,
      );
    }
    await _storage.saveToken(token);
    _apiClient.updateToken(token);
    return token;
  }

  Future<String> login({
    required String email,
    required String password,
  }) async {
    final response = await _apiClient.post(
      ApiEndpoints.login,
      data: {
        'email': email.trim(),
        'password': password,
      },
    );
    return _persistToken(asMap(response.data)['access_token']);
  }

  Future<String> register({
    required String email,
    required String fullName,
    required String password,
    required String orgName,
  }) async {
    final response = await _apiClient.post(
      ApiEndpoints.register,
      data: {
        'email': email.trim(),
        'full_name': fullName.trim(),
        'password': password,
        'org_name': orgName.trim(),
      },
    );
    return _persistToken(asMap(response.data)['access_token']);
  }

  Future<String> anonymousLogin() async {
    final response = await _apiClient.post(ApiEndpoints.anonymous);
    return _persistToken(asMap(response.data)['access_token']);
  }

  Future<Response<dynamic>> oauthProviders() {
    return _apiClient.get(ApiEndpoints.providers);
  }

  /// Returns the provider's authorization URL for the system browser to open.
  Future<Response<dynamic>> oauthAuthorize(String provider) {
    return _apiClient.get(ApiEndpoints.oauthAuthorize(provider));
  }

  /// Exchanges the callback code for a session token and persists it.
  /// [provider] must be the same one used to start the flow, because the
  /// backend routes the callback by provider name.
  Future<String> oauthCallback(
    String provider,
    String code, {
    String? state,
  }) async {
    final response = await _apiClient.get(
      ApiEndpoints.oauthCallback(provider),
      queryParameters: {
        'code': code,
        if (state != null && state.isNotEmpty) 'state': state,
      },
    );
    return _persistToken(asMap(response.data)['access_token']);
  }

  Future<UserModel> getMe() async {
    final response = await _apiClient.get(ApiEndpoints.me);
    final user = UserModel.fromJson(asMap(response.data));
    await _storage.saveUserInfo(email: user.email, name: user.fullName);
    return user;
  }

  Future<void> logout() async {
    await _apiClient.clearSession();
  }

  Future<String?> getSavedToken() async {
    return _storage.getToken();
  }
}

