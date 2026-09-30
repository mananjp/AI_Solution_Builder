"use client";

import Link from "next/link";

import { ActionLink } from "./action-link";
import { enterTransition, motion, useMotionEnabled } from "./motion";

/**
 * Landing hero.
 *
 * The entrance fade is the only motion left here. The looping scroll indicator
 * is gone: it pointed at content that begins immediately below, so it was
 * decoration rather than a wayfinding cue, and it animated forever on a page
 * whose whole point is to be read.
 *
 * `bg-surface-gold` on both calls to action used to be undefined in
 * `globals.css` and unregistered in `@theme`, so Tailwind emitted nothing for it
 * and the primary button rendered with no background at all. These now use the
 * real foreground token via `ActionLink`.
 */
export function Hero() {
  const animate = useMotionEnabled();

  const copy = (
    <>
      <p className="mb-8 inline-flex items-center gap-3 text-[10px] font-bold uppercase tracking-[0.3em] text-muted md:text-xs">
        <span className="h-px w-8 bg-border-2" />
        Ancient precision. Modern intelligence.
        <span className="h-px w-8 bg-border-2" />
      </p>

      <h1 className="mb-8 font-serif text-5xl leading-[0.95] tracking-tight text-foreground md:text-7xl lg:text-8xl">
        Structure your <br />
        {/* The original ran a `from-foreground to-foreground` gradient over
            transparent text. Once the palette went monochrome both stops
            resolved to the same colour, so the effect was invisible. */}
        <span className="italic text-muted">intelligence.</span>
      </h1>

      <p className="mb-12 max-w-2xl text-lg font-light leading-relaxed text-balance text-muted md:text-xl">
        The autonomous pipeline that dissects business requirements, performs
        rigorous architectural reasoning, and synthesizes production-ready
        software systems in minutes.
      </p>

      <div className="flex flex-col items-center gap-3 sm:flex-row">
        <ActionLink scale="hero">
          <Link href="/chat">Build with SUTRA</Link>
        </ActionLink>
        <ActionLink tone="secondary" scale="hero">
          <Link href="/dashboard">Explore Workspaces</Link>
        </ActionLink>
      </div>
    </>
  );

  return (
    <section className="flex w-full flex-col items-center justify-center px-4 pb-28 pt-40 md:pb-36 md:pt-48">
      {animate ? (
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={enterTransition(0.1)}
          className="mx-auto flex max-w-4xl flex-col items-center text-center"
        >
          {copy}
        </motion.div>
      ) : (
        <div className="mx-auto flex max-w-4xl flex-col items-center text-center">
          {copy}
        </div>
      )}
    </section>
  );
}
