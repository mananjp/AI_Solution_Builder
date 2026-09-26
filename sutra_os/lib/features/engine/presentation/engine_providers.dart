import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/presentation/auth_controller.dart';
import '../data/engine_repository.dart';
import '../domain/engine_models.dart';

/// Polls [fetch] immediately and then every [interval], cancelling cleanly when
/// the provider is disposed.
///
/// The web app drives the same three loops with `setInterval` (engine health
/// every 15s, resource gauges every 5s, active builds every 3s). A plain
/// `FutureProvider` would fetch exactly once, so a long-lived dashboard would
/// silently show a stale reading forever.
StreamProvider<T> pollingProvider<T>(
  Future<T> Function(Ref ref) fetch, {
  required Duration interval,
}) {
  return StreamProvider<T>((ref) async* {
    final isAuthenticated = ref.watch(
      authControllerProvider.select((s) => s.isAuthenticated),
    );
    if (!isAuthenticated) return;

    // A failed poll must not tear down the stream; the last good reading stays
    // on screen and the next tick retries.
    Timer? timer;
    final controller = StreamController<T>();
    controller.onListen = () {
      Future<void> tick() async {
        try {
          controller.add(await fetch(ref));
        } catch (_) {
          // Ignored on purpose: see above.
        }
        if (!controller.isClosed) {
          timer = Timer(interval, tick);
        }
      }

      tick();
    };
    controller.onCancel = () {
      timer?.cancel();
      timer = null;
    };

    ref.onDispose(() {
      timer?.cancel();
      timer = null;
      if (!controller.isClosed) {
        controller.close();
      }
    });

    yield* controller.stream;
  });
}

/// Engine reachability, refreshed every 15s like the web dashboard.
final engineHealthProvider = pollingProvider<EngineHealthModel>(
  (ref) => ref.read(engineRepositoryProvider).fetchHealth(),
  interval: const Duration(seconds: 15),
);

/// Host CPU / memory / disk, refreshed every 5s like the web resource gauges.
final systemResourcesProvider = pollingProvider<SystemResourcesModel>(
  (ref) => ref.read(engineRepositoryProvider).fetchResources(),
  interval: const Duration(seconds: 5),
);

/// On-demand self-check; only run when the user asks for it.
final engineDiagnosisProvider =
    FutureProvider<EngineDiagnosisModel>((ref) async {
  return ref.read(engineRepositoryProvider).diagnose();
});
