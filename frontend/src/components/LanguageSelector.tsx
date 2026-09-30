'use client';

import { Check, ChevronDown, Globe } from 'lucide-react';

import { useI18n } from '@/components/I18nProvider';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { SUPPORTED_LANGUAGES } from '@/lib/i18n/languages';
import { setCurrentLanguage } from '@/lib/api';
import type { ComponentProps } from 'react';

type ButtonSize = NonNullable<ComponentProps<typeof Button>['size']>;

export interface LanguageSelectorProps {
  /**
   * Shows the two-letter code on the trigger instead of the language's own
   * name. For the narrow contexts — the auth pages and the landing header —
   * where "ગુજરાતી" would crowd the control.
   */
  compact?: boolean;
  /**
   * Must match the size of the buttons it sits beside. The Navbar mixes 28px
   * controls, so it takes the default; the landing header sits among 40px ones.
   */
  size?: ButtonSize;
  className?: string;
}

/**
 * Language switcher.
 *
 * Built on the shared `DropdownMenu` and, critically, on the shared `Button` via
 * `asChild`. `DropdownMenuTrigger` on its own renders a bare Radix trigger with
 * no classes at all, so passing `className` to it styled an unstyled element —
 * no `inline-flex`, no border, no radius, no hover, no focus ring. Composing it
 * with `Button` is what makes it look like its neighbours.
 *
 * Each row shows the language in its own script plus its English name, so a
 * reader who cannot identify a script can still find theirs.
 */
export function LanguageSelector({
  compact = false,
  size = 'sm',
  className,
}: LanguageSelectorProps) {
  const { lang, setLang, t } = useI18n();
  const current = SUPPORTED_LANGUAGES.find((l) => l.code === lang) ?? SUPPORTED_LANGUAGES[0];

  const handleSelect = (code: string) => {
    setLang(code);
    // The API layer reads the same value to set the request's content language,
    // so the two have to be told together.
    setCurrentLanguage(code);
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size={size}
          aria-label={t('lang.language')}
          title={t('lang.language')}
          className={`gap-1.5 ${className ?? ''}`}
        >
          {/* Explicit sizes: Button scales any icon without a `size-*` class to
              16px, which is too large for a 28px control. */}
          <Globe aria-hidden className="size-3.5 shrink-0 opacity-70" />
          <span dir="auto" className="font-medium leading-none">
            {compact ? current.code.toUpperCase() : current.native}
          </span>
          <ChevronDown aria-hidden className="size-3 shrink-0 opacity-50" />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>{t('lang.language')}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {SUPPORTED_LANGUAGES.map((l) => (
          <DropdownMenuItem
            key={l.code}
            onSelect={() => handleSelect(l.code)}
            aria-current={l.code === lang ? 'true' : undefined}
            className="gap-3"
          >
            <span className="flex min-w-0 flex-1 flex-col">
              {/* `dir="auto"` so a right-to-left script lays out correctly if one
                  is ever added. */}
              <span dir="auto" className="truncate font-medium">
                {l.native}
              </span>
              <span className="truncate text-[11px] text-muted">{l.english}</span>
            </span>
            {l.code === lang ? (
              <Check aria-hidden className="size-4 shrink-0" />
            ) : (
              <span className="shrink-0 font-mono text-[10px] uppercase text-muted">
                {l.code}
              </span>
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default LanguageSelector;
