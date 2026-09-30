import type { ElementType, ReactNode } from "react";

import { cn } from "@/lib/cn";

/**
 * Horizontal page container: a centred max-width with responsive gutters.
 *
 * The landing page had `mx-auto max-w-[1400px] px-6 md:px-12` written out three
 * times — header, main, footer — so the gutters had to be kept in sync by hand.
 * When the sections were split into components the content sections lost the
 * wrapper entirely and ran edge to edge.
 *
 * Vertical padding is deliberately not included: sections own their own rhythm,
 * and stacking it here made the spacing depend on which element was used.
 */
export function Container({
  as: Tag = "div",
  className,
  children,
}: {
  as?: ElementType;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Tag className={cn("mx-auto w-full max-w-[1400px] px-6 md:px-12", className)}>
      {children}
    </Tag>
  );
}
