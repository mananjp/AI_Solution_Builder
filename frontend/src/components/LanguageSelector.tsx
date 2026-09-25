'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Check, Globe } from 'lucide-react';
import { useI18n } from '@/components/I18nProvider';
import { SUPPORTED_LANGUAGES } from '@/lib/i18n/languages';

interface LanguageSelectorProps {
  compact?: boolean;
  align?: 'left' | 'right';
  className?: string;
}

export function LanguageSelector({
  compact = false,
  align = 'right',
  className = '',
}: LanguageSelectorProps) {
  const { lang, setLang, t } = useI18n();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  const dropdownAlign = align === 'right' ? 'right-0' : 'left-0';

  return (
    <div ref={ref} className={`relative ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={t('lang.language')}
        title={t('lang.language')}
        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm text-[11px] font-semibold uppercase tracking-widest text-[var(--text-2)] hover:text-[var(--text)] hover:bg-[var(--bg-2)] border border-[var(--border)] transition-all cursor-pointer"
      >
        <Globe className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />
        {!compact && <span className="font-mono">{lang}</span>}
      </button>

      {open && (
        <div
          className={`absolute ${dropdownAlign} top-full mt-2 w-56 z-50 bg-[var(--bg-2)] border border-[var(--border)] rounded-sm shadow-xl`}
        >
          <p className="px-3 py-2 text-[9px] uppercase tracking-widest font-bold text-[var(--text-3)] border-b border-[var(--border)]">
            {t('lang.language')}
          </p>
          <div className="max-h-72 overflow-y-auto p-1">
            {SUPPORTED_LANGUAGES.map((l) => {
              const active = l.code === lang;
              return (
                <button
                  key={l.code}
                  type="button"
                  onClick={() => {
                    setLang(l.code);
                    setOpen(false);
                  }}
                  className={`w-full flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-sm text-[12px] transition-colors cursor-pointer ${
                    active
                      ? 'bg-[var(--bg)] text-[var(--sutra-charcoal)] font-semibold'
                      : 'text-[var(--text-2)] hover:text-[var(--text)] hover:bg-[var(--bg)]'
                  }`}
                >
                  <span dir="auto" className="truncate">{l.native}</span>
                  <span className="flex items-center gap-1.5 shrink-0">
                    {l.rtl && (
                      <span dir="ltr" className="text-[8px] uppercase tracking-widest font-bold text-[var(--text-3)] border border-[var(--border)] px-1 py-px rounded-sm">
                        RTL
                      </span>
                    )}
                    {active && <Check className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}