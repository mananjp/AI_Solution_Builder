import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../core/network/json_utils.dart';
import '../../workspace/data/workspace_repository.dart';
import '../../workspace/presentation/workspace_providers.dart';

/// One turn of the SSE conversation, in the order the backend emits it.
class ChatTurn {
  const ChatTurn({
    required this.event,
    this.agent,
    this.sessionId,
    this.solutionId,
    this.buildId,
    this.phase,
    this.step,
    this.totalSteps,
    this.percentage,
    this.message,
    this.simulation,
    this.mode,
    this.llmProvider,
    this.sidecarOnline,
  });

  final String event;
  final String? agent;
  final String? sessionId;
  final String? solutionId;
  final String? buildId;
  final String? phase;
  final int? step;
  final int? totalSteps;
  final int? percentage;
  final String? message;
  final bool? simulation;
  final String? mode;
  final String? llmProvider;
  final bool? sidecarOnline;

  bool get isError => event == 'error';
  bool get isComplete => event == 'complete';

  static ChatTurn fromSse(SseEvent e) {
    return ChatTurn(
      event: e.name,
      agent: e.data['agent']?.toString(),
      sessionId: e.data['session_id']?.toString(),
      solutionId: e.data['solution_id']?.toString(),
      buildId: e.data['build_id']?.toString(),
      phase: e.data['phase']?.toString(),
      step: asIntOrNull(e.data['step']),
      totalSteps: asIntOrNull(e.data['total_steps']),
      percentage: asIntOrNull(e.data['percentage']),
      message: e.data['message']?.toString(),
      simulation: _boolOrNull(e.data['simulation']),
      mode: e.data['mode']?.toString(),
      llmProvider: e.data['llm_provider']?.toString(),
      sidecarOnline: _boolOrNull(e.data['sidecar_online']),
    );
  }

  static bool? _boolOrNull(dynamic value) {
    if (value is bool) return value;
    if (value is String) {
      if (value.toLowerCase() == 'true') return true;
      if (value.toLowerCase() == 'false') return false;
    }
    return null;
  }
}

/// Result of a finished stream, used to refresh build/blueprint state.
class ChatOutcome {
  const ChatOutcome({this.solutionId, this.buildId, this.message});

  final String? solutionId;
  final String? buildId;
  final String? message;
}

/// Streams a chat turn against `POST /api/v1/opencode/chat`.
///
/// The previous Flutter implementation called the blocking `/chat/send`
/// endpoint, waited for the whole turn, and rendered a canned reply, so
/// build_progress phases, the simulation warning, and session continuity were
/// all invisible.
Stream<ChatTurn> streamChatTurn(
  ApiClient client, {
  required String message,
  String? sessionId,
  String? solutionId,
  String? appName,
  String? uploadedContext,
  bool buildRequested = false,
  CancelToken? cancelToken,
}) {
  return client.streamPost(
    ApiEndpoints.openCodeChat,
    data: {
      'message': message,
      if (sessionId != null && sessionId.isNotEmpty) 'session_id': sessionId,
      if (solutionId != null && solutionId.isNotEmpty) 'solution_id': solutionId,
      if (appName != null && appName.isNotEmpty) 'app_name': appName,
      // Parsed text of the attached URL/document. The backend folds this into
      // the prompt context; without it the upload was fetched and discarded.
      if (uploadedContext != null && uploadedContext.isNotEmpty)
        'uploaded_context': uploadedContext,
      'build_requested': buildRequested,
    },
    cancelToken: cancelToken,
  ).map(ChatTurn.fromSse);
}

/// Holds the streaming conversation state for the chat screen.
///
/// Progress events mutate the progress model; assistant text is appended to the
/// transcript; `complete` ends the turn. A transport failure surfaces as an
/// error string instead of silently ending the stream.
class ChatController extends StateNotifier<ChatState> {
  ChatController(this._ref) : super(const ChatState());

  final Ref _ref;
  CancelToken? _cancel;

  @override
  void dispose() {
    _cancel?.cancel('screen closed');
    super.dispose();
  }

