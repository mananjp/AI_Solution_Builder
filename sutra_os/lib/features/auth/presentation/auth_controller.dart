import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_exceptions.dart';
import '../data/auth_repository.dart';
import '../domain/auth_state.dart';

final authControllerProvider =
    NotifierProvider<AuthController, AuthState>(AuthController.new);

class AuthController extends Notifier<AuthState> {
  late final AuthRepository _repository;
  bool _statusChecked = false;

  @override
  AuthState build() {
    _repository = ref.watch(authRepositoryProvider);
    // Runs once per container lifetime; the router treats `initial` as
    // "unknown, do not redirect yet", so there is no need to re-check on every
    // rebuild of this notifier.
    if (!_statusChecked) {
      _statusChecked = true;
      Future.microtask(checkAuthStatus);
    }
    return const AuthState();
  }

  Future<void> checkAuthStatus() async {
    final token = await _repository.getSavedToken();
    if (token == null || token.isEmpty) {
      state = state.copyWith(
        status: AuthStatus.unauthenticated,
        token: null,
        user: null,
      );
      return;
    }

    try {
      final user = await _repository.getMe();
      state = state.copyWith(
        status: AuthStatus.authenticated,
        user: user,
        token: token,
        errorMessage: null,
      );
    } on ApiException catch (e) {
      if (e.statusCode == 401) {
        // The server actively rejected the token, so the session really is dead.
        await _repository.logout();
        state = state.copyWith(
          status: AuthStatus.unauthenticated,
          token: null,
          user: null,
        );
        return;
      }
      // A cold start or dropped connection says nothing about token validity.
      // Wiping the session here was signing users out on every Render wake-up.
      // Stay signed in and let the individual screens surface their own errors.
      state = state.copyWith(
        status: AuthStatus.authenticated,
        token: token,
        user: null,
        errorMessage: e.message,
        isWarmingUp: e.isColdStart,
      );
    } catch (_) {
      await _repository.logout();
      state = state.copyWith(
        status: AuthStatus.unauthenticated,
        token: null,
        user: null,
      );
    }
  }

  /// Invoked when the API layer sees a 401. Drops the session so the router
  /// redirect fires instead of the UI sitting on a protected route with dead
  /// data.
  Future<void> handleSessionExpired() async {
    if (state.status == AuthStatus.unauthenticated) return;
    await _repository.logout();
    state = const AuthState(status: AuthStatus.unauthenticated);
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
      final token = await _repository.anonymousLogin();
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
