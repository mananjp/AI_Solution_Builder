import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_exceptions.dart';
import '../data/auth_repository.dart';
import '../domain/auth_state.dart';

final authControllerProvider =
    NotifierProvider<AuthController, AuthState>(AuthController.new);

class AuthController extends Notifier<AuthState> {
  late final AuthRepository _repository;

  @override
  AuthState build() {
    _repository = ref.watch(authRepositoryProvider);
    Future.microtask(() => checkAuthStatus());
    return const AuthState();
  }

  Future<void> checkAuthStatus() async {
    final token = await _repository.getSavedToken();
    if (token == null || token.isEmpty) {
      state = state.copyWith(status: AuthStatus.unauthenticated);
      return;
    }

    try {
      final user = await _repository.getMe();
      state = state.copyWith(
        status: AuthStatus.authenticated,
        user: user,
        token: token,
      );
    } catch (e) {
      await _repository.logout();
      state = state.copyWith(
        status: AuthStatus.unauthenticated,
        token: null,
        user: null,
      );
    }
  }

  Future<bool> login(String email, String password) async {
    state = state.copyWith(
      status: AuthStatus.loading,
      errorMessage: null,
      isWarmingUp: false,
    );

    try {
      final token = await _repository.login(email: email, password: password);
      final user = await _repository.getMe();
      state = state.copyWith(
        status: AuthStatus.authenticated,
        token: token,
        user: user,
        errorMessage: null,
      );
      return true;
    } on ApiException catch (e) {
      state = state.copyWith(
        status: AuthStatus.error,
        errorMessage: e.message,
        isWarmingUp: e.isColdStart,
      );
      return false;
    } catch (e) {
      state = state.copyWith(
        status: AuthStatus.error,
        errorMessage: 'An unexpected error occurred. Please try again.',
      );
      return false;
    }
  }

  Future<bool> register({
    required String email,
    required String fullName,
    required String password,
    required String orgName,
  }) async {
    state = state.copyWith(
      status: AuthStatus.loading,
      errorMessage: null,
      isWarmingUp: false,
    );

    try {
      final token = await _repository.register(
        email: email,
        fullName: fullName,
        password: password,
        orgName: orgName,
      );
      final user = await _repository.getMe();
      state = state.copyWith(
        status: AuthStatus.authenticated,
        token: token,
        user: user,
        errorMessage: null,
      );
      return true;
    } on ApiException catch (e) {
      state = state.copyWith(
        status: AuthStatus.error,
        errorMessage: e.message,
        isWarmingUp: e.isColdStart,
      );
      return false;
    } catch (e) {
      state = state.copyWith(
        status: AuthStatus.error,
        errorMessage: 'Registration failed. Please check your credentials.',
      );
      return false;
    }
  }

  Future<bool> loginAsGuest() async {
    state = state.copyWith(
      status: AuthStatus.loading,
      errorMessage: null,
      isWarmingUp: false,
    );

    try {
      final data = await _repository.anonymousLogin();
      final token = data['access_token'] as String;
      final user = await _repository.getMe();
      state = state.copyWith(
        status: AuthStatus.authenticated,
        token: token,
        user: user,
        errorMessage: null,
      );
      return true;
    } on ApiException catch (e) {
      state = state.copyWith(
        status: AuthStatus.error,
        errorMessage: e.message,
        isWarmingUp: e.isColdStart,
      );
      return false;
    } catch (e) {
      state = state.copyWith(
        status: AuthStatus.error,
        errorMessage: 'Failed to initialize anonymous workspace.',
      );
      return false;
    }
  }

  Future<void> logout() async {
    await _repository.logout();
    state = const AuthState(status: AuthStatus.unauthenticated);
  }
}
