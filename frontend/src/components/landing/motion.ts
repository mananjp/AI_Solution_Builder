"use client";

import { motion, type Transition } from "motion/react";

import { useReducedMotion } from "@/lib/use-reduced-motion";

/**
 * Motion helper for the landing page.
 *
 * The page used to declare around twenty infinite `animate` loops with no
 * reduced-motion handling, so a visitor who had asked their OS to reduce motion
 * still got a permanently rotating logo, a pulsing grid and a scanning laser.
 * Those are gone; the single entrance fade below is all that remains, and it is
 * skipped entirely when motion is reduced.
 *
 * `enterTransition` is a plain function rather than a hook: it builds a config
 * object and holds no state, so naming it `use*` would only invite a
 * rules-of-hooks violation at the call site.
 */
export function useMotionEnabled() {
  return !useReducedMotion();
}

/** Transition for a one-shot entrance. */
export function enterTransition(delay = 0): Transition {
  return { duration: 0.6, delay, ease: [0.23, 1, 0.32, 1] };
}

export { motion };
