import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

final secureStorageServiceProvider = Provider<SecureStorageService>((ref) {
  return SecureStorageService();
});

class SecureStorageService {
  static const _tokenKey = 'sutra_jwt_token';
  static const _userEmailKey = 'sutra_user_email';
  static const _userNameKey = 'sutra_user_name';

  final FlutterSecureStorage _storage;

  SecureStorageService({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  Future<void> saveToken(String token) async {
    await _storage.write(key: _tokenKey, value: token);
  }

  Future<String?> getToken() async {
    return await _storage.read(key: _tokenKey);
  }

  Future<void> saveUserInfo({required String email, required String name}) async {
    await _storage.write(key: _userEmailKey, value: email);
    await _storage.write(key: _userNameKey, value: name);
  }

  Future<Map<String, String?>> getUserInfo() async {
    final email = await _storage.read(key: _userEmailKey);
    final name = await _storage.read(key: _userNameKey);
    return {'email': email, 'name': name};
  }

  Future<void> clearAll() async {
    await _storage.delete(key: _tokenKey);
    await _storage.delete(key: _userEmailKey);
    await _storage.delete(key: _userNameKey);
  }

  Future<bool> hasToken() async {
    final token = await getToken();
    return token != null && token.isNotEmpty;
  }
}
