"use client";

import { PIPELINE_STAGES, type PipelineStage } from "./landing-content";
import { SectionHeading } from "./section-heading";

/**
 * The five-stage pipeline.
 *
 * The cards used to float on a four-second loop, staggered by index, with a
 * ring pulsing inside each icon and a highlight travelling along a connector
 * line. Five simultaneous loops on a page someone is trying to read is noise,
 * and the stagger meant the leftmost card was always mid-animation while the
 * rightmost was not, so the row never looked settled.
 *
 * The connector is a plain rule with a filled portion for completed stages,
 * which conveys the same progression without moving.
 */
export function Pipeline() {
  return (
    <section className="py-24 md:py-28">
      <SectionHeading
        title="The Architectural Pipeline"
        kicker="From raw intent to tangible software."
      />


      <ol className="relative grid grid-cols-1 gap-8 md:grid-cols-5 md:gap-6">
        {/* Connector, desktop only: the cards stack on narrow screens and a
            horizontal rule across them would imply a relationship that is not
            there. */}
        <div
          aria-hidden
          className="absolute left-0 right-0 top-[27px] hidden h-px bg-border md:block"
        />

        {PIPELINE_STAGES.map((stage) => (
          <PipelineCard key={stage.id} stage={stage} />
        ))}
      </ol>
    </section>
  );
}

function PipelineCard({ stage }: { stage: PipelineStage }) {
  const Icon = stage.icon;

  return (
    <li className="relative flex flex-col items-center gap-4 text-center">
      {/* The node sits above the connector rule, so it needs an opaque
          background to mask the line passing behind it. */}
      <span className="relative flex h-14 w-14 items-center justify-center rounded-full border border-border bg-background">
        <Icon className="h-5 w-5 text-foreground" aria-hidden />
      </span>

      <span className="font-mono text-[11px] tracking-widest text-muted">
        {stage.step}
      </span>

      <h3 className="text-sm font-bold uppercase tracking-widest text-foreground">
        {stage.title}
      </h3>

      <p className="max-w-[200px] text-xs font-light leading-relaxed text-muted">
        {stage.desc}
      </p>
    </li>
  );
}
