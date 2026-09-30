"use client";

import { useCallback, useEffect, useState } from "react";
import { ThemeToggle } from "@/components/lab/theme-toggle";

const STORAGE_KEY = "sutra.theme";
type Scheme = "light" | "dark";

const read = (): Scheme => {
  if (typeof document === "undefined") return "light";
  const attr = document.documentElement.getAttribute("data-theme");
  return attr === "dark" ? "dark" : "light";
};

/**
 * Owns the colour scheme for the whole app.
 *
 * globals.css pairs every token with light-dark(), which resolves against the
 * element's own color-scheme. That makes the scheme a single decision made in
 * one place -- the data-theme attribute on <html> -- rather than something each
 * component has to know about. The blocking script in layout.tsx sets the
 * attribute before first paint; this keeps it correct afterwards and gives the
 * user a way to change it.
 */
export function ThemeToggleButton() {
  const [scheme, setScheme] = useState<Scheme>("light");

  // Read on mount rather than initialising from document at render time: the
  // server has no document, so the first client render must match the HTML it
  // hydrated from or React will report a mismatch.
  useEffect(() => {
    // This is an intentional post-hydration read of the document bootstrap.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setScheme(read());
  }, []);

  const apply = useCallback((next: Scheme) => {
    setScheme(next);
    document.documentElement.setAttribute("data-theme", next);
    // color-scheme drives the UA's own painting: scrollbars, form control
    // defaults, and the canvas behind a page. Leaving it to the CSS alone
    // leaves light scrollbars on a dark page.
    document.documentElement.style.colorScheme = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Private browsing can refuse writes. The attribute still applies for
      // this page view, which is better than failing the toggle outright.
    }
  }, []);

  // Until the user picks a side, keep following the system, so a machine that
  // flips to dark in the evening does not need a reload.
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e: MediaQueryListEvent) => {
      let saved: string | null = null;
      try {
        saved = localStorage.getItem(STORAGE_KEY);
      } catch {
        // Ignore and treat as "no saved choice".
      }
      if (saved === "light" || saved === "dark") return;
      const next: Scheme = e.matches ? "dark" : "light";
      document.documentElement.setAttribute("data-theme", next);
      document.documentElement.style.colorScheme = next;
      setScheme(next);
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return (
    <ThemeToggle
      dark={scheme === "dark"}
      onChange={(dark) => apply(dark ? "dark" : "light")}
      label={scheme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
    />
  );
}

export default ThemeToggleButton;
