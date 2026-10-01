export interface LanguageDef {
  code: string;
  native: string;
  rtl: boolean;
}

export const DEFAULT_LANGUAGE = 'en';

// BCp 47-friendly short codes — mirrors backend SUPPORTED_LANGUAGES (app/core/i18n.py).
export const SUPPORTED_LANGUAGES: LanguageDef[] = [
  { code: 'en', native: 'English', rtl: false },
  { code: 'es', native: 'Español', rtl: false },
  { code: 'fr', native: 'Français', rtl: false },
  { code: 'de', native: 'Deutsch', rtl: false },
  { code: 'pt', native: 'Português', rtl: false },
  { code: 'it', native: 'Italiano', rtl: false },
  { code: 'nl', native: 'Nederlands', rtl: false },
  { code: 'ru', native: 'Русский', rtl: false },
  { code: 'hi', native: 'हिन्दी', rtl: false },
  { code: 'gu', native: 'ગુજરાતી', rtl: false },
  { code: 'mr', native: 'मराठी', rtl: false },
  { code: 'bn', native: 'বাংলা', rtl: false },
  { code: 'ta', native: 'தமிழ்', rtl: false },
  { code: 'te', native: 'తెలుగు', rtl: false },
  { code: 'kn', native: 'ಕನ್ನಡ', rtl: false },
  { code: 'ml', native: 'മലയാളം', rtl: false },
  { code: 'pa', native: 'ਪੰਜਾਬੀ', rtl: false },
  { code: 'ur', native: 'اردو', rtl: true },
  { code: 'or', native: 'ଓଡ଼ିଆ', rtl: false },
  { code: 'as', native: 'অসমীয়া', rtl: false },
  { code: 'ja', native: '日本語', rtl: false },
  { code: 'ko', native: '한국어', rtl: false },
  { code: 'zh', native: '中文', rtl: false },
  { code: 'ar', native: 'العربية', rtl: true },
  { code: 'fa', native: 'فارسی', rtl: true },
  { code: 'he', native: 'עברית', rtl: true },
  { code: 'id', native: 'Bahasa Indonesia', rtl: false },
  { code: 'vi', native: 'Tiếng Việt', rtl: false },
  { code: 'tr', native: 'Türkçe', rtl: false },
];

const SUPPORTED_CODES = new Set(SUPPORTED_LANGUAGES.map((l) => l.code));
const RTL_CODES = new Set(SUPPORTED_LANGUAGES.filter((l) => l.rtl).map((l) => l.code));

export function normalizeCode(raw: string): string {
  if (!raw) return '';
  const primary = raw.trim().toLowerCase().split(/[-_]/)[0];
  if (primary.startsWith('zh')) return 'zh';
  return SUPPORTED_CODES.has(primary) ? primary : '';
}

export function isSupportedCode(code: string): boolean {
  return SUPPORTED_CODES.has(normalizeCode(code));
}

export function isRtlCode(code: string): boolean {
  return RTL_CODES.has(normalizeCode(code));
}

export function languageLabel(code: string): string {
  const c = normalizeCode(code);
  return (SUPPORTED_LANGUAGES.find((l) => l.code === c)?.native ?? c) || DEFAULT_LANGUAGE;
}