  /// Sends [message], optionally requesting a build. Returns the outcome so the
  /// caller can invalidate build/blueprint providers.
  Future<ChatOutcome?> send(
    String message, {
    required bool buildRequested,
    String? appName,
    String? uploadedContext,
  }) async {
    if (state.isStreaming) return null;
    final trimmed = message.trim();
    if (trimmed.isEmpty) return null;

    _cancel?.cancel('superseded');
    _cancel = CancelToken();

    final solutionId = _ref.read(activeSolutionIdProvider);
    final client = _ref.read(apiClientProvider);

    state = state.copyWith(
      isStreaming: true,
      error: null,
      transcript: [
        ...state.transcript,
        ChatMessage(role: ChatRole.user, text: trimmed),
      ],
      progress: const BuildProgress(),
      agent: null,
      capability: null,
    );

    ChatOutcome? outcome;
    var sawTerminalEvent = false;
    try {
      await for (final turn in streamChatTurn(
        client,
        message: trimmed,
        sessionId: state.sessionId,
        solutionId: solutionId,
        appName: appName,
        uploadedContext: uploadedContext,
        buildRequested: buildRequested,
        cancelToken: _cancel,
      )) {
        if (!mounted) break;
        if (turn.isComplete || turn.isError) sawTerminalEvent = true;
        outcome = _apply(turn, outcome);
      }
    } catch (e) {
      if (mounted) {
        state = state.copyWith(
          isStreaming: false,
          error: 'Chat connection failed: $e',
          progress: state.progress.copyWith(active: false),
        );
      }
      return outcome;
    }

    if (!mounted) return outcome;

    // The server can drop a stream without ever sending `complete` (observed
    // live: heartbeats then a clean close). Without this the turn would end in
    // silence and look like the app did nothing.
    final stalled = !sawTerminalEvent && !_cancel!.isCancelled;
    state = state.copyWith(
      isStreaming: false,
      // Do not clobber a real `error` event with null: an `error` turn is
      // terminal, so `sawTerminalEvent` is true and this branch used to erase
      // the only explanation the user got.
      error: stalled
          ? 'The build engine closed the connection before finishing. '
              'Your work may not have been saved — try again.'
          : state.error,
      progress: state.progress.copyWith(active: false),
    );

    // A turn that produced a solution or build must refresh dependent data.
    final newSolutionId = outcome?.solutionId ?? state.solutionId;
    if (newSolutionId != null) {
      _ref.invalidate(workspaceRepositoryProvider);
      _ref.invalidate(solutionDetailProvider(newSolutionId));
    }
    if (outcome?.solutionId != null) {
      // The server may have created a brand new solution. Refresh every list it
      // feeds and point the app at the new solution, otherwise the user lands
      // on a stale selection and cannot see the work they just asked for.
      final newId = outcome!.solutionId!;
      _ref.invalidate(activeSolutionsProvider);
      final workspaceId = _ref.read(activeWorkspaceIdProvider);
      if (workspaceId != null) {
        _ref.invalidate(solutionsListProvider(workspaceId));
      }
      _ref.read(activeSolutionIdProvider.notifier).set(newId);
    }
    if (outcome?.buildId != null && solutionId != null) {
      _ref.invalidate(mvpBuildsProvider(solutionId));
    }

    return outcome;
  }

