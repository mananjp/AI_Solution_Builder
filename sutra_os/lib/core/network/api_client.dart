import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../storage/secure_storage_service.dart';
import 'api_endpoints.dart';
import 'api_exceptions.dart';

/// Broadcasts session-expiry so the app can drop to the unauthenticated route.
///
/// The API client cannot write to [AuthState] directly: that would create an
/// import cycle (auth -> repository -> api client -> auth). A stream breaks it.
class SessionEvents {
  final _controller = StreamController<void>.broadcast();

  Stream<void> get unauthorized => _controller.stream;

  bool _signalled = false;

  void reportUnauthorized() {
    // Collapse a burst of parallel 401s into a single event.
    if (_signalled) return;
    _signalled = true;
    _controller.add(null);
    Future<void>.delayed(const Duration(milliseconds: 500), () {
      _signalled = false;
    });
  }

  void dispose() => _controller.close();
}

final sessionEventsProvider = Provider<SessionEvents>((ref) {
  final events = SessionEvents();
  ref.onDispose(events.dispose);
  return events;
});

/// Exposes [SessionEvents.unauthorized] as a provider so `ref.listen` fires on
/// every emission. Listening to [sessionEventsProvider] directly would not work:
/// that provider's value never changes, so its listener would never run.
final sessionExpiredProvider = StreamProvider<void>((ref) {
  return ref.watch(sessionEventsProvider).unauthorized;
});

final apiClientProvider = Provider<ApiClient>((ref) {
  final storage = ref.watch(secureStorageServiceProvider);
  final sessionEvents = ref.watch(sessionEventsProvider);
  return ApiClient(storageService: storage, sessionEvents: sessionEvents);
});

class ApiClient {
  final Dio _dio;
  final SecureStorageService _storageService;
  final SessionEvents _sessionEvents;

  /// Mirror of the persisted token.
  ///
  /// Reading from secure storage costs a platform-channel round trip per
  /// request (and Android's first read can block for seconds). Caching it here
  /// keeps one round trip per session instead of one per call.
  String? _cachedToken;
  bool _tokenCacheLoaded = false;

