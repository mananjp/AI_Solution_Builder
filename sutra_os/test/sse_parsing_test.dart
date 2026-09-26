import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sutra_os/core/network/api_client.dart';
import 'package:sutra_os/core/storage/secure_storage_service.dart';
import 'package:sutra_os/features/chat/application/chat_controller.dart';

/// Streams a canned SSE body, but hands it out in caller-chosen chunk sizes so
/// a test can prove the parser tolerates frames split mid-line and mid-UTF8.
class _ChunkedSseAdapter implements HttpClientAdapter {
  _ChunkedSseAdapter(this.frames, this.chunkSize);

  /// Each entry is one raw text chunk as the server wrote it.
  final List<String> frames;
  final int chunkSize;

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final bytes = utf8.encode(frames.join());
    Stream<Uint8List> body() async* {
      for (var i = 0; i < bytes.length; i += chunkSize) {
        final end =
            (i + chunkSize > bytes.length) ? bytes.length : i + chunkSize;
        yield Uint8List.fromList(bytes.sublist(i, end));
        // Give the consumer a real chance to interleave, like a socket would.
        await Future<void>.delayed(Duration.zero);
      }
    }

    return ResponseBody(
      body(),
      200,
      headers: {
        Headers.contentTypeHeader: ['text/event-stream'],
      },
    );
  }
}

class _InMemorySecureStorage extends FlutterSecureStorage {
  final Map<String, String> values = {};

  @override
  Future<void> write({
    required String key,
    required String? value,
    AndroidOptions? aOptions,
    IOSOptions? iOptions,
    LinuxOptions? lOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
    WebOptions? webOptions,
  }) async =>
      values[key] = value ?? '';

  @override
  Future<String?> read({
    required String key,
    AndroidOptions? aOptions,
    IOSOptions? iOptions,
    LinuxOptions? lOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
    WebOptions? webOptions,
  }) async =>
      values[key];
}

/// The exact event sequence `POST /api/v1/opencode/chat` emits, in order.
List<String> _serverFrames() => [
      'event: agent_start\ndata: {"agent":"opencode","session_id":"sess-1",'
          '"solution_id":"sol-1","message":"Connected to the OpenCode sidecar..."}\n\n',
      'event: capability\ndata: {"sidecar_online":true,"llm_provider":"ollama",'
          '"llm_authenticated":true,"simulation":false,'
          '"mode":"opencode-sidecar"}\n\n',
      'event: build_progress\ndata: {"phase":"analyzing","step":1,'
          '"total_steps":7,"percentage":15,"message":"Synthesizing domain '
          'architecture for Café Ordering System..."}\n\n',
      'event: build_progress\ndata: {"phase":"packaging","step":6,'
          '"total_steps":7,"percentage":90,"message":"Packaging production '
          'archive (.zip) and saving build artifacts..."}\n\n',
      'event: message\ndata: {"role":"assistant","message":"Blueprint is ready '
          'for review.","session_id":"sess-1"}\n\n',
      'event: complete\ndata: {"status":"complete","message":"Build complete! '
          '42 files generated.","session_id":"sess-1","solution_id":"sol-1",'
          '"build_id":"bld-9"}\n\n',
    ];

Future<List<ChatTurn>> _collect(int chunkSize) async {
  final dio = Dio(BaseOptions(baseUrl: 'https://test.local'))
    ..httpClientAdapter = _ChunkedSseAdapter(_serverFrames(), chunkSize);
  final client = ApiClient(
    storageService:
        SecureStorageService(storage: _InMemorySecureStorage()),
    dio: dio,
  );

  final turns = <ChatTurn>[];
  await for (final event
      in client.streamPost('/api/v1/opencode/chat', data: {'message': 'go'})) {
    turns.add(ChatTurn.fromSse(event));
  }
  return turns;
}

void main() {
  group('SSE parsing', () {
    test('reassembles frames delivered in arbitrarily small chunks', () async {
      // 7 bytes at a time splits both lines and multi-byte characters. The
      // previous per-chunk LineSplitter treated a partial trailing line as a
      // complete line, so every frame after the first arrived as garbage.
      final turns = await _collect(7);

      expect(
        turns.map((t) => t.event).toList(),
        [
          'agent_start',
          'capability',
          'build_progress',
          'build_progress',
          'message',
          'complete',
        ],
        reason: 'every event must survive chunk-boundary splitting',
      );

      expect(turns[0].agent, 'opencode');
      expect(turns[0].sessionId, 'sess-1');
      expect(turns[0].message, 'Connected to the OpenCode sidecar...');

      expect(turns[1].simulation, isFalse);
      expect(turns[1].mode, 'opencode-sidecar');
      expect(turns[1].llmProvider, 'ollama');
      expect(turns[1].sidecarOnline, isTrue);

      expect(turns[2].phase, 'analyzing');
      expect(turns[2].step, 1);
      expect(turns[2].totalSteps, 7);
      expect(turns[2].percentage, 15);

      expect(turns[3].phase, 'packaging');
      expect(turns[3].percentage, 90);

      expect(turns[4].message, 'Blueprint is ready for review.');

      expect(turns[5].buildId, 'bld-9');
      expect(turns[5].solutionId, 'sol-1');
      expect(turns[5].isComplete, isTrue);
    });

    test('parses identically when each frame arrives whole', () async {
      final whole = await _collect(1 << 20);
      final split = await _collect(7);
      expect(
        split.map((t) => '${t.event}:${t.message ?? t.phase ?? t.buildId}'),
        whole.map((t) => '${t.event}:${t.message ?? t.phase ?? t.buildId}'),
      );
    });

    test('flags a simulation-mode capability event', () async {
      final dio = Dio(BaseOptions(baseUrl: 'https://test.local'))
        ..httpClientAdapter = _ChunkedSseAdapter(
          [
            'event: capability\ndata: {"sidecar_online":false,'
                '"llm_provider":"mock","llm_authenticated":false,'
                '"simulation":true,"mode":"integrated-synthesizer"}\n\n',
            'event: error\ndata: {"message":"builder unavailable"}\n\n',
          ],
          5,
        );
      final client = ApiClient(
        storageService:
            SecureStorageService(storage: _InMemorySecureStorage()),
        dio: dio,
      );

      final turns = <ChatTurn>[];
      await for (final event
          in client.streamPost('/api/v1/opencode/chat', data: {'message': 'go'})) {
        turns.add(ChatTurn.fromSse(event));
      }

      expect(turns, hasLength(2));
      expect(turns[0].simulation, isTrue);
      expect(turns[0].mode, 'integrated-synthesizer');
      expect(turns[1].isError, isTrue);
      expect(turns[1].message, 'builder unavailable');
    });
  });
}
