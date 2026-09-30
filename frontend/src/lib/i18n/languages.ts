export interface LanguageDef {
  code: string;
  native: string;
  english: string;
  rtl: boolean;
}

export const DEFAULT_LANGUAGE = 'en';

/**
 * Languages the interface is actually translated into.
 *
 * This list used to advertise 28 languages while only three dictionaries exist
 * in `./dictionaries` (`en`, `hi`, `gu`). Selecting any of the other 25 fell
 * through to `getDictionary(lang) ?? getDictionary(DEFAULT_LANGUAGE)`, so the
 * page rendered entirely in English — while `I18nProvider` still wrote
 * `document.documentElement.lang` and `dir` from the chosen code. Picking Arabic
 * produced English copy in a right-to-left layout under an `lang="ar"` tag,
 * which is worse than no option at all: a screen reader announces English text
 * with the wrong language, and the RTL layout exposes directional bugs that a
 * user of a real translation would hit.
 *
 * So the selector now offers only what genuinely works. Adding a language means
 * adding its dictionary file first, then listing it here.
 *
 * Note this is deliberately narrower than the backend's `SUPPORTED_LANGUAGES`.
 * The backend list drives the *language of AI-generated content* — detecting it
 * from a prompt and writing replies in it — which is a working feature
 * independent of the interface chrome. Narrowing that would remove a capability
 * the product actually has, so it is left alone.
 */
export const SUPPORTED_LANGUAGES: LanguageDef[] = [
  { code: 'en', native: 'English', english: 'English', rtl: false },
  { code: 'hi', native: 'हिन्दी', english: 'Hindi', rtl: false },
  { code: 'gu', native: 'ગુજરાતી', english: 'Gujarati', rtl: false },
];

const SUPPORTED_CODES = new Set(SUPPORTED_LANGUAGES.map((l) => l.code));
const RTL_CODES = new Set(SUPPORTED_LANGUAGES.filter((l) => l.rtl).map((l) => l.code));

export function normalizeCode(raw: string): string {
  if (!raw) return '';
  const primary = raw.trim().toLowerCase().split(/[-_]/)[0];
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
  return SUPPORTED_LANGUAGES.find((l) => l.code === c)?.native ?? DEFAULT_LANGUAGE;
}