  ApiClient({
    required SecureStorageService storageService,
    SessionEvents? sessionEvents,
    Dio? dio,
  })  : _storageService = storageService,
        _sessionEvents = sessionEvents ?? SessionEvents(),
        _dio = dio ??
            Dio(
              BaseOptions(
                baseUrl: ApiEndpoints.baseUrl,
                connectTimeout: const Duration(seconds: 65),
                receiveTimeout: const Duration(seconds: 65),
                sendTimeout: const Duration(seconds: 65),
                headers: {
                  'Content-Type': 'application/json',
                  'Accept': 'application/json',
                },
              ),
            ) {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await _token();
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          if (kDebugMode) {
            debugPrint('[API] => ${options.method} ${options.uri}');
          }
          return handler.next(options);
        },
        onResponse: (response, handler) {
          if (kDebugMode) {
            debugPrint('[API] <= ${response.statusCode} ${response.requestOptions.uri}');
          }
          return handler.next(response);
        },
        onError: (DioException error, handler) async {
          if (kDebugMode) {
            debugPrint('[API] ERR: ${error.type} | ${error.response?.statusCode} | ${error.requestOptions.uri}');
          }
          if (error.response?.statusCode == 401) {
            await clearSession();
            _sessionEvents.reportUnauthorized();
          }
          return handler.next(error);
        },
      ),
    );

    // The free-tier host sleeps after inactivity and answers the first request
    // of a new session only once it has booted. One retry turns that into a
    // short pause instead of a hard failure.
    _dio.interceptors.add(
      InterceptorsWrapper(
        onError: (DioException error, handler) async {
          final isColdStart = error.type == DioExceptionType.connectionError ||
              error.type == DioExceptionType.connectionTimeout;
          final alreadyRetried = error.requestOptions.extra['cold_start_retry'] == true;

          if (!isColdStart || alreadyRetried) return handler.next(error);

          if (kDebugMode) {
            debugPrint('[API] cold start detected, retrying once after 2s');
          }
          error.requestOptions.extra['cold_start_retry'] = true;
          await Future<void>.delayed(const Duration(seconds: 2));
          try {
            final response = await _dio.fetch<Object?>(error.requestOptions);
            return handler.resolve(response);
          } on DioException catch (e) {
            return handler.next(e);
          }
        },
      ),
    );
  }

  Dio get dio => _dio;

  Future<String?> _token() async {
    if (!_tokenCacheLoaded) {
      try {
        _cachedToken = await _storageService.getToken();
      } catch (e) {
        // A keystore failure must not break every request; the call goes out
        // unauthenticated and the server answers 401 as it should.
        debugPrint('[API] token read failed: $e');
        _cachedToken = null;
      }
      _tokenCacheLoaded = true;
    }
    return _cachedToken;
  }

  /// Call after any write that changes the stored token.
  void updateToken(String? token) {
    _cachedToken = token;
    _tokenCacheLoaded = true;
  }

  /// Drops the cached token and the persisted session. The app is expected to
  /// react to [SessionEvents.unauthorized] and route back to sign-in.
  Future<void> clearSession() async {
    _cachedToken = null;
    _tokenCacheLoaded = true;
    try {
      await _storageService.clearAll();
    } catch (e) {
      debugPrint('[API] session clear failed: $e');
    }
  }

  Future<Response<T>> get<T>(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
    CancelToken? cancelToken,
  }) async {
    try {
      return await _dio.get<T>(
        path,
        queryParameters: queryParameters,
        options: options,
        cancelToken: cancelToken,
      );
    } on DioException catch (e) {
      throw ApiException.fromDioException(e);
    }
  }

  Future<Response<T>> post<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
    CancelToken? cancelToken,
  }) async {
    try {
      return await _dio.post<T>(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
        cancelToken: cancelToken,
      );
    } on DioException catch (e) {
      throw ApiException.fromDioException(e);
    }
  }

  Future<Response<T>> patch<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
    CancelToken? cancelToken,
  }) async {
    try {
      return await _dio.patch<T>(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
        cancelToken: cancelToken,
      );
    } on DioException catch (e) {
      throw ApiException.fromDioException(e);
    }
  }

  Future<Response<T>> put<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
    CancelToken? cancelToken,
  }) async {
    try {
      return await _dio.put<T>(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
        cancelToken: cancelToken,
      );
    } on DioException catch (e) {
      throw ApiException.fromDioException(e);
    }
  }

  Future<Response<T>> delete<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
    CancelToken? cancelToken,
  }) async {
    try {
      return await _dio.delete<T>(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
        cancelToken: cancelToken,
      );
    } on DioException catch (e) {
      throw ApiException.fromDioException(e);
    }
  }

  /// Fetches a binary body (build archives, exported artifacts) as raw bytes.
  ///
  /// The interceptors still apply, so the bearer token and the cold-start retry
  /// work the same as for JSON calls.
  Future<Uint8List> download(
    String path, {
    Map<String, dynamic>? queryParameters,
    CancelToken? cancelToken,
  }) async {
    try {
      final response = await _dio.get<List<int>>(
        path,
        queryParameters: queryParameters,
        options: Options(responseType: ResponseType.bytes),
        cancelToken: cancelToken,
      );
      final data = response.data;
      if (data == null) return Uint8List(0);
      return data is Uint8List ? data : Uint8List.fromList(data);
    } on DioException catch (e) {
      throw ApiException.fromDioException(e);
    }
  }

  /// Opens a Server-Sent Events stream and yields decoded frames.
  ///
  /// The backend emits `event:`/`data:` lines; this reassembles them into
  /// [SseEvent]s, tolerating multi-line data and frames split across network
  /// chunks. `complete` and `error` end the stream.
  Stream<SseEvent> streamPost(
    String path, {
    Map<String, dynamic>? data,
    CancelToken? cancelToken,
  }) async* {
    final token = await _token();
    final request = RequestOptions(
      path: path,
      baseUrl: _dio.options.baseUrl,
      method: 'POST',
      data: data,
      headers: {
        'Content-Type': Headers.jsonContentType,
        'Accept': 'text/event-stream',
        if (token != null && token.isNotEmpty)
          'Authorization': 'Bearer $token',
      },
      responseType: ResponseType.stream,
      // A full build streams for minutes. The normal 65s receive timeout would
      // sever the connection mid-synthesis; the server sends `: ping`
      // heartbeats, and the user can abort explicitly via the cancel token.
      receiveTimeout: null,
      cancelToken: cancelToken,
    );

    // For `ResponseType.stream` Dio's transformer hands back the `ResponseBody`
    // itself, not a `Stream`. Fetching it as `Stream<Uint8List>` throws a
    // cast error that surfaces only as an opaque "unknown" network failure.
    final ResponseBody body;
    try {
      final response = await _dio.fetch<ResponseBody>(request);
      body = response.data ??
          ResponseBody.fromString('', 200, headers: {
            Headers.contentTypeHeader: [Headers.jsonContentType],
          });
    } on DioException catch (e) {
      throw ApiException.fromDioException(e);
    }

    var eventName = 'message';
    final dataLines = <String>[];

    // Chunks respect neither line nor character boundaries: one `data:` line
    // can be split across reads, and a multi-byte character can straddle them.
    // Buffer raw BYTES and only ever cut at 0x0A, which can never appear
    // inside a multi-byte sequence, so a cut is always a safe character
    // boundary. Decoding per chunk instead would truncate a split character,
    // and `startChunkedConversion` is unusable here because the default
    // `Converter` implementation buffers everything until close().
    var buffer = <int>[];

    await for (final chunk in body.stream) {
      buffer.addAll(chunk);

      var lastNewline = -1;
      for (var i = buffer.length - 1; i >= 0; i--) {
        if (buffer[i] == 0x0A) {
          lastNewline = i;
          break;
        }
      }
      if (lastNewline < 0) continue;

      final complete = utf8.decode(
        buffer.sublist(0, lastNewline),
        allowMalformed: true,
      );
      buffer = buffer.sublist(lastNewline + 1);

      for (final raw in complete.split('\n')) {
        final line = raw.endsWith('\r') ? raw.substring(0, raw.length - 1) : raw;
        if (line.isEmpty) {
          if (dataLines.isNotEmpty) {
            yield SseEvent(eventName, _decodeFrame(dataLines.join('\n')));
            dataLines.clear();
          }
          eventName = 'message';
        } else if (line.startsWith('event:')) {
          eventName = line.substring(6).trim();
        } else if (line.startsWith('data:')) {
          dataLines.add(line.substring(5).trimLeft());
        }
        // `id:`/`retry:` are not used by this backend.
      }
    }
    // A trailing line with no final newline, plus anything left in the buffer.
    if (buffer.isNotEmpty) {
      final tail = utf8.decode(buffer, allowMalformed: true);
      for (final raw in tail.split('\n')) {
        final line =
            raw.endsWith('\r') ? raw.substring(0, raw.length - 1) : raw;
        if (line.isEmpty) {
          if (dataLines.isNotEmpty) {
            yield SseEvent(eventName, _decodeFrame(dataLines.join('\n')));
            dataLines.clear();
          }
          eventName = 'message';
        } else if (line.startsWith('event:')) {
          eventName = line.substring(6).trim();
        } else if (line.startsWith('data:')) {
          dataLines.add(line.substring(5).trimLeft());
        }
      }
    }
    // A stream that ends without an explicit `complete` frame is still a
    // completed response; surface the trailing data if there is any.
    if (dataLines.isNotEmpty) {
      yield SseEvent(eventName, _decodeFrame(dataLines.join('\n')));
    }
  }

  Map<String, dynamic> _decodeFrame(String raw) {
    if (raw.isEmpty) return const {};
    try {
      final decoded = jsonDecode(raw);
      if (decoded is Map) {
        return decoded.map((k, v) => MapEntry(k.toString(), v));
      }
      return {'value': decoded};
    } catch (_) {
      // Not every frame is JSON; keep the text rather than dropping it.
      return {'raw': raw};
    }
  }
}

/// One decoded Server-Sent Event frame.
class SseEvent {
  final String name;
  final Map<String, dynamic> data;

  const SseEvent(this.name, this.data);

  bool get isComplete => name == 'complete';
  bool get isError => name == 'error';

  @override
  String toString() => 'SseEvent($name, $data)';
}


