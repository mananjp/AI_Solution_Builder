'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Check, Globe, ChevronDown } from 'lucide-react';
import { useI18n } from '@/components/I18nProvider';
import { SUPPORTED_LANGUAGES } from '@/lib/i18n/languages';
import { setCurrentLanguage } from '@/lib/api';

export interface LanguageSelectorProps {
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
  const currentLanguageDef =
    SUPPORTED_LANGUAGES.find((l) => l.code === lang) || SUPPORTED_LANGUAGES[0];

  const handleSelectLanguage = (code: string) => {
    setLang(code);
    setCurrentLanguage(code);
    setOpen(false);
  };

  return (
    <div ref={ref} className={`relative inline-block text-left ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={t('lang.language')}
        title={t('lang.language')}
        className="h-8 px-2.5 rounded-sm bg-[var(--bg-2)] border border-[var(--border)] hover:border-[var(--sutra-muted-gold)] text-[var(--text)] flex items-center gap-2 text-xs font-medium transition-all shadow-sm focus:outline-none cursor-pointer"
      >
        <Globe className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)] shrink-0" />
        <span className="font-sans font-medium tracking-wide">
          {compact ? lang.toUpperCase() : currentLanguageDef.native}
        </span>
        <ChevronDown
          className={`w-3 h-3 text-[var(--text-3)] transition-transform duration-200 ${
            open ? 'rotate-180' : ''
          }`}
        />
      </button>

      {open && (
        <div
          className={`absolute ${dropdownAlign} top-full mt-1.5 w-60 z-50 bg-[#0d121f] border border-[var(--sutra-muted-gold)]/30 rounded-md shadow-2xl overflow-hidden py-1 animate-fade-in backdrop-blur-md`}
        >
          <div className="px-3 py-1.5 text-[10px] uppercase tracking-wider font-semibold text-[var(--sutra-muted-gold)] border-b border-[var(--border)] bg-[#090d16] flex items-center justify-between">
            <span>{t('lang.language')}</span>
            <span className="text-[9px] text-slate-400 font-normal">ભાષા / भाषा</span>
          </div>

          <div className="max-h-72 overflow-y-auto divide-y divide-[var(--border)]/30 p-1">
            {SUPPORTED_LANGUAGES.map((l) => {
              const active = l.code === lang;
              return (
                <button
                  key={l.code}
                  type="button"
                  onClick={() => handleSelectLanguage(l.code)}
                  className={`w-full flex items-center justify-between gap-2 px-3 py-2 rounded-sm text-[12px] transition-colors cursor-pointer ${
                    active
                      ? 'bg-[var(--sutra-muted-gold)]/15 text-[var(--sutra-deep-gold)] font-medium'
                      : 'text-slate-200 hover:bg-[var(--sutra-muted-gold)]/10 hover:text-white'
                  }`}
                >
                  <span dir="auto" className="font-medium truncate tracking-wide">
                    {l.native}
                  </span>
                  <span className="flex items-center gap-1.5 shrink-0">
                    {l.rtl && (
                      <span
                        dir="ltr"
                        className="text-[8px] uppercase tracking-widest font-bold text-amber-400/80 border border-amber-400/30 px-1 py-px rounded-sm"
                      >
                        RTL
                      </span>
                    )}
                    <span className="text-[10px] font-mono text-slate-400 uppercase">
                      {l.code}
                    </span>
                    {active && <Check className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)] shrink-0" />}
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

export default LanguageSelector;
