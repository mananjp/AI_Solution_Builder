'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Globe, ChevronDown, Check } from 'lucide-react';
import { useLanguage, SUPPORTED_LANGUAGES } from '@/context/LanguageContext';

interface LanguageSelectorProps {
  className?: string;
  compact?: boolean;
}

export default function LanguageSelector({ className = '', compact = false }: LanguageSelectorProps) {
  const { language, setLanguage, currentOption } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  return (
    <div className={`relative inline-block text-left ${className}`} ref={containerRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="h-8 px-2.5 rounded-sm bg-[var(--bg-2)] border border-[var(--border)] hover:border-[var(--sutra-muted-gold)] text-[var(--text)] flex items-center gap-2 text-xs font-medium transition-all shadow-sm focus:outline-none"
        title="Select Language (ગુજરાતી, हिन्दी, English, etc.)"
        aria-expanded={isOpen}
      >
        <Globe className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)] shrink-0" />
        <span className="font-sans font-medium tracking-wide">
          {compact ? currentOption.code.toUpperCase() : currentOption.nativeName}
        </span>
        <ChevronDown
          className={`w-3 h-3 text-[var(--text-3)] transition-transform duration-200 ${
            isOpen ? 'rotate-180' : ''
          }`}
        />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-1.5 w-56 rounded-md bg-[#0d121f] border border-[var(--sutra-muted-gold)]/30 shadow-2xl z-50 overflow-hidden py-1 animate-fade-in backdrop-blur-md">
          <div className="px-3 py-1.5 text-[10px] uppercase tracking-wider font-semibold text-[var(--sutra-muted-gold)] border-b border-[var(--border)] bg-[#090d16]">
            Select Language / ભાષા / भाषा
          </div>

          <div className="max-h-72 overflow-y-auto divide-y divide-[var(--border)]/40">
            {SUPPORTED_LANGUAGES.map((opt) => {
              const isSelected = opt.code === language;
              return (
                <button
                  key={opt.code}
                  type="button"
                  onClick={() => {
                    setLanguage(opt.code);
                    setIsOpen(false);
                  }}
                  className={`w-full text-left px-3 py-2 flex items-center justify-between transition-colors hover:bg-[var(--sutra-muted-gold)]/10 ${
                    isSelected ? 'bg-[var(--sutra-muted-gold)]/15 text-[var(--sutra-deep-gold)] font-medium' : 'text-slate-200'
                  }`}
                >
                  <div className="flex flex-col">
                    <span className="text-xs font-medium tracking-wide">
                      {opt.nativeName}
                    </span>
                    <span className="text-[10px] text-slate-400">
                      {opt.name} {opt.script !== 'Latin' && `• ${opt.script}`}
                    </span>
                  </div>

                  {isSelected && (
                    <Check className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)] shrink-0" />
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
