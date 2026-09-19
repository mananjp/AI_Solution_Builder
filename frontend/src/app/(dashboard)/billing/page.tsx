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
      }
    }

    loadBilling();
  }, []);

  const handleTopup = async (amount: number) => {
    setTopupLoading(true);
    setTopupSuccess(null);
    try {
      await billingApi.topup(amount);
      setTopupSuccess(`Credited +${amount.toLocaleString()} credits.`);
      if (usage && usage.current_balance != null) {
        setUsage({ ...usage, current_balance: usage.current_balance + amount });
      }
    } catch {
      if (usage && usage.current_balance != null) {
        setUsage({ ...usage, current_balance: usage.current_balance + amount });
      }
      setTopupSuccess(`Credited +${amount.toLocaleString()} demo credits.`);
    } finally {
      setTopupLoading(false);
      setTimeout(() => setTopupSuccess(null), 4000);
    }
  };

  const percentUsed =
    usage && usage.current_balance != null && usage.monthly_limit
      ? Math.min(100, Math.round(((usage.credits_used ?? 0) / usage.monthly_limit) * 100))
      : 0;

  return (
    <div className="space-y-6 max-w-6xl mx-auto animate-fade-up">
      {/* Top Banner: Credit Meter */}
      <div className="p-6 rounded-xl bg-[#111] border border-[#1a1a1a] flex flex-wrap items-center justify-between gap-6">
        <div className="space-y-2 flex-1 min-w-[280px]">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#161616] border border-[#242424] text-[#818cf8] text-xs font-medium">
            <Zap className="w-3.5 h-3.5 text-[#6366f1]" />
            <span>Plan: {usage?.plan_name || 'Professional'}</span>
          </div>
          <h1 className="text-xl font-semibold text-white">AI Credits &amp; Subscription</h1>
          <p className="text-xs text-[#555] leading-relaxed">
            Credits power autonomous swarm synthesis, workable application provisioning, and component regenerations.
          </p>

          <div className="pt-2 space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-[#555]">Monthly Usage</span>
              <span className="text-white font-medium">
                {usage?.current_balance == null
                  ? 'Unlimited Credits'
                  : `${usage.current_balance.toLocaleString()} / ${(usage.monthly_limit || 0).toLocaleString()} Credits Remaining`}
              </span>
            </div>
            <div className="w-full h-1.5 bg-[#0a0a0a] rounded-full overflow-hidden border border-[#1a1a1a]">
              <div
                className="h-full bg-[#6366f1] rounded-full transition-all duration-500"
                style={{ width: `${100 - percentUsed}%` }}
              />
            </div>
          </div>
        </div>

        {/* Quick Top-Up Action */}
        <div className="p-4 rounded-lg bg-[#0a0a0a] border border-[#1a1a1a] space-y-2 min-w-[220px]">
          <span className="text-xs font-semibold text-white block">Top Up Credits</span>
          <div className="flex flex-col gap-1.5">
            <button
              onClick={() => handleTopup(5000)}
              disabled={topupLoading}
              className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-[#161616] hover:bg-[#1f1f1f] text-xs font-medium text-white border border-[#242424] transition-colors"
            >
              <span>+5,000 Credits</span>
              <span className="text-[#818cf8] font-mono">$25</span>
            </button>
            <button
              onClick={() => handleTopup(15000)}
              disabled={topupLoading}
              className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-[#6366f1] hover:bg-[#5558dd] text-xs font-medium text-white transition-colors"
            >
              <span>+15,000 Credits</span>
              <span className="text-white font-mono">$60</span>
            </button>
          </div>
          {topupSuccess && (
            <p className="text-[11px] text-[#4ade80] font-medium">{topupSuccess}</p>
          )}
        </div>
      </div>

      {/* Subscription Plans */}
      <div className="space-y-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Subscription Plans</h2>
          <p className="text-xs text-[#555] mt-0.5">Scale your architecture capability as your team grows</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {plans.map((p) => {
            const isPro = p.id === 'pro';
            return (
              <div
                key={p.id}
                className={`p-5 rounded-xl border flex flex-col justify-between transition-colors ${isPro
                    ? 'bg-[#111] border-[#6366f150]'
                    : 'bg-[#111] border-[#1a1a1a]'
                  }`}
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-sm text-white">{p.name}</h3>
                    {isPro && <span className="badge badge-blue">Popular</span>}
                  </div>

                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl font-semibold text-white">${p.price_usd}</span>
                    <span className="text-xs text-[#555]">/month</span>
                  </div>

                  <p className="text-xs text-[#a1a1a1]">
                    <strong className="text-white">{p.monthly_credits.toLocaleString()}</strong> credits included
                  </p>

                  <ul className="space-y-2 pt-2 text-xs text-[#666]">
                    {p.features.map((feat, idx) => (
                      <li key={idx} className="flex items-center gap-2">
                        <Check className="w-3.5 h-3.5 text-[#4ade80] shrink-0" />
                        <span>{feat}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="pt-4 mt-4 border-t border-[#1a1a1a]">
                  <button
                    className={`w-full py-2 rounded-lg text-xs font-medium transition-colors ${isPro
                        ? 'bg-[#6366f1] hover:bg-[#5558dd] text-white'
                        : 'bg-[#161616] hover:bg-[#1f1f1f] text-[#a1a1a1] border border-[#242424]'
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
      <div className="p-5 rounded-xl bg-[#111] border border-[#1a1a1a] space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Clock className="w-4 h-4 text-[#6366f1]" />
            <span>Credit Consumption Ledger</span>
          </h2>
          <span className="text-xs text-[#555]">Real-Time Metering</span>
        </div>

        <div className="border border-[#1a1a1a] rounded-lg overflow-hidden bg-[#0a0a0a]">
          <table className="w-full text-left text-xs text-[#f5f5f5]">
            <thead className="bg-[#111] text-[#555] uppercase text-[10px] tracking-wider border-b border-[#1a1a1a]">
              <tr>
                <th className="p-3">Date</th>
                <th className="p-3">Action</th>
                <th className="p-3">Description</th>
                <th className="p-3 text-right">Points</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1a1a1a]">
              {transactions.map((tx) => (
                <tr key={tx.id} className="hover:bg-[#111] transition-colors">
                  <td className="p-3 text-[#555] font-mono text-[11px]">
                    {tx.created_at ? new Date(tx.created_at).toLocaleDateString() : '-'}
                  </td>
                  <td className="p-3 font-semibold text-[#818cf8] font-mono text-[11px]">{tx.action}</td>
                  <td className="p-3 text-[#a1a1a1]">{tx.description}</td>
                  <td className="p-3 text-right font-mono font-semibold text-[11px]">
                    <span className={tx.amount > 0 ? 'text-[#4ade80]' : 'text-[#f87171]'}>
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
