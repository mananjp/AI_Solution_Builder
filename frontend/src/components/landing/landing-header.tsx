"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { LanguageSelector } from "@/components/LanguageSelector";
import { ThemeToggleButton } from "@/components/ThemeToggle";
import { ActionLink } from "./action-link";
import { Container } from "./container";

/**
 * Landing header.
 *
 * Sticky rather than absolutely positioned: as an absolutely positioned element
 * inside the page root it scrolled away, taking the sign-in and theme controls
 * with it, so a visitor who had to scroll could not reach either.
 */
export function LandingHeader() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/80 backdrop-blur-md">
      <Container className="flex h-20 items-center justify-between">
        <Link
          href="/"
          className="font-sanskrit text-4xl font-bold leading-none text-foreground"
        >
          सूत्र
        </Link>

        <div className="flex items-center gap-2 md:gap-3">
          {/* `lg` so it lines up with the 40px theme toggle and the nav-scale
              action links beside it. */}
          <LanguageSelector compact size="lg" />
          {/* The landing page has its own header rather than the app Navbar, so
              the scheme control has to be mounted here too. Without it a
              visitor on a light-mode machine has no way to reach the dark
              palette, since every token resolves against data-theme. */}
          <ThemeToggleButton />
          <ActionLink tone="quiet">
            <Link href="/login">Sign in</Link>
          </ActionLink>
          <ActionLink>
            <Link href="/dashboard">
              Workspace <ArrowRight />
            </Link>
          </ActionLink>
        </div>
      </Container>
    </header>
  );
}
