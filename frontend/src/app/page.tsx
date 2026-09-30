import { Capabilities } from "@/components/landing/capabilities";
import { Container } from "@/components/landing/container";
import { Hero } from "@/components/landing/hero";
import { LandingFooter } from "@/components/landing/landing-footer";
import { LandingHeader } from "@/components/landing/landing-header";
import { Pipeline } from "@/components/landing/pipeline";

/**
 * Landing page.
 *
 * Composition only. It was 653 lines of inline markup mixing copy, layout and
 * around twenty animation loops; it is now four sections in
 * `src/components/landing/`.
 *
 * What was removed, and why:
 *
 *   - The full-screen 3D logo that sat behind everything: a fixed 1200x1200 SVG
 *     on a fifteen-second `rotateX`/`rotateY`/`scale` loop with `mix-blend-screen`,
 *     which meant a constant repaint of a blurred blended layer over the entire
 *     viewport, plus a `useScroll` handler tracking the whole document. It also
 *     washed out the light palette and sat behind body copy at 30% opacity.
 *   - The mock workspace screenshot. It was about 500 lines presenting an
 *     invented product as though it were real: a hardcoded "124.5k req/s", a
 *     "72%" load figure, fabricated build logs, and a live-looking
 *     `logistics.sutra.app` reading "Successfully Deployed". A marketing page
 *     showing a fictional deploy state is the same fabrication that was removed
 *     from the dashboard, where it made a dead backend look healthy.
 *   - The per-card float, pulse, orbit, equaliser and grid-scan loops, which
 *     conveyed nothing and left the page permanently in motion.
 *
 * Vertical rhythm is uniform: every content section is `py-24 md:py-28`, and the
 * hero carries matching padding of its own so the gap below the calls to action
 * is the same as the gap between sections.
 */
export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background font-sans text-foreground selection:bg-muted-foreground">
      <LandingHeader />

      <main>
        <Hero />

        {/* The rule is a sibling of the container rather than a border on it, so
            it spans the viewport instead of stopping at the max-width. */}
        <div className="border-t border-border">
          <Container>
            <Pipeline />
            <Capabilities />
          </Container>
        </div>
      </main>

      <LandingFooter />
    </div>
  );
}
