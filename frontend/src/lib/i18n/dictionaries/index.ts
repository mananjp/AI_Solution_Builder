import type { Dictionary, TranslationKey } from './en';
import { en } from './en';
import { hi } from './hi';

// Registry of shipped UI translations; missing languages fall back to English.
const DICTIONARIES: Record<string, Dictionary> = {
  en,
  hi,
};

export type { Dictionary, TranslationKey } from './en';

export function translate(
  dictionary: Dictionary | undefined,
  key: TranslationKey,
  params?: Record<string, string | number>,
): string {
  const value = (key as string)
    .split('.')
    .reduce<unknown>((acc, part) => {
      if (
        acc &&
        typeof acc === 'object' &&
        part in (acc as Record<string, unknown>)
      ) {
        return (acc as Record<string, unknown>)[part];
      }
      return undefined;
    }, dictionary);
  let result = typeof value === 'string' ? value : key;
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      result = result.replaceAll(`{{${k}}}`, String(v));
    }
  }
  return result;
}

export function getDictionary(langCode: string): Dictionary | undefined {
  return DICTIONARIES[langCode];
}