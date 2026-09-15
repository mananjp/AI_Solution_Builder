'use client';

import React, { useEffect, useRef } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { ArrowRight } from '@phosphor-icons/react/dist/ssr/ArrowRight';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

function Reveal({ children, className = '', delay = 0 }: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          el.style.opacity = '1';
          el.style.transform = 'translateY(0)';
          obs.unobserve(el);
        }
      },
      { threshold: 0.08 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: 0,
        transform: 'translateY(20px)',
        transition: `opacity 0.6s cubic-bezier(0.16,1,0.3,1) ${delay}s, transform 0.6s cubic-bezier(0.16,1,0.3,1) ${delay}s`,
      }}
    >
      {children}
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground grain">
      {/* Top bar */}
      <header className="fixed top-0 left-0 right-0 z-50 h-12 border-b border-border bg-background/80 backdrop-blur-xl flex items-center justify-between px-6 lg:px-10">
        <div className="flex items-center gap-8">
          <span className="font-semibold text-[15px] tracking-tight">
            AI Solution<span className="text-primary ml-1 font-mono text-[10px] tracking-[0.15em] uppercase">Builder</span>
          </span>
          <span className="hidden md:block text-[11px] text-muted-foreground font-mono">
            multi-agent architecture engine
          </span>
        </div>
        <div className="flex items-center gap-5">
          <Link href="/login" className="text-[12px] text-muted-foreground hover:text-foreground transition-colors">
            Sign in
          </Link>
          <Button render={<Link href="/dashboard" />} nativeButton={false} size="sm" className="bg-primary text-primary-foreground hover:bg-primary/90 font-medium text-[12px] px-4">
            Open studio
          </Button>
        </div>
      </header>

      <main className="pt-14">
        {/* HERO */}
        <section className="min-h-[100dvh] flex items-center px-6 lg:px-10">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-6 items-center w-full">
            <div className="lg:col-span-6">
              <Reveal>
                <h1 className="text-[clamp(2.2rem,5vw,4.5rem)] font-bold leading-[1.02] tracking-[-0.03em]">
                  Describe your system.
                  <br />
                  <span className="text-primary">We build it.</span>
                </h1>
              </Reveal>
              <Reveal delay={0.05}>
                <p className="mt-6 text-[15px] text-muted-foreground max-w-md leading-relaxed">
                  Six autonomous agents handle the full pipeline. From a rough
                  prompt or document upload to live PostgreSQL schemas, REST APIs,
                  and deployable code. Not mockups.
                </p>
              </Reveal>
              <Reveal delay={0.1}>
                <div className="mt-8 flex items-center gap-4">
