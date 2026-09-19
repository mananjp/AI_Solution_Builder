'use client';

import React from 'react';
import Link from 'next/link';
import { Sparkles, ArrowRight, CheckCircle2, Cpu, FileText, Database, Compass } from 'lucide-react';

const features = [
  {
    title: '6-Agent Swarm',
    desc: 'Business Analyst, Solutions Architect, UX, DB and Blueprint agents collaborate via LangGraph.',
    icon: Cpu,
  },
  {
    title: 'Any PRD, Any Format',
    desc: 'Drop PDFs, DOCX, CSV schemas, or paste a URL — extracted and fed as context to every agent.',
    icon: FileText,
  },
  {
    title: 'Industry Templates',
    desc: 'Curated patterns for Commerce, Logistics, Healthcare, FinTech and B2B SaaS.',
    icon: Compass,
  },
  {
    title: 'Production Artifacts',
    desc: 'HLD, LLD, ER + DDL, OpenAPI 3.1, BPMN 2.0, 12-week roadmap — exportable to PDF/DOCX.',
    icon: Database,
  },
];

const pipeline = [
  { step: '01', label: 'Discovery & Analysis', desc: 'Prompt parsed — domain, intent, and constraints extracted.' },
  { step: '02', label: 'Module Matching', desc: 'Subsystems identified and mapped from curated templates.' },
  { step: '03', label: 'Blueprint Synthesis', desc: 'HLD, LLD, DDL, OpenAPI, BPMN, and 12-week plan generated.' },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#0a0a0a] text-[#f5f5f5]">

      {/* Nav */}
      <header className="h-14 border-b border-[#1a1a1a] flex items-center justify-between px-6 max-w-[1200px] mx-auto">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-[#6366f1] flex items-center justify-center text-white">
            <Sparkles className="w-3.5 h-3.5" />
          </div>
          <span className="text-sm font-semibold text-white">AI Solution Builder</span>
        </Link>
        <div className="flex items-center gap-2">
          <Link
            href="/login"
            className="px-3 py-1.5 text-[13px] text-[#666] hover:text-white transition-colors"
          >
            Sign in
          </Link>
          <Link
            href="/dashboard"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#6366f1] hover:bg-[#5558dd] text-white text-[13px] font-medium transition-colors"
          >
            Open Studio <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </header>

      <main className="max-w-[1000px] mx-auto px-6 py-20 space-y-20">

        {/* Hero */}
        <section className="text-center space-y-6 animate-fade-up">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#111] border border-[#242424] text-[#666] text-xs">
            <span className="animate-pulse-dot dot-green" />
            Groq 120B · LangGraph · SQLite local dev
          </div>

          <h1 className="text-[40px] sm:text-[56px] font-bold tracking-tight leading-[1.05] text-white text-balance">
            Turn rough ideas into<br />
            <span className="text-[#a1a1a1]">complete system blueprints</span>
            <br />in minutes.
          </h1>

          <p className="text-[#666] text-base max-w-[580px] mx-auto leading-relaxed text-balance">
            The autonomous pipeline that dissects prompts, ingests PRDs, recommends architectures and ships
            HLD, LLD, schemas, APIs, BPMN and roadmaps — then mounts a live working app.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/chat"
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-[#6366f1] hover:bg-[#5558dd] text-white text-sm font-medium transition-colors"
            >
              <Sparkles className="w-4 h-4" />
              Start AI Architecture Session
            </Link>
            <Link
              href="/dashboard"
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-[#111] hover:bg-[#161616] border border-[#242424] text-white text-sm font-medium transition-colors"
            >
              Explore Workspaces
            </Link>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-5 text-xs text-[#555]">
            <span className="flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-[#22c55e]" />No Docker required</span>
            <span className="flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-[#22c55e]" />Tenant-isolated schemas</span>
            <span className="flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-[#22c55e]" />2–5 min builds</span>
          </div>
        </section>

        {/* Pipeline preview */}
        <section className="border border-[#1a1a1a] rounded-xl overflow-hidden animate-fade-up" style={{ animationDelay: '0.1s' }}>
          <div className="px-5 py-3.5 border-b border-[#1a1a1a] flex items-center justify-between">
            <div className="flex items-center gap-2 text-[13px] font-medium text-white">
              Autonomous Execution Pipeline
            </div>
            <span className="badge badge-green">LIVE</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-[#1a1a1a]">
            {pipeline.map((p) => (
              <div key={p.step} className="px-5 py-5 bg-[#0a0a0a]">
                <span className="text-[11px] font-semibold text-[#444] tracking-widest">{p.step}</span>
                <p className="text-sm font-semibold text-white mt-2">{p.label}</p>
                <p className="text-[13px] text-[#666] mt-1 leading-relaxed">{p.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Features */}
        <section className="space-y-6 animate-fade-up" style={{ animationDelay: '0.2s' }}>
          <div>
            <h2 className="text-xl font-semibold text-white">Enterprise-grade generation</h2>
            <p className="text-sm text-[#666] mt-1">Everything product and engineering need to jumpstart delivery.</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {features.map((f) => {
              const Icon = f.icon;
              return (
                <div
                  key={f.title}
                  className="p-5 rounded-xl bg-[#111] border border-[#1a1a1a] hover:border-[#242424] transition-colors"
                >
                  <div className="w-8 h-8 rounded-lg bg-[#161616] border border-[#242424] flex items-center justify-center text-[#6366f1] mb-3">
                    <Icon className="w-4 h-4" />
                  </div>
                  <h3 className="text-sm font-semibold text-white">{f.title}</h3>
                  <p className="text-[13px] text-[#666] mt-1.5 leading-relaxed">{f.desc}</p>
                </div>
              );
            })}
          </div>
        </section>
      </main>

      <footer className="border-t border-[#1a1a1a] py-6 px-6 max-w-[1200px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-[#444]">
        <p>© 2026 AI Solution Builder OS</p>
        <div className="flex items-center gap-5">
          <Link href="/dashboard" className="hover:text-[#a1a1a1] transition-colors">Dashboard</Link>
          <Link href="/chat" className="hover:text-[#a1a1a1] transition-colors">AI Architect</Link>
          <Link href="/login" className="hover:text-[#a1a1a1] transition-colors">Account</Link>
        </div>
      </footer>
    </div>
  );
}
