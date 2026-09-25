import { DEFAULT_LANGUAGE, normalizeCode } from './languages';

const STORAGE_KEY = 'sutra.lang';

export function loadLanguage(): string {
  if (typeof window === 'undefined') return DEFAULT_LANGUAGE;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return normalizeCode(raw || '') || DEFAULT_LANGUAGE;
  } catch {
    return DEFAULT_LANGUAGE;
  }
}

export function saveLanguage(code: string) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, normalizeCode(code) || DEFAULT_LANGUAGE);
  } catch {
    /* storage may be unavailable (private mode / disabled) — non-fatal */
  }
}

/** Passive read for the API layer (request headers) — SSR-safe. */
export function getActiveLanguageCode(): string {
  return loadLanguage();
}