  ChatOutcome? _apply(ChatTurn turn, ChatOutcome? previous) {
    switch (turn.event) {
      case 'agent_start':
        state = state.copyWith(
          agent: turn.agent ?? turn.message,
          sessionId: turn.sessionId ?? state.sessionId,
          // A brand new solution can be created server-side.
          solutionId: turn.solutionId ?? state.solutionId,
        );
        if (turn.message != null) {
          state = state.copyWith(
            transcript: [
              ...state.transcript,
              ChatMessage(role: ChatRole.system, text: turn.message!),
            ],
          );
        }
        return ChatOutcome(
          solutionId: turn.solutionId ?? previous?.solutionId,
          buildId: previous?.buildId,
          message: previous?.message,
        );

      case 'capability':
        state = state.copyWith(
          capability: ChatCapability(
            simulation: turn.simulation ?? false,
            mode: turn.mode ?? 'unknown',
            llmProvider: turn.llmProvider,
            sidecarOnline: turn.sidecarOnline ?? false,
          ),
        );
        return previous;

      case 'build_progress':
        state = state.copyWith(
          progress: BuildProgress(
            active: true,
            phase: turn.phase,
            step: turn.step,
            totalSteps: turn.totalSteps,
            percentage: turn.percentage,
            message: turn.message,
          ),
        );
        return previous;

      case 'message':
        if (turn.message != null && turn.message!.isNotEmpty) {
          state = state.copyWith(
            transcript: [
              ...state.transcript,
              ChatMessage(role: ChatRole.assistant, text: turn.message!),
            ],
            sessionId: turn.sessionId ?? state.sessionId,
          );
        }
        return previous;

      case 'error':
        state = state.copyWith(
          error: turn.message ?? 'The build engine reported an error.',
        );
        return previous;

      case 'complete':
        state = state.copyWith(
          sessionId: turn.sessionId ?? state.sessionId,
          solutionId: turn.solutionId ?? state.solutionId,
        );
        if (turn.message != null && turn.message!.isNotEmpty) {
          state = state.copyWith(
            transcript: [
              ...state.transcript,
              ChatMessage(role: ChatRole.assistant, text: turn.message!),
            ],
          );
        }
        return ChatOutcome(
          solutionId: turn.solutionId,
          buildId: turn.buildId ?? previous?.buildId,
          message: turn.message,
        );

      default:
        return previous;
    }
  }

  void stop() {
    _cancel?.cancel('stopped by user');
    if (mounted) {
      state = state.copyWith(
        isStreaming: false,
        progress: state.progress.copyWith(active: false),
      );
    }
  }
}

enum ChatRole { user, assistant, system }

class ChatMessage {
  const ChatMessage({required this.role, required this.text});

  final ChatRole role;
  final String text;
}

class BuildProgress {
  const BuildProgress({
    this.active = false,
    this.phase,
    this.step,
    this.totalSteps,
    this.percentage,
    this.message,
  });

  final bool active;
  final String? phase;
  final int? step;
  final int? totalSteps;
  final int? percentage;
  final String? message;

  double get fraction => ((percentage ?? 0) / 100).clamp(0.0, 1.0);

  BuildProgress copyWith({
    bool? active,
    String? phase,
    int? step,
    int? totalSteps,
    int? percentage,
    String? message,
  }) {
    return BuildProgress(
      active: active ?? this.active,
      phase: phase ?? this.phase,
      step: step ?? this.step,
      totalSteps: totalSteps ?? this.totalSteps,
      percentage: percentage ?? this.percentage,
      message: message ?? this.message,
    );
  }
}

class ChatCapability {
  const ChatCapability({
    required this.simulation,
    required this.mode,
    this.llmProvider,
    this.sidecarOnline = false,
  });

  final bool simulation;
  final String mode;
  final String? llmProvider;
  final bool sidecarOnline;
}

class ChatState {
  const ChatState({
    this.transcript = const [],
    this.isStreaming = false,
    this.error,
    this.sessionId,
    this.solutionId,
    this.agent,
    this.capability,
    this.progress = const BuildProgress(),
  });

  final List<ChatMessage> transcript;
  final bool isStreaming;
  final String? error;
  final String? sessionId;
  final String? solutionId;
  final String? agent;
  final ChatCapability? capability;
  final BuildProgress progress;

  ChatState copyWith({
    List<ChatMessage>? transcript,
    bool? isStreaming,
    Object? error = _sentinel,
    Object? sessionId = _sentinel,
    Object? solutionId = _sentinel,
    Object? agent = _sentinel,
    Object? capability = _sentinel,
    BuildProgress? progress,
  }) {
    return ChatState(
      transcript: transcript ?? this.transcript,
      isStreaming: isStreaming ?? this.isStreaming,
      error: identical(error, _sentinel) ? this.error : error as String?,
      sessionId:
          identical(sessionId, _sentinel) ? this.sessionId : sessionId as String?,
      solutionId: identical(solutionId, _sentinel)
          ? this.solutionId
          : solutionId as String?,
      agent: identical(agent, _sentinel) ? this.agent : agent as String?,
      capability: identical(capability, _sentinel)
          ? this.capability
          : capability as ChatCapability?,
      progress: progress ?? this.progress,
    );
  }

  static const _sentinel = Object();
}

final chatControllerProvider =
    StateNotifierProvider<ChatController, ChatState>((ref) {
  return ChatController(ref);
});
