import type { ComponentProps, ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

/**
 * The single definition of every action on the landing page.
 *
 * These were written inline at each call site and had drifted apart:
 *
 *   - the primary treatment was re-typed as `bg-foreground text-background` in
 *     two places even though `--primary` already resolves to `var(--foreground)`.
 *   - `size="lg"` on the shared Button is `h-9 px-2.5`, and the hero then
 *     overrode only the padding with `px-8`, leaving a 36px-tall button with 32px
 *     of side padding.
 *   - `uppercase tracking-widest` was copy-pasted onto each call site.
 *   - "Sign in" was a bare `<Link>`, so it had no height, no focus ring and no
 *     hover treatment while the button beside it had all three.
 *
 * It now sets no box metrics of its own. Height and padding come from the
 * Button's own `size`, so the nav and hero cannot drift from the rest of the app
 * again — adding a Button size automatically changes every landing action.
 */

type Tone = "primary" | "secondary" | "quiet";

/**
 * `nav` matches the theme toggle sitting beside it in the header (40px), and
 * `hero` is the large call to action in the first screen.
 */
type Scale = "nav" | "hero";

const SCALE = {
  nav: "lg",
  hero: "pill",
} as const satisfies Record<Scale, NonNullable<ComponentProps<typeof Button>["size"]>>;

const TONE: Record<Tone, string> = {
  // `default` is bg-primary text-primary-foreground, and --primary is
  // var(--foreground): no colour override needed.
  primary: "",
  secondary: "",
  // `ghost` drops the raised shadow, so a quiet action does not compete with the
  // solid one beside it.
  quiet: "font-semibold",
};

const LABEL = "uppercase tracking-widest";

interface ActionLinkProps extends Omit<ComponentProps<typeof Button>, "size"> {
  tone?: Tone;
  scale?: Scale;
  children: ReactNode;
}

export function ActionLink({
  tone = "primary",
  scale = "nav",
  className,
  variant,
  children,
  ...props
}: ActionLinkProps) {
  const resolvedVariant =
    variant ??
    (tone === "quiet"
      ? ("ghost" as const)
      : tone === "secondary"
        ? ("outline" as const)
        : ("default" as const));

  return (
    <Button
      asChild
      variant={resolvedVariant}
      size={SCALE[scale]}
      className={cn(LABEL, TONE[tone], className)}
      {...props}
    >
      {children}
    </Button>
  );
}
