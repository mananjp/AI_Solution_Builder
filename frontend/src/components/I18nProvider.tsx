'use client';

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { DEFAULT_LANGUAGE, isRtlCode, normalizeCode } from '@/lib/i18n/languages';
import { getDictionary, translate } from '@/lib/i18n/dictionaries';
import type { TranslationKey } from '@/lib/i18n/dictionaries';
import { loadLanguage, saveLanguage } from '@/lib/i18n/client';

export interface I18nContextValue {
  lang: string;
  setLang: (code: string) => void;
  t: (key: TranslationKey, params?: Record<string, string | number>) => string;
  isRtl: boolean;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  // Lazy init reads localStorage only on the client; SSR always resolves 'en'.
  const [lang, setLangState] = useState<string>(() => {
    if (typeof window === 'undefined') return DEFAULT_LANGUAGE;
    return loadLanguage();
  });

  const setLang = useCallback((code: string) => {
    const next = normalizeCode(code) || DEFAULT_LANGUAGE;
    saveLanguage(next);
    setLangState(next);
  }, []);

  useEffect(() => {
    if (typeof document === 'undefined') return;
    document.documentElement.lang = lang;
    document.documentElement.dir = isRtlCode(lang) ? 'rtl' : 'ltr';
  }, [lang]);

  const value = useMemo<I18nContextValue>(() => {
    const dictionary = getDictionary(lang) ?? getDictionary(DEFAULT_LANGUAGE);
    return {
      lang,
      setLang,
      isRtl: isRtlCode(lang),
      t: (key, params) => translate(dictionary, key, params),
    };
  }, [lang, setLang]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error('useI18n must be used inside <I18nProvider>');
  }
  return ctx;
}