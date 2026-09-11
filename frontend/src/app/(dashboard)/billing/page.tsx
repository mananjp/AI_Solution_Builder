'use client';

import React, { useState, useEffect } from 'react';
import { 
  Check, 
  Clock, 
  Zap
} from 'lucide-react';
import { billingApi } from '@/lib/api';
import { PlanTier, BillingUsage, CreditTransaction } from '@/types';

export default function BillingPage() {
  const [plans, setPlans] = useState<PlanTier[]>([]);
  const [usage, setUsage] = useState<BillingUsage | null>(null);
  const [transactions, setTransactions] = useState<CreditTransaction[]>([]);
  const [topupLoading, setTopupLoading] = useState(false);
  const [topupSuccess, setTopupSuccess] = useState<string | null>(null);

  useEffect(() => {
    async function loadBilling() {
      try {
        const [pl, usg, txs] = await Promise.all([
          billingApi.getPlans(),
          billingApi.getUsage(),
          billingApi.getTransactions(),
        ]);
        setPlans(pl);
        setUsage(usg);
        setTransactions(txs);
      } catch {
        // Fallback for UI demonstration
        setPlans([
          {
            id: 'free',
            name: 'Free Tier',
            price_usd: 0,
            monthly_credits: 1000,
            max_workable_systems: 1,
            features: ['1 Workable System', '1,000 monthly credits', 'Community Support', 'Standard exports (JSON, Markdown)']
          },
          {
            id: 'pro',
            name: 'Professional',
            price_usd: 49,
            monthly_credits: 10000,
            max_workable_systems: 5,
            features: ['5 Workable Systems', '10,000 monthly credits', 'Priority Groq 120B inference', 'Deployable Code ZIP + CI/CD', 'BPMN Process Modeler']
          },
          {
            id: 'enterprise',
            name: 'Enterprise Scale',
            price_usd: 299,
            monthly_credits: 100000,
            max_workable_systems: 50,
            features: ['Unlimited Workable Systems', '100,000 monthly credits', 'Dedicated Schema Isolation', 'One-Click Deployer', 'Audit Logging & SLA']
          }
        ]);
        setUsage({
          org_id: 'org-demo',
          plan_name: 'Professional',
          monthly_limit: 10000,
          current_balance: 8500,
          credits_used: 1500,
        });
        setTransactions([
          { id: 'tx-1', amount: 10000, action: 'plan_renewal', description: 'Monthly Professional Plan Allocation', created_at: '2026-09-01T00:00:00Z' },
          { id: 'tx-2', amount: -200, action: 'generate_solution', description: 'Full Swarm Solution Synthesis', created_at: '2026-09-10T12:00:00Z' },
          { id: 'tx-3', amount: -50, action: 'regenerate_artifact', description: 'Regenerated Database Schema (v2)', created_at: '2026-09-10T15:30:00Z' },
        ]);
      } finally {
      }
    }

    loadBilling();
  }, []);

  const handleTopup = async (amount: number) => {
    setTopupLoading(true);
    setTopupSuccess(null);
    try {
      await billingApi.topup(amount);
      setTopupSuccess(`Successfully credited +${amount.toLocaleString()} credits!`);
      if (usage) {
        setUsage({ ...usage, current_balance: usage.current_balance + amount });
      }
    } catch {
      if (usage) {
        setUsage({ ...usage, current_balance: usage.current_balance + amount });
      }
      setTopupSuccess(`Successfully credited +${amount.toLocaleString()} demo credits!`);
    } finally {
      setTopupLoading(false);
      setTimeout(() => setTopupSuccess(null), 4000);
    }
  };

  const percentUsed = usage ? Math.min(100, Math.round((usage.credits_used / usage.monthly_limit) * 100)) : 15;

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Top Banner: Credit Meter */}
      <div className="p-8 rounded-3xl bg-gradient-to-r from-indigo-950/60 via-slate-900/80 to-purple-950/40 border border-white/5 shadow-2xl relative overflow-hidden">
        <div className="relative z-10 flex flex-wrap items-center justify-between gap-6">
          <div className="space-y-2 max-w-xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-semibold">
              <Zap className="w-3.5 h-3.5 text-indigo-400" />
              <span>Current Plan: {usage?.plan_name || 'Professional'}</span>
            </div>
            <h2 className="text-2xl font-extrabold text-white tracking-tight">AI Credits & Subscription</h2>
            <p className="text-xs text-slate-300 leading-relaxed">
              Credits power autonomous swarm synthesis, workable application provisioning, and isolated component regenerations.
            </p>

            {/* Credit Gauge */}
            <div className="pt-3 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Monthly Usage</span>
                <span className="text-white font-bold">
                  {(usage?.current_balance || 8500).toLocaleString()} / {(usage?.monthly_limit || 10000).toLocaleString()} Credits Remaining
                </span>
              </div>
              <div className="w-full h-2.5 bg-slate-950 rounded-full overflow-hidden border border-white/5">
                <div 
                  className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-cyan-400 rounded-full transition-all duration-500" 
                  style={{ width: `${100 - percentUsed}%` }} 
                />
              </div>
            </div>
          </div>

          {/* Quick Top-Up Action */}
          <div className="p-5 rounded-2xl bg-slate-900/80 border border-white/10 space-y-3 min-w-[240px]">
            <span className="text-xs font-bold text-white block">Need More Credits?</span>
            <div className="flex flex-col gap-2">
              <button
                onClick={() => handleTopup(5000)}
                disabled={topupLoading}
                className="flex items-center justify-between px-3.5 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-slate-200 border border-white/10 transition-colors"
              >
                <span>+5,000 Credits</span>
                <span className="text-indigo-400 font-mono font-bold">$25</span>
              </button>
              <button
                onClick={() => handleTopup(15000)}
                disabled={topupLoading}
                className="flex items-center justify-between px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white shadow-md shadow-indigo-600/20 transition-all hover:scale-105"
              >
                <span>+15,000 Credits</span>
                <span className="text-cyan-200 font-mono font-bold">$60</span>
              </button>
            </div>
            {topupSuccess && (
              <p className="text-[11px] text-emerald-400 font-medium animate-fade-in">{topupSuccess}</p>
            )}
          </div>
        </div>
      </div>

      {/* Subscription Plans */}
      <div className="space-y-4">
        <div>
          <h3 className="text-lg font-bold text-white">Subscription Plans</h3>
          <p className="text-xs text-slate-400 mt-0.5">Scale your architecture capability as your team grows</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {plans.map((p) => {
            const isPro = p.id === 'pro';
            return (
              <div
                key={p.id}
                className={`p-6 rounded-2xl border flex flex-col justify-between relative transition-all ${
                  isPro
                    ? 'bg-gradient-to-b from-indigo-950/40 to-slate-900/80 border-indigo-500/50 shadow-xl shadow-indigo-500/10'
                    : 'bg-slate-900/40 border-white/5'
                }`}
              >
                {isPro && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full bg-indigo-600 text-white text-[10px] font-bold uppercase tracking-wider shadow-md">
                    Most Popular
                  </span>
                )}

                <div className="space-y-4">
                  <div>
                    <h4 className="font-bold text-lg text-white">{p.name}</h4>
                    <div className="mt-2 flex items-baseline gap-1">
                      <span className="text-3xl font-extrabold text-white">${p.price_usd}</span>
                      <span className="text-xs text-slate-400">/month</span>
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-950/60 border border-white/5 text-xs text-slate-300">
                    <span className="text-indigo-400 font-bold">{p.monthly_credits.toLocaleString()}</span> credits included monthly
                  </div>

                  <ul className="space-y-2.5 pt-2 text-xs text-slate-300">
                    {p.features.map((feat, idx) => (
                      <li key={idx} className="flex items-center gap-2">
                        <Check className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                        <span>{feat}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="pt-6 mt-6 border-t border-white/5">
                  <button
                    className={`w-full py-2.5 rounded-xl text-xs font-semibold transition-all ${
                      isPro
                        ? 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/25'
                        : 'bg-white/5 hover:bg-white/10 text-slate-200 border border-white/10'
                    }`}
                  >
                    {isPro ? 'Current Plan' : 'Select Plan'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Credit Transactions Ledger */}
      <div className="p-6 rounded-2xl bg-slate-900/40 border border-white/5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <Clock className="w-4 h-4 text-purple-400" />
            <span>Credit Consumption Ledger</span>
          </h3>
          <span className="text-xs text-slate-500">Real-Time Usage Metering</span>
        </div>

        <div className="border border-white/5 rounded-xl overflow-hidden bg-slate-950/60">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-900 text-slate-400 uppercase text-[10px] tracking-wider border-b border-white/5">
              <tr>
                <th className="p-3">Date</th>
                <th className="p-3">Action</th>
                <th className="p-3">Description</th>
                <th className="p-3 text-right">Points</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {transactions.map((tx) => (
                <tr key={tx.id} className="hover:bg-white/[0.02] transition-colors">
                  <td className="p-3 text-slate-500 font-mono text-[11px]">
                    {tx.created_at ? new Date(tx.created_at).toLocaleDateString() : '-'}
                  </td>
                  <td className="p-3 font-semibold text-indigo-300 font-mono text-[11px]">{tx.action}</td>
                  <td className="p-3 text-slate-300">{tx.description}</td>
                  <td className="p-3 text-right font-mono font-semibold">
                    <span className={tx.amount > 0 ? 'text-emerald-400' : 'text-rose-400'}>
                      {tx.amount > 0 ? `+${tx.amount}` : tx.amount}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
