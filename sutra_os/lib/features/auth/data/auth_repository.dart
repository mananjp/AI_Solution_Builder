import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
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

    final data = response.data as Map<String, dynamic>;
    final token = data['access_token'] as String;
    await _storage.saveToken(token);
    return token;
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

    final data = response.data as Map<String, dynamic>;
    final token = data['access_token'] as String;
    await _storage.saveToken(token);
    return token;
  }

  Future<Map<String, dynamic>> anonymousLogin() async {
    final response = await _apiClient.post(ApiEndpoints.anonymous);
    final data = response.data as Map<String, dynamic>;
    final token = data['access_token'] as String;
    await _storage.saveToken(token);
    return data;
  }

  Future<UserModel> getMe() async {
    final response = await _apiClient.get(ApiEndpoints.me);
    final data = response.data as Map<String, dynamic>;
    final user = UserModel.fromJson(data);
    await _storage.saveUserInfo(email: user.email, name: user.fullName);
    return user;
  }

  Future<void> logout() async {
    await _storage.clearAll();
  }

  Future<String?> getSavedToken() async {
    return await _storage.getToken();
  }
}
