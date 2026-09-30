import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

interface SectionHeadingProps {
  title: ReactNode;
  /** Short uppercase line under the title. */
  kicker?: ReactNode;
  /** Optional supporting paragraph. */
  description?: ReactNode;
  className?: string;
}

/**
 * Shared heading block for the landing sections.
 *
 * Each of the three sections previously repeated the same
 * `<div className="mb-16 text-center">` wrapper with its own vertical rhythm
 * (`mb-20`, `mb-16`), so the spacing drifted between sections.
 */
export function SectionHeading({
  title,
  kicker,
  description,
  className,
}: SectionHeadingProps) {
  return (
    <div className={cn("mb-14 text-center md:mb-16", className)}>
      <h2 className="text-3xl font-serif tracking-tight text-foreground md:text-4xl">
        {title}
      </h2>
      {description ? (
        <p className="mx-auto mt-4 max-w-xl text-sm font-light text-muted md:text-base">
          {description}
        </p>
      ) : (
        kicker && (
          <p className="mt-4 text-xs font-semibold uppercase tracking-widest text-muted">
            {kicker}
          </p>
        )
      )}
    </div>
  );
}
