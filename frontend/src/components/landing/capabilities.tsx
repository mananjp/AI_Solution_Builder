"use client";

import type { ElementType } from "react";

import { CAPABILITIES } from "./landing-content";
import { SectionHeading } from "./section-heading";

/**
 * Core engine capabilities.
 *
 * These were four cards each wrapped in its own looping backdrop — falling
 * lines, counter-rotating orbits, an equaliser and a scanning grid — plus a
 * blurred glow that faded in on hover. None of it carried information: at 10%
 * opacity behind body copy it read as texture, and four different animations
 * fighting for attention is what made the page look generated rather than
 * designed. The cards now stand on their own.
 *
 * The copy and icons still come from `landing-content`, so the section remains
 * data-driven.
 */
export function Capabilities() {
  return (
    <section className="py-24 md:py-28">
      <SectionHeading
        title="Core Engine Capabilities"
        kicker="Intelligence at every layer."
      />

      <ul className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {CAPABILITIES.map((capability) => (
          <CapabilityCard
            key={capability.id}
            title={capability.title}
            desc={capability.desc}
            icon={capability.icon}
          />
        ))}
      </ul>
    </section>
  );
}

function CapabilityCard({
  title,
  desc,
  icon: Icon,
}: {
  title: string;
  desc: string;
  icon: ElementType;
}) {
  return (
    <li className="rounded-xl border border-border bg-surface/40 p-8">
      <div className="mb-6 flex h-11 w-11 items-center justify-center rounded-lg border border-border bg-background">
        <Icon className="h-5 w-5 text-muted" aria-hidden />
      </div>
      <h3 className="mb-3 font-serif text-xl tracking-wide text-foreground">
        {title}
      </h3>
      <p className="text-[15px] font-light leading-relaxed text-muted">{desc}</p>
    </li>
  );
}
