'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Mic, Square, Loader2, Globe } from 'lucide-react';
import { uploadApi } from '@/lib/api';
import { useI18n } from '@/components/I18nProvider';
import { SUPPORTED_LANGUAGES } from '@/lib/i18n/languages';
import { Button } from "@/components/ui/button";

interface VoiceInputButtonProps {
  onTranscribed: (text: string, lang?: string) => void;
  className?: string;
  disabled?: boolean;
}

export function VoiceInputButton({
  onTranscribed,
  className = '',
  disabled = false,
}: VoiceInputButtonProps) {
  const { lang, t } = useI18n();
  const currentOption =
    SUPPORTED_LANGUAGES.find((l) => l.code === lang) || SUPPORTED_LANGUAGES[0];

  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const [detectedLang, setDetectedLang] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  const startRecording = async () => {
    setErrorMessage(null);
    setDetectedLang(null);
    audioChunksRef.current = [];

    if (!navigator?.mediaDevices?.getUserMedia) {
      setErrorMessage('Audio recording is not supported on this browser.');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      let mimeType = 'audio/webm';
      if (!MediaRecorder.isTypeSupported('audio/webm')) {
        if (MediaRecorder.isTypeSupported('audio/mp4')) {
          mimeType = 'audio/mp4';
        } else if (MediaRecorder.isTypeSupported('audio/ogg')) {
          mimeType = 'audio/ogg';
        } else {
          mimeType = '';
        }
      }

      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        if (timerRef.current) clearInterval(timerRef.current);

        const chunks = audioChunksRef.current;
        if (chunks.length === 0) return;

        const blobType = recorder.mimeType || 'audio/webm';
        const audioBlob = new Blob(chunks, { type: blobType });
        const ext = blobType.includes('mp4') ? 'mp4' : blobType.includes('ogg') ? 'ogg' : 'webm';

        setIsProcessing(true);
        try {
          // Pass the user's selected language (e.g. 'gu', 'hi', 'en') to Groq Whisper
          const res = await uploadApi.uploadAudio(audioBlob, `voice_note.${ext}`, lang);
          if (res?.transcription) {
            onTranscribed(res.transcription, res.detected_language);
            if (res.detected_language) {
              setDetectedLang(res.detected_language);
            }
          }
        } catch (err: unknown) {
          const msg =
            err && typeof err === 'object' && 'message' in err
              ? String((err as { message: string }).message)
              : 'Voice transcription failed.';
          setErrorMessage(msg);
        } finally {
          setIsProcessing(false);
          setIsRecording(false);
          setRecordSeconds(0);
        }
      };

      recorder.start(250);
      setIsRecording(true);
      setRecordSeconds(0);

      timerRef.current = setInterval(() => {
        setRecordSeconds((s) => s + 1);
      }, 1000);
    } catch (err) {
      console.error('Microphone access denied:', err);
      setErrorMessage('Microphone access denied. Please allow microphone permissions.');
      setIsRecording(false);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  };

  const formatTime = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const remainder = secs % 60;
    return `${mins}:${remainder < 10 ? '0' : ''}${remainder}`;
  };

  return (
    <div className={`inline-flex min-w-0 items-center gap-2 ${className}`}>
      {isRecording ? (
        <Button variant="outline" size="sm"
          type="button"
          onClick={stopRecording}
          disabled={disabled || isProcessing}
          className="inline-flex min-w-0 max-w-[9rem] items-center gap-1.5 text-xs font-medium bg-[var(--red-wash)] text-[var(--red)] border border-[var(--red-wash)] hover:bg-[var(--red-wash)] transition-all animate-pulse"
          title={t('voice.stopRecordingTitle') || 'Stop recording'}
        >
          <Square className="w-3.5 h-3.5 shrink-0 fill-current" />
          <span className="truncate">{t('voice.recording') || 'Recording'} {formatTime(recordSeconds)}</span>
        </Button>
      ) : isProcessing ? (
        <Button variant="outline" size="sm"
          type="button"
          disabled
          className="inline-flex min-w-0 max-w-[9rem] items-center gap-1.5 text-xs font-medium bg-[var(--sutra-strong)]/10 text-[var(--sutra-strong)] border border-[var(--sutra-strong)]/30 cursor-wait"
          title={t('voice.transcribing') || 'Transcribing (Groq Whisper)...'}
        >
          <Loader2 className="w-3.5 h-3.5 shrink-0 animate-spin" />
          <span className="truncate">{t('voice.transcribing') || 'Transcribing (Groq Whisper)...'}</span>
        </Button>
      ) : (
        <Button variant="secondary" size="sm"
          type="button"
          onClick={startRecording}
          disabled={disabled}
          className="inline-flex min-w-0 max-w-[11rem] items-center gap-1.5 text-xs font-medium text-[var(--text-2)] hover:text-[var(--text-1)] hover:bg-[var(--bg-2)] border border-[var(--border)] transition-all"
          title={`Speak in ${currentOption.native} (${currentOption.code.toUpperCase()}), English, or any language (Groq Whisper AI)`}
        >
          <Mic className="w-4 h-4 shrink-0 text-[var(--sutra-strong)]" />
          <span className="hidden truncate sm:inline">{t('voice.voiceNote') || 'Voice Note'}</span>
          <span className="shrink-0 text-[10px] font-mono px-1 py-0.2 rounded bg-[var(--bg)] border border-[var(--border)] text-[var(--sutra-strong)]">
            {lang.toUpperCase()}
          </span>
        </Button>
      )}

      {detectedLang && !isRecording && !isProcessing && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] uppercase font-semibold bg-[var(--green-wash)] text-[var(--green)] border border-[var(--green-wash)]">
          <Globe className="w-2.5 h-2.5" />
          {detectedLang}
        </span>
      )}

      {errorMessage && (
        <span className="text-[11px] text-[var(--red)] max-w-xs truncate" title={errorMessage}>
          {errorMessage}
        </span>
      )}
    </div>
  );
}

export default VoiceInputButton;