<Button render={<Link href="/chat" />} nativeButton={false} className="bg-primary text-primary-foreground hover:bg-primary/90 font-semibold text-[13px]">
                    Start building
                    <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                  </Button>
                  <Button render={<Link href="/dashboard" />} nativeButton={false} variant="outline" className="border-border text-foreground hover:bg-accent font-medium text-[13px]">
                    View workspaces
                  </Button>
                </div>
              </Reveal>
            </div>

            <div className="lg:col-span-6">
              <Reveal delay={0.15}>
                <div className="relative rounded-lg overflow-hidden border border-border">
                  <Image
                    src="https://picsum.photos/seed/ai-arch-dashboard/800/520"
                    alt="AI Solution Builder dashboard showing architecture workspace"
                    width={800}
                    height={520}
                    className="w-full h-auto object-cover"
                    priority
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-background/60 via-transparent to-transparent" />
                </div>
              </Reveal>
            </div>
          </div>
        </section>

        {/* HOW IT WORKS */}
        <section className="px-6 lg:px-10 py-20 lg:py-28">
          <Reveal>
            <h2 className="text-[clamp(1.5rem,3vw,2.5rem)] font-bold tracking-tight mb-14 max-w-xl">
              From rough idea to production artifacts.
            </h2>
          </Reveal>

          <div className="flex flex-col">
            {[
              {
                title: 'Ingest anything',
                body: 'PDFs, DOCX, CSV schemas, Excel, OpenAPI specs, raw URLs. The parser normalizes every format into structured text that the agents consume.',
              },
              {
                title: 'Autonomous analysis',
                body: 'Six specialized agents run in sequence: domain classification, module recommendation, architecture design, UX wireframing, database engineering, blueprint synthesis.',
              },
              {
                title: 'Production artifacts',
                body: 'HLD, LLD, ER diagrams, PostgreSQL DDL with row-level security, OpenAPI 3.1 specs, BPMN 2.0 workflows, responsive wireframes, delivery roadmaps.',
              },
              {
                title: 'Mounted live systems',
                body: 'Tenant-isolated PostgreSQL schemas provisioned automatically. Dynamic CRUD REST endpoints generated from the schema. Synthetic data seeded. Interactive sandbox.',
              },
              {
                title: 'One-click deploy',
                body: 'Push the generated codebase to a fresh GitHub repository with Render blueprint auto-deploy. Dockerfile, CI workflow, and infrastructure included.',
              },
            ].map((item, i) => (
              <Reveal key={item.title} delay={i * 0.04}>
                <div className="grid grid-cols-12 gap-4 py-6 border-t border-border group">
                  <div className="col-span-2 md:col-span-1">
                    <span className="font-mono text-[11px] text-primary">{String(i + 1).padStart(2, '0')}</span>
                  </div>
                  <div className="col-span-10 md:col-span-3">
                    <h3 className="text-[15px] font-semibold group-hover:text-primary transition-colors">
                      {item.title}
                    </h3>
                  </div>
                  <div className="col-span-12 md:col-span-8">
                    <p className="text-[13px] text-muted-foreground leading-relaxed max-w-2xl">
                      {item.body}
                    </p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        {/* ARCHITECTURE */}
        <section className="px-6 lg:px-10 py-20 lg:py-28">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">
            <div className="lg:col-span-5">
              <Reveal>
                <h2 className="text-[clamp(1.5rem,3vw,2.2rem)] font-bold tracking-tight leading-snug">
                  Five services.
                  <br />
                  One shared volume.
                  <br />
                  <span className="text-muted-foreground">Zero network hops.</span>
                </h2>
              </Reveal>
              <Reveal delay={0.05}>
                <p className="mt-6 text-[13px] text-muted-foreground leading-relaxed max-w-md">
                  The backend and OpenCode sidecar share a Docker volume.
                  Generated source files are visible to the API instantly.
                  No polling, no file transfer, no race conditions.
                </p>
              </Reveal>
            </div>

            <div className="lg:col-span-7">
              <Reveal delay={0.1}>
                <div className="border border-border bg-card rounded-lg overflow-hidden">
                  <div className="px-3 py-2 border-b border-border">
                    <span className="font-mono text-[9px] text-muted-foreground tracking-wider uppercase">
                      service topology
                    </span>
                  </div>
                  <div className="p-6 font-mono text-[12px] leading-[2] text-muted-foreground">
                    <div><span className="text-primary">frontend</span><span className="text-muted-foreground/60">:3000</span> <span className="text-muted-foreground/60">next.js standalone</span></div>
                    <div><span className="text-muted-foreground/60">  |</span></div>
                    <div><span className="text-muted-foreground/60">  +--&gt;</span> <span className="text-foreground">backend</span><span className="text-muted-foreground/60">:8000</span> <span className="text-muted-foreground/60">fastapi + langgraph</span></div>
                    <div><span className="text-muted-foreground/60">  |     +--&gt;</span> <span className="text-foreground">postgres</span><span className="text-muted-foreground/60">:5432</span> <span className="text-muted-foreground/60">pgvector + rls</span></div>
                    <div><span className="text-muted-foreground/60">  |     +--&gt;</span> <span className="text-foreground">redis</span><span className="text-muted-foreground/60">:6379</span> <span className="text-muted-foreground/60">rate limit + cache</span></div>
                    <div><span className="text-muted-foreground/60">  |     +--&gt;</span> <span className="text-foreground">opencode</span><span className="text-muted-foreground/60">:4096</span> <span className="text-muted-foreground/60">mvp-builder agent</span></div>
                    <div><span className="text-muted-foreground/60">  |</span></div>
                    <div><span className="text-muted-foreground/60">  +--&gt;</span> <span className="text-primary">shared volume</span> <span className="text-muted-foreground/60">mvp_workspace</span></div>
                    <div className="mt-3 pt-3 border-t border-border"><span className="text-success">status: all healthy</span></div>
                  </div>
                </div>
              </Reveal>
            </div>
          </div>
        </section>

        {/* STATS */}
        <section className="px-6 lg:px-10 py-16">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-8 lg:gap-12">
            {[
              { value: '6', label: 'agents in the swarm' },
              { value: '7+', label: 'input formats' },
              { value: '9', label: 'artifact types' },
              { value: '1-click', label: 'github deploy' },
            ].map((s) => (
              <Reveal key={s.label}>
                <div>
                  <p className="text-[clamp(2rem,4vw,3.5rem)] font-bold text-primary leading-none tracking-tight">
                    {s.value}
                  </p>
                  <p className="mt-2 font-mono text-[10px] text-muted-foreground tracking-wider uppercase">
                    {s.label}
                  </p>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        {/* CTA */}
        <section className="px-6 lg:px-10 py-20 lg:py-28">
          <Reveal>
            <div className="max-w-2xl">
              <h2 className="text-[clamp(1.5rem,3vw,2.5rem)] font-bold tracking-tight">
                Describe your system in plain language.
              </h2>
              <p className="mt-4 text-[15px] text-muted-foreground max-w-lg">
                The agent swarm handles the rest. Upload a document, paste a
                URL, or just tell it what you need.
              </p>
              <div className="mt-8">
                <Button render={<Link href="/chat" />} nativeButton={false} className="bg-primary text-primary-foreground hover:bg-primary/90 font-semibold text-[13px]">
                  Launch the architect
                  <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                </Button>
              </div>
            </div>
          </Reveal>
        </section>

        {/* Footer */}
        <footer className="px-6 lg:px-10 py-6 border-t border-border flex items-center justify-between text-[11px] text-muted-foreground font-mono">
          <span>2026 AI Solution Builder</span>
          <div className="flex items-center gap-5">
            <Link href="/dashboard" className="hover:text-foreground transition-colors">Dashboard</Link>
            <Link href="/chat" className="hover:text-foreground transition-colors">Architect</Link>
            <Link href="/login" className="hover:text-foreground transition-colors">Account</Link>
          </div>
        </footer>
      </main>
    </div>
  );
}
