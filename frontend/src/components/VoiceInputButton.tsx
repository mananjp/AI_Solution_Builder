'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Mic, Square, Loader2, Globe } from 'lucide-react';
import { uploadApi } from '@/lib/api';
import { useI18n } from '@/components/I18nProvider';

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
  const { t } = useI18n();
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
          const res = await uploadApi.uploadAudio(audioBlob, `voice_note.${ext}`);
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
    <div className={`inline-flex items-center gap-2 ${className}`}>
      {isRecording ? (
        <button
          type="button"
          onClick={stopRecording}
          disabled={disabled || isProcessing}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/30 hover:bg-red-500/20 transition-all shadow-sm animate-pulse"
          title={t('voice.stopRecordingTitle')}
        >
          <Square className="w-3.5 h-3.5 fill-current" />
          <span>{t('voice.recording')} {formatTime(recordSeconds)}</span>
        </button>
      ) : isProcessing ? (
        <button
          type="button"
          disabled
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/30 cursor-wait"
        >
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          <span>{t('voice.transcribing')}</span>
        </button>
      ) : (
        <button
          type="button"
          onClick={startRecording}
          disabled={disabled}
          className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-[var(--text-2)] hover:text-[var(--text-1)] hover:bg-[var(--bg-2)] border border-[var(--border)] transition-all"
          title={t('voice.speakHint')}
        >
          <Mic className="w-4 h-4 text-indigo-500" />
          <span className="hidden sm:inline">{t('voice.voiceNote')}</span>
        </button>
      )}

      {detectedLang && !isRecording && !isProcessing && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] uppercase font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
          <Globe className="w-2.5 h-2.5" />
          {detectedLang}
        </span>
      )}

      {errorMessage && (
        <span className="text-[11px] text-red-500 max-w-xs truncate" title={errorMessage}>
          {errorMessage}
        </span>
      )}
    </div>
  );
}
