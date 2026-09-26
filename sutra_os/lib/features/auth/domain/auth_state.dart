import 'user_model.dart';

enum AuthStatus { initial, loading, authenticated, unauthenticated, error }

/// Sentinel distinguishing "argument omitted" from an explicit `null`.
const Object _unset = Object();

class AuthState {
  final AuthStatus status;
  final UserModel? user;
  final String? token;
  final String? errorMessage;
  final bool isWarmingUp;

  const AuthState({
    this.status = AuthStatus.initial,
    this.user,
    this.token,
    this.errorMessage,
    this.isWarmingUp = false,
  });

  bool get isAuthenticated => status == AuthStatus.authenticated && token != null;
  bool get isLoading => status == AuthStatus.loading;

  /// Unlike a plain `user ?? this.user`, this actually clears a field when
  /// `null` is passed. Signing out has to be able to drop the cached user, and
  /// the old implementation silently kept it.
  AuthState copyWith({
    AuthStatus? status,
    Object? user = _unset,
    Object? token = _unset,
    Object? errorMessage = _unset,
    bool? isWarmingUp,
  }) {
    return AuthState(
      status: status ?? this.status,
      user: identical(user, _unset) ? this.user : user as UserModel?,
      token: identical(token, _unset) ? this.token : token as String?,
      errorMessage: identical(errorMessage, _unset)
          ? this.errorMessage
          : errorMessage as String?,
      isWarmingUp: isWarmingUp ?? this.isWarmingUp,
    );
  }
}
