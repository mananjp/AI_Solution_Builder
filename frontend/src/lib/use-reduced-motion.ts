"use client"

import { useSyncExternalStore } from "react"

const QUERY = "(prefers-reduced-motion: reduce)"

function subscribe(onChange: () => void) {
  const query = window.matchMedia(QUERY)
  query.addEventListener("change", onChange)
  return () => query.removeEventListener("change", onChange)
}

function getSnapshot() {
  return window.matchMedia(QUERY).matches
}

/** Server render assumes motion is allowed, so the first paint matches the SSR output. */
function getServerSnapshot() {
  return false
}

/**
 * True when the visitor asked their OS to reduce motion.
 *
 * Components read this to swap springs and eased transitions for instant ones.
 */
export function useReducedMotion() {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
}
