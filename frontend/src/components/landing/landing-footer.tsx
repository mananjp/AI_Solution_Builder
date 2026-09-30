import Link from "next/link";

import { ActionLink } from "./action-link";
import { Container } from "./container";

const LINKS = [
  { href: "/dashboard", label: "Workspace" },
  { href: "/chat", label: "Builder" },
  { href: "/login", label: "Account" },
] as const;

export function LandingFooter() {
  return (
    <footer className="border-t border-border">
      <Container className="flex flex-col items-center justify-between py-12 text-xs text-muted md:flex-row">
        <div className="flex items-center gap-4">
          <span className="font-sanskrit text-xl text-foreground">सूत्र</span>
          <p className="font-bold uppercase tracking-widest">Sutra OS</p>
        </div>
        <nav className="mt-6 flex flex-wrap items-center gap-1 md:mt-0">
          {LINKS.map((link) => (
            <ActionLink key={link.href} tone="quiet">
              <Link href={link.href}>{link.label}</Link>
            </ActionLink>
          ))}
        </nav>
      </Container>
    </footer>
  );
}
