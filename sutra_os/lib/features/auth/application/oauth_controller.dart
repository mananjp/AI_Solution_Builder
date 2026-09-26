import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/network/json_utils.dart';
import '../data/auth_repository.dart';
import '../presentation/auth_controller.dart';


/// Which social providers the backend actually has configured.
class OAuthProviderInfo {
  const OAuthProviderInfo({required this.providers, required this.allowAnonymous});

  final List<String> providers;
  final bool allowAnonymous;

  factory OAuthProviderInfo.fromJson(Map<String, dynamic> json) {
    return OAuthProviderInfo(
      providers: asList(json['providers'])
          .map((e) => e?.toString() ?? '')
          .where((e) => e.isNotEmpty)
          .toList(),
      allowAnonymous: asBool(json['allow_anonymous']),
    );
  }
}

final oauthProvidersProvider =
    FutureProvider<OAuthProviderInfo>((ref) async {
  final response = await ref.read(authRepositoryProvider).oauthProviders();
  return OAuthProviderInfo.fromJson(asMap(response.data));
});

class OAuthCallbackState {
  const OAuthCallbackState({
    this.isCompleting = false,
    this.error,
    this.succeeded = false,
  });

  final bool isCompleting;
  final String? error;

  /// Set once the code exchange landed a real session. The screen watches this
  /// to navigate on; without it the user sat on `/callback` forever, because a
  /// successful exchange produced neither an error nor a route change.
  final bool succeeded;

  OAuthCallbackState copyWith({
    bool? isCompleting,
    String? error,
    bool? succeeded,
  }) {
    return OAuthCallbackState(
      isCompleting: isCompleting ?? this.isCompleting,
      error: error ?? this.error,
      succeeded: succeeded ?? this.succeeded,
    );
  }
}

class OAuthCallbackController extends StateNotifier<OAuthCallbackState> {
  OAuthCallbackController(this._ref) : super(const OAuthCallbackState());

  final Ref _ref;


  /// Opens the provider's authorization URL in the system browser. The
  /// provider redirects back to `/callback?provider=...&code=...`, which
  /// `complete` handles.
  Future<void> authorize(String provider) async {
    try {
      final response =
          await _ref.read(authRepositoryProvider).oauthAuthorize(provider);
      final url = asString(asMap(response.data)['authorization_url']);
      if (url.isEmpty) {
        state = state.copyWith(error: 'No authorization URL was returned.');
        return;
      }
      final uri = Uri.parse(url);
      final launched =
          await launchUrl(uri, mode: LaunchMode.externalApplication);
      if (!launched) {
        state = state.copyWith(error: 'Could not open the browser.');
      }
    } catch (e) {
      state = state.copyWith(error: '$e');
    }
  }

  /// Exchanges the returned code for a session.
  Future<void> complete(String provider, String code, String? state) async {
    this.state = const OAuthCallbackState(isCompleting: true);
    try {
      await _ref
          .read(authRepositoryProvider)
          .oauthCallback(provider, code, state: state);
      // The exchange stores the token, but the app's auth state is still
      // `unauthenticated`, so every protected route would bounce the user back
      // to /login. Re-check the session to hydrate AuthState before the screen
      // navigates.
      await _ref.read(authControllerProvider.notifier).checkAuthStatus();
      this.state = const OAuthCallbackState(succeeded: true);
    } catch (e) {
      this.state = OAuthCallbackState(error: '$e');
    }
  }
}


final oauthCallbackProvider =
    StateNotifierProvider<OAuthCallbackController, OAuthCallbackState>((ref) {
  return OAuthCallbackController(ref);
});

