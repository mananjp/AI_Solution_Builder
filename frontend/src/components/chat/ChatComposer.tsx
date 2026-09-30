'use client';

import { useCallback, useLayoutEffect, useRef } from 'react';
import { Paperclip, Settings2 } from 'lucide-react';
import { VoiceInputButton } from '@/components/VoiceInputButton';
import { SendButton } from '@/components/lab/send-button';
import { Button } from "@/components/ui/button";

interface ChatComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (build: boolean) => void;
  disabled: boolean;
  streaming: boolean;
  buildRequested: boolean;
  onToggleBuild: (value: boolean) => void;
  appName: string;
  onAppNameChange: (value: string) => void;
  showAppNameField: boolean;
  placeholder: string;
  appNamePlaceholder: string;
  buildLabel: string;
  appNameLabel: string;
  attachLabel: string;
  onAttach: () => void;
  compact?: boolean;
}

export default function ChatComposer({
  value,
  onChange,
  onSubmit,
  disabled,
  streaming,
  buildRequested,
  onToggleBuild,
  appName,
  onAppNameChange,
  showAppNameField,
  placeholder,
  appNamePlaceholder,
  buildLabel,
  appNameLabel,
  attachLabel,
  onAttach,
  compact = false,
}: ChatComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Grow with the content up to ~6 lines, then scroll. Without this a long
  // prompt is clipped to a single line, which reads as "my message got cut off".
  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, compact ? 96 : 160)}px`;
  }, [value, compact]);

  const submit = useCallback(() => {
    if (!value.trim() || streaming) return;
    onSubmit(buildRequested);
    // Keep focus so a follow-up can be typed without reaching for the mouse.
    requestAnimationFrame(() => textareaRef.current?.focus());
  }, [value, streaming, buildRequested, onSubmit]);

  return (
    <div className="shrink-0 border-t border-[var(--border)] bg-[var(--bg-2)] p-3">
      {showAppNameField && (
        <div className="mb-2.5 flex animate-fade-in items-center gap-2">
          <span className="shrink-0 text-[10px] font-bold uppercase tracking-widest text-[var(--text-3)]">
            {appNameLabel}
          </span>
          <input
            type="text"
            value={appName}
            onChange={(e) => onAppNameChange(e.target.value)}
            placeholder={appNamePlaceholder}
            disabled={streaming}
            className="min-w-0 flex-1 rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-[12px] text-[var(--sutra-ink)] outline-none transition-colors placeholder:text-[var(--text-3)] focus:border-[var(--sutra-strong)] disabled:opacity-60"
          />
        </div>
      )}

<div className="flex items-end gap-2">
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          onClick={onAttach}
          disabled={streaming}
          aria-label={attachLabel}
        >
          <Paperclip className="h-4 w-4" />
        </Button>

        <VoiceInputButton
          onTranscribed={(text) => onChange(value ? `${value} ${text}` : text)}
          disabled={streaming}
        />

        <div className="relative flex min-w-0 flex-1 items-end rounded-lg border border-[var(--border)] bg-[var(--bg)] shadow-sm transition-colors focus-within:border-[var(--sutra-strong)]">
          <textarea
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              // Enter sends, Shift+Enter inserts a newline, and a key that
              // closes an IME composition is left alone so typing in Hindi or
              // Chinese still works.
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={placeholder}
            disabled={disabled || streaming}
            className="max-h-40 min-h-[2.75rem] w-full resize-none bg-transparent px-3.5 py-3 pr-28 text-[13px] leading-relaxed text-[var(--sutra-ink)] outline-none placeholder:text-[var(--text-3)] disabled:opacity-60"
          />

          
            <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onToggleBuild(!buildRequested)}
            disabled={disabled || streaming}
            className="shrink-0 gap-1.5 text-[11px] uppercase tracking-wider text-[var(--text-3)]"
          >
            <Settings2 className="h-3 w-3" />
            <span className="hidden sm:inline">{buildLabel}</span>
          </Button>
        </div>

        {/* The lab send button flies the icon out on submit and confirms with a
            tick, so a sent message is visibly acknowledged instead of the arrow
            just sitting there. */}
        <SendButton
          onSend={value.trim() && !streaming ? submit : undefined}
          label="Send"
          sentLabel="Sent"
          variant="solid"
          iconOnly
          className="shrink-0"
        />
      </div>
    </div>
  );
}
