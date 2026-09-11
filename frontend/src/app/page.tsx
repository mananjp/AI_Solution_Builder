'use client';

import React from 'react';
import Link from 'next/link';
import { 
  Sparkles, 
  Cpu, 
  Database, 
  ArrowRight, 
  CheckCircle2, 
  Zap, 
  FileText, 
  Compass,
  Terminal
} from 'lucide-react';

export default function LandingPage() {
  const features = [
    {
      title: '6-Agent Autonomous Swarm',
      desc: 'Business Analyst, Solutions Architect, UX Specialist, Database Engineer, and Blueprint Generator work in harmony.',
      icon: Cpu,
      gradient: 'from-indigo-500 to-purple-500',
    },
    {
      title: 'Multi-Format PRD Ingestion',
      desc: 'Drag and drop PDFs, DOCX, CSV schemas, or Excel sheets. Instant text extraction and requirement synthesis.',
      icon: FileText,
      gradient: 'from-blue-500 to-cyan-500',
    },
    {
      title: 'Industry Template Intelligence',
      desc: 'Pre-seeded vertical patterns for E-Commerce, Logistics, Healthcare, FinTech, and B2B SaaS workflows.',
      icon: Compass,
      gradient: 'from-emerald-500 to-teal-500',
    },
    {
      title: 'Full Engineering Artifacts',
      desc: 'Generates production-grade HLD, LLD, ER diagrams, PostgreSQL DDL schemas, OpenAPI specs, and delivery roadmaps.',
      icon: Database,
      gradient: 'from-purple-500 to-pink-500',
    },
  ];

  return (
    <div className="min-h-screen bg-[#070a13] text-slate-100 selection:bg-indigo-500 selection:text-white relative overflow-hidden">
      {/* Dynamic Background Glows */}
      <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-indigo-600/15 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute top-1/3 right-1/4 w-[500px] h-[500px] bg-cyan-500/10 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-10 left-1/3 w-[700px] h-[700px] bg-purple-600/10 rounded-full blur-[160px] pointer-events-none" />

      {/* Grid Pattern */}
      <div className="absolute inset-0 bg-grid-pattern opacity-40 pointer-events-none" />

      {/* Navigation Header */}
      <header className="relative z-20 max-w-7xl mx-auto px-6 h-20 flex items-center justify-between border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center text-white shadow-lg shadow-indigo-500/30">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <span className="font-extrabold text-white text-lg tracking-tight">AI Solution</span>
            <span className="text-xs text-indigo-400 font-semibold tracking-wider uppercase ml-1.5 px-2 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-500/20">
              Builder OS
            </span>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <Link
            href="/login"
            className="px-4 py-2 text-xs font-semibold text-slate-300 hover:text-white hover:bg-white/5 rounded-xl transition-all"
          >
            Sign In
          </Link>
          <Link
            href="/dashboard"
            className="flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white shadow-lg shadow-indigo-500/25 transition-all hover:scale-105"
          >
            <span>Open Studio</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </header>

      {/* Hero Section */}
      <main className="relative z-10 max-w-6xl mx-auto px-6 pt-20 pb-28 text-center">
        {/* Top Badge */}
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-semibold mb-8 animate-fade-in">
          <Zap className="w-3.5 h-3.5 text-indigo-400" />
          <span>Powered by Groq 120B & LangGraph Swarm Intelligence</span>
        </div>

        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold text-white tracking-tight leading-[1.1] max-w-5xl mx-auto">
          Turn Rough Business Ideas Into{' '}
          <span className="gradient-text">Complete System Blueprints</span>{' '}
          In Minutes.
        </h1>

        <p className="mt-6 text-base sm:text-lg text-slate-400 max-w-3xl mx-auto leading-relaxed">
          Autonomous multi-agent pipeline that dissects user prompts, analyzes PRD documents, recommends vertical architectures, and generates production-ready High-Level Designs, wireframe specs, database schemas, and delivery roadmaps.
        </p>

        {/* CTA Group */}
        <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
          <Link
            href="/chat"
            className="flex items-center gap-2.5 px-6 py-3.5 rounded-2xl bg-gradient-to-r from-indigo-600 via-purple-600 to-cyan-500 hover:opacity-95 text-white font-semibold text-sm shadow-xl shadow-indigo-600/30 transition-all hover:scale-105"
          >
            <Sparkles className="w-4 h-4" />
            <span>Start AI Architecture Session</span>
          </Link>
          <Link
            href="/dashboard"
            className="flex items-center gap-2 px-6 py-3.5 rounded-2xl bg-slate-900/80 hover:bg-slate-800/80 border border-white/10 text-slate-200 font-semibold text-sm transition-all"
          >
            <span>Explore Workspaces</span>
          </Link>
        </div>

        {/* Interactive Architecture Swarm Visualizer */}
        <div className="mt-16 text-left max-w-4xl mx-auto p-1 rounded-2xl bg-gradient-to-b from-white/10 to-transparent shadow-2xl">
          <div className="bg-[#0b0f19] rounded-2xl p-6 border border-white/10 overflow-hidden">
            <div className="flex items-center justify-between pb-4 border-b border-white/5 text-xs text-slate-400">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-indigo-400" />
                <span className="font-mono text-slate-200">Autonomous Execution Pipeline</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-emerald-400 font-mono text-[11px]">System Online</span>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="p-4 rounded-xl bg-slate-900/80 border border-indigo-500/20 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-indigo-300">1. Discovery & Analysis</span>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                </div>
                <p className="text-[11px] text-slate-400">
                  User prompt parsed, confidence 94%, domain categorized as Omnichannel Retail.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/80 border border-cyan-500/20 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-cyan-300">2. Module Matching</span>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                </div>
                <p className="text-[11px] text-slate-400">
                  Synthesized 4 core subsystems: Inventory Engine, Point-of-Sale, Analytics, Loyalty.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/80 border border-purple-500/20 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-purple-300">3. Blueprint Synthesis</span>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                </div>
                <p className="text-[11px] text-slate-400">
                  Produced HLD, LLD, PostgreSQL DDL schemas, OpenAPI specs, and 12-week roadmap.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Features Grid */}
        <div className="mt-28">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <h2 className="text-2xl sm:text-3xl font-bold text-white">
              Enterprise-Grade Architecture Generation
            </h2>
            <p className="text-sm text-slate-400 mt-3">
              Everything engineering leads and product owners need to jumpstart system delivery.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-left">
            {features.map((feat, idx) => {
              const Icon = feat.icon;
              return (
                <div
                  key={idx}
                  className="p-6 rounded-2xl bg-slate-900/40 border border-white/5 hover:border-indigo-500/30 transition-all hover:bg-slate-900/60"
                >
                  <div className={`w-10 h-10 rounded-xl bg-gradient-to-tr ${feat.gradient} flex items-center justify-center text-white mb-4 shadow-md`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <h3 className="text-lg font-semibold text-white mb-2">{feat.title}</h3>
                  <p className="text-xs text-slate-400 leading-relaxed">{feat.desc}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer */}
        <footer className="mt-28 pt-8 border-t border-white/5 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-4">
          <p>© 2026 AI Solution Builder OS. Alpine PostgreSQL + Groq 120B.</p>
          <div className="flex items-center gap-6">
            <Link href="/dashboard" className="hover:text-slate-300">Dashboard</Link>
            <Link href="/chat" className="hover:text-slate-300">AI Architect</Link>
            <Link href="/login" className="hover:text-slate-300">Account</Link>
          </div>
        </footer>
      </main>
    </div>
  );
}
