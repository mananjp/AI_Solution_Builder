"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { SkiperBadge } from "@/components/ui/skiper-ui/skiper-badge";
import { Link001 } from "@/components/ui/skiper-ui/skiper40";
import { Sparkles, ArrowRight, Layers, Database, ShieldCheck } from "lucide-react";

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-50 text-slate-900">
      {/* Decorative ambient background */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 right-1/4 h-96 w-96 rounded-full bg-indigo-500/10 blur-3xl" />
        <div className="absolute top-60 left-1/3 h-80 w-80 rounded-full bg-violet-500/10 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-6xl px-6 py-16">
        {/* Header Hero */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
          className="rounded-3xl border border-slate-200/90 bg-white/80 p-8 shadow-sm backdrop-blur-md md:p-12"
        >
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-600 text-white shadow-md shadow-indigo-500/20">
                <Sparkles className="h-6 w-6" />
              </span>
              <div>
                <h1 className="text-3xl font-extrabold tracking-tight md:text-4xl text-slate-900">
                  __APP_TITLE__
                </h1>
                <p className="mt-1 text-sm font-medium text-slate-500">
                  Autonomous MVP built by AI Solution Builder &amp; OpenCode
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <SkiperBadge variant="purple" pulse>
                Active Prototype
              </SkiperBadge>
              <SkiperBadge variant="success" pulse={false}>
                Ready
              </SkiperBadge>
            </div>
          </div>

          <p className="mt-6 max-w-2xl text-base leading-relaxed text-slate-600">
            A verified, interactive business solution prototype engineered with Next.js App Router,
            Tailwind CSS, and motion-forward UI components.
          </p>

          {/* Quick Metrics */}
          <div className="mt-8 grid grid-cols-2 gap-4 border-y border-slate-100 py-6 sm:grid-cols-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-700">
                <Layers className="h-5 w-5" />
              </div>
              <div>
                <div className="text-xl font-bold text-slate-900">Production-Ready</div>
                <div className="text-xs text-slate-500">Architecture</div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-700">
                <Database className="h-5 w-5" />
              </div>
              <div>
                <div className="text-xl font-bold text-indigo-700">REST + Async DB</div>
                <div className="text-xs text-slate-500">FastAPI backend</div>
              </div>
            </div>

            <div className="col-span-2 sm:col-span-1 flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <div>
                <div className="text-xl font-bold text-emerald-700">Acceptance Tests</div>
                <div className="text-xs text-slate-500">Pytest verified</div>
              </div>
            </div>
          </div>

          {/* Module navigation cards */}
          <div className="mt-8">
            <h2 className="text-sm font-semibold tracking-wider text-slate-400 uppercase">
              Application Modules &amp; Interfaces
            </h2>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {/* __MODULE_LINKS__ */}
            </div>
          </div>

          <div className="mt-10 flex items-center justify-between border-t border-slate-100 pt-6 text-xs text-slate-500">
            <span>Powered by OpenCode AI &amp; Skiper UI Registry</span>
            <Link001 href="/api/docs" className="text-indigo-600 hover:text-indigo-800">
              API Documentation
            </Link001>
          </div>
        </motion.div>
      </div>
    </main>
  );
}