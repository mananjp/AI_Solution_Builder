import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

import '../../features/workspace/data/workspace_repository.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import '../theme/app_text_styles.dart';

/// Audio recording & Whisper voice transcription button.
///
/// Mirrors the Next.js web frontend's `VoiceInputButton`.
/// Records speech notes from the device microphone and uploads them to
/// `POST /api/v1/upload/audio` for transcription.
class VoiceInputButton extends ConsumerStatefulWidget {
  const VoiceInputButton({
    super.key,
    required this.onTranscribed,
    this.disabled = false,
    this.language,
    this.compact = true,
  });

  final void Function(String text, String? detectedLanguage) onTranscribed;
  final bool disabled;
  final String? language;
  final bool compact;

  @override
  ConsumerState<VoiceInputButton> createState() => _VoiceInputButtonState();
}

class _VoiceInputButtonState extends ConsumerState<VoiceInputButton>
    with SingleTickerProviderStateMixin {
  late final AudioRecorder _recorder;
  bool _isRecording = false;
  bool _isTranscribing = false;
  int _recordSeconds = 0;
  Timer? _timer;
  String? _recordingPath;
  StreamSubscription<Uint8List>? _recordSub;
  final List<int> _webAudioBytes = [];
  late final AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _recorder = AudioRecorder();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
      lowerBound: 0.8,
      upperBound: 1.2,
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _timer?.cancel();
    _recordSub?.cancel();
    _pulseController.dispose();
    _recorder.dispose();
    super.dispose();
  }

  Future<void> _startRecording() async {
    if (widget.disabled || _isTranscribing) return;

    try {
      final hasPerm = await _recorder.hasPermission();
      if (!hasPerm) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Microphone permission not granted.'),
              backgroundColor: AppColors.statusErrorRed,
            ),
          );
        }
        return;
      }

      setState(() {
        _isRecording = true;
        _recordSeconds = 0;
        _webAudioBytes.clear();
      });

      _timer?.cancel();
      _timer = Timer.periodic(const Duration(seconds: 1), (_) {
        if (mounted) {
          setState(() => _recordSeconds++);
        }
      });

      if (kIsWeb) {
        final stream = await _recorder.startStream(
          const RecordConfig(encoder: AudioEncoder.opus),
        );
        _recordSub = stream.listen((chunk) {
          _webAudioBytes.addAll(chunk);
        });
      } else {
        final tempDir = await getTemporaryDirectory();
        final path =
            '${tempDir.path}/sutra_voice_${DateTime.now().millisecondsSinceEpoch}.m4a';
        _recordingPath = path;
        await _recorder.start(
          const RecordConfig(encoder: AudioEncoder.aacLc),
          path: path,
        );
      }
    } catch (e) {
      _stopTimer();
      setState(() => _isRecording = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Could not start microphone: $e'),
            backgroundColor: AppColors.statusErrorRed,
          ),
        );
      }
    }
  }

  Future<void> _stopRecording() async {
    _stopTimer();
    setState(() {
      _isRecording = false;
      _isTranscribing = true;
    });

    try {
      final path = await _recorder.stop();
      await _recordSub?.cancel();
      _recordSub = null;

      final repo = ref.read(workspaceRepositoryProvider);
      final Map<String, dynamic> result;

      if (kIsWeb) {
        if (_webAudioBytes.isEmpty) {
          throw Exception('No audio captured.');
        }
        result = await repo.uploadAudio(
          filename: 'voice_note.webm',
          bytes: _webAudioBytes,
          language: widget.language,
        );
      } else {
        final filePath = path ?? _recordingPath;
        if (filePath == null) {
          throw Exception('Recording path was not generated.');
        }
        result = await repo.uploadAudio(
          filename: 'voice_note.m4a',
          filePath: filePath,
          language: widget.language,
        );
      }

      final transcription = result['transcription'] as String? ??
          result['extracted_context'] as String? ??
          result['text'] as String?;

      final detectedLang = result['detected_language'] as String?;

      if (transcription != null && transcription.trim().isNotEmpty) {
        widget.onTranscribed(transcription.trim(), detectedLang);
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('No speech recognized in recording.'),
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Voice transcription failed: $e'),
            backgroundColor: AppColors.statusErrorRed,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isTranscribing = false);
      }
    }
  }

  void _stopTimer() {
    _timer?.cancel();
    _timer = null;
  }

  String _formatTimer(int seconds) {
    final m = (seconds ~/ 60).toString();
    final s = (seconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  @override
  Widget build(BuildContext context) {
    if (_isTranscribing) {
      return Container(
        height: 38,
        padding: const EdgeInsets.symmetric(horizontal: 10),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: AppColors.goldSubtle,
          borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
          border: Border.all(color: AppColors.gold.withValues(alpha: 0.4)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(
              width: 12,
              height: 12,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: AppColors.goldDark,
              ),
            ),
            const SizedBox(width: 6),
            Text(
              'Transcribing...',
              style: AppTextStyles.mono(fontSize: 10, color: AppColors.goldDark),
            ),
          ],
        ),
      );
    }

    if (_isRecording) {
      return GestureDetector(
        onTap: _stopRecording,
        child: Container(
          height: 38,
          padding: const EdgeInsets.symmetric(horizontal: 10),
          decoration: BoxDecoration(
            color: AppColors.statusErrorRed.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
            border: Border.all(
              color: AppColors.statusErrorRed.withValues(alpha: 0.5),
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              ScaleTransition(
                scale: _pulseController,
                child: Container(
                  width: 8,
                  height: 8,
                  decoration: const BoxDecoration(
                    color: AppColors.statusErrorRed,
                    shape: BoxShape.circle,
                  ),
                ),
              ),
              const SizedBox(width: 6),
              Text(
                _formatTimer(_recordSeconds),
                style: AppTextStyles.mono(
                  fontSize: 11,
                  color: AppColors.statusErrorRed,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(width: 8),
              const Icon(
                Icons.stop,
                size: 16,
                color: AppColors.statusErrorRed,
              ),
            ],
          ),
        ),
      );
    }

    return IconButton(
      tooltip: 'Voice input (record note)',
      onPressed: widget.disabled ? null : _startRecording,
      icon: const Icon(Icons.mic, size: 18),
      color: AppColors.lightTextSecondary,
      style: IconButton.styleFrom(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
        ),
      ),
    );
  }
}
