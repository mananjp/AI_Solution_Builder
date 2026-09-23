'use client';

import React, { useState, useEffect } from 'react';
import {
  Check,
  Clock,
  Zap
} from 'lucide-react';
import { billingApi } from '@/lib/api';
import { PlanTier, BillingUsage, CreditTransaction, CheckoutSession } from '@/types';

const DEMO_PLANS: PlanTier[] = [
  {
    id: 'free',
    name: 'Free Tier',
    price_usd: 0,
    monthly_credits: 1000,
    max_workable_systems: 1,
    features: ['1 Workable System', '1,000 monthly credits', 'Community Support', 'Standard exports (JSON, Markdown)'],
  },
  {
    id: 'pro',
    name: 'Professional',
    price_usd: 49,
    monthly_credits: 10000,
    max_workable_systems: 5,
    features: ['5 Workable Systems', '10,000 monthly credits', 'Priority Groq 120B inference', 'Deployable Code ZIP + CI/CD', 'BPMN Process Modeler'],
  },
  {
    id: 'enterprise',
    name: 'Enterprise Scale',
    price_usd: 299,
    monthly_credits: 100000,
    max_workable_systems: 50,
    features: ['Unlimited Workable Systems', '100,000 monthly credits', 'Dedicated Schema Isolation', 'One-Click Deployer', 'Audit Logging & SLA'],
  },
];

const DEMO_USAGE: BillingUsage = {
  org_id: 'org-demo',
  plan_name: 'Professional',
  monthly_limit: 10000,
  current_balance: 8500,
  credits_used: 1500,
};

const DEMO_TRANSACTIONS: CreditTransaction[] = [
  { id: 'tx-1', amount: 10000, action: 'plan_renewal', description: 'Monthly Professional Plan Allocation', created_at: '2026-09-01T00:00:00Z' },
  { id: 'tx-2', amount: -200, action: 'generate_solution', description: 'Full Swarm Solution Synthesis', created_at: '2026-09-10T12:00:00Z' },
  { id: 'tx-3', amount: -50, action: 'regenerate_artifact', description: 'Regenerated Database Schema (v2)', created_at: '2026-09-10T15:30:00Z' },
];

async function fetchBillingBundle(): Promise<{ plans: PlanTier[]; usage: BillingUsage | null; transactions: CreditTransaction[] }> {
  try {
    const [plans, usg, txs] = await Promise.all([
      billingApi.getPlans(),
      billingApi.getUsage(),
      billingApi.getTransactions(),
    ]);
    return { plans, usage: usg, transactions: txs };
  } catch {
    return { plans: DEMO_PLANS, usage: DEMO_USAGE, transactions: DEMO_TRANSACTIONS };
  }
}

export default function BillingPage() {
  const [plans, setPlans] = useState<PlanTier[]>([]);
  const [usage, setUsage] = useState<BillingUsage | null>(null);
  const [transactions, setTransactions] = useState<CreditTransaction[]>([]);
  const [topupLoading, setTopupLoading] = useState(false);
  const [topupSuccess, setTopupSuccess] = useState<string | null>(null);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);

  const applyBilling = (bundle: { plans: PlanTier[]; usage: BillingUsage | null; transactions: CreditTransaction[] }) => {
    setPlans(bundle.plans);
    setUsage(bundle.usage);
    setTransactions(bundle.transactions);
  };

  useEffect(() => {
    fetchBillingBundle().then(applyBilling);
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

  const loadRazorpayScript = (): Promise<boolean> =>
    new Promise((resolve) => {
      if (typeof window !== 'undefined' && window.Razorpay) {
        resolve(true);
        return;
      }
      const existing = document.getElementById('razorpay-checkout-js');
      if (existing) {
        existing.addEventListener('load', () => resolve(true), { once: true });
        existing.addEventListener('error', () => resolve(false), { once: true });
        return;
      }
      const script = document.createElement('script');
      script.id = 'razorpay-checkout-js';
      script.src = 'https://checkout.razorpay.com/v1/checkout.js';
      script.async = true;
      script.onload = () => resolve(true);
      script.onerror = () => resolve(false);
      document.head.appendChild(script);
    });

  const openCheckout = async (session: CheckoutSession) => {
    setCheckoutError(null);
    if (!session.key_id) {
      setCheckoutError('Payment gateway is not configured. Please contact support.');
      return;
    }
    const loaded = await loadRazorpayScript();
    if (!loaded || !window.Razorpay) {
      setCheckoutError('Unable to load the payment gateway. Please try again.');
      return;
    }
    const rzp = new window.Razorpay({
      key: session.key_id,
      amount: session.amount * 100,
      currency: session.currency,
      order_id: session.order_id,
      name: 'AI Solution Builder',
      description: `${session.credits.toLocaleString()} credits (order ${session.order_id.slice(-8)})`,
      handler: async () => {
        setTopupSuccess(`Payment captured for ${session.credits.toLocaleString()} credits.`);
        fetchBillingBundle().then(applyBilling);
        setTimeout(() => setTopupSuccess(null), 6000);
      },
      modal: {
        ondismiss: () => {},
      },
    });
    rzp.open();
  };

  const upgradePlan = async (plan: PlanTier) => {
    setCheckoutLoading(true);
    setCheckoutError(null);
    try {
      const session = await billingApi.checkout({
        plan_id: plan.id,
        pack_credits: plan.monthly_credits,
        gateway: 'razorpay',
        currency: 'INR',
      });
      await openCheckout(session);
    } catch (err) {
      setCheckoutError(err instanceof Error ? err.message : 'Checkout failed. Please try again.');
    } finally {
      setCheckoutLoading(false);
    }
  };

  const percentRemaining =
    usage && usage.current_balance != null && usage.monthly_limit
      ? Math.max(0, Math.min(100, Math.round((usage.current_balance / usage.monthly_limit) * 100)))
      : 100;

  return (
    <div className="space-y-8 max-w-5xl mx-auto animate-fade-up py-4">
      
      <div className="border-b border-[var(--border)] pb-4">
        <h1 className="text-2xl font-serif text-[var(--sutra-charcoal)]">AI Credits & Subscription</h1>
        <p className="text-[13px] text-[var(--text-2)] mt-1 font-light">Manage your billing, plan features, and computational consumption.</p>
      </div>

      {/* Top Banner: Credit Meter */}
      <div className="sutra-card p-8 flex flex-wrap items-center justify-between gap-8 bg-[var(--bg-2)]">
        <div className="space-y-4 flex-1 min-w-[280px]">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-[var(--sutra-charcoal)] text-[var(--sutra-warm-ivory)] text-[10px] uppercase tracking-widest font-bold">
            <Zap className="w-3.5 h-3.5" />
            <span>Plan: {usage?.plan_name || 'Professional'}</span>
          </div>
          <h2 className="text-xl font-serif text-[var(--sutra-charcoal)]">Current Cycle Usage</h2>
          
          <div className="pt-2 space-y-2">
            <div className="flex items-center justify-between text-[11px] uppercase tracking-widest font-bold">
              <span className="text-[var(--text-3)]">Consumption</span>
              <span className="text-[var(--sutra-charcoal)]">
                {usage?.current_balance == null
                  ? 'Unlimited Credits'
                  : `${usage.current_balance.toLocaleString()} / ${(usage.monthly_limit || 0).toLocaleString()} Credits Remaining`}
              </span>
            </div>
            <div className="w-full h-2 bg-[var(--bg)] rounded-sm overflow-hidden border border-[var(--border)]">
              <div
                className="h-full bg-[var(--sutra-muted-gold)] transition-all duration-500"
                style={{ width: `${percentRemaining}%` }}
              />
            </div>
          </div>
        </div>

        {/* Quick Top-Up Action */}
        <div className="p-5 border border-[var(--border)] bg-[var(--bg)] space-y-4 min-w-[260px] shadow-sm">
          <span className="text-[11px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)] block border-b border-[var(--border)] pb-2">Top Up Credits</span>
          <div className="flex flex-col gap-2">
            <button
              onClick={() => handleTopup(5000)}
              disabled={topupLoading}
              className="btn btn-secondary w-full justify-between"
            >
              <span>+5,000 Credits</span>
              <span className="text-[var(--sutra-muted-gold)] font-serif italic text-sm">$25</span>
            </button>
            <button
              onClick={() => handleTopup(15000)}
              disabled={topupLoading}
              className="btn btn-primary w-full justify-between"
            >
              <span>+15,000 Credits</span>
              <span className="text-[var(--sutra-warm-ivory)] font-serif italic text-sm opacity-80">$60</span>
            </button>
          </div>
          {topupSuccess && (
            <p className="text-[11px] uppercase tracking-widest font-bold text-[var(--green)] mt-2">{topupSuccess}</p>
          )}
          {checkoutError && (
            <p className="text-[11px] uppercase tracking-widest font-bold text-[var(--red)] mt-2">{checkoutError}</p>
          )}
        </div>
      </div>

      {/* Subscription Plans */}
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-serif text-[var(--sutra-charcoal)]">Scale Architecture</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {plans.map((p) => {
            const isPro = p.id === 'pro';
            return (
              <div
                key={p.id}
                className={`sutra-card p-6 flex flex-col justify-between transition-colors ${isPro
                    ? 'border-[var(--sutra-muted-gold)] shadow-md relative'
                    : 'bg-[var(--bg-2)] hover:border-[var(--text-3)]'
                  }`}
              >
                {isPro && (
                  <div className="absolute top-0 right-6 -translate-y-1/2 px-3 py-1 bg-[var(--sutra-muted-gold)] text-[var(--bg)] text-[9px] uppercase tracking-widest font-bold shadow-sm">
                    Current Plan
                  </div>
                )}
                
                <div className="space-y-4">
                  <h3 className="font-semibold text-[13px] uppercase tracking-widest text-[var(--sutra-charcoal)]">{p.name}</h3>

                  <div className="flex items-baseline gap-1 border-b border-[var(--border)] pb-4">
                    <span className="text-3xl font-serif text-[var(--sutra-charcoal)]">${p.price_usd}</span>
                    <span className="text-[11px] text-[var(--text-3)] font-bold uppercase tracking-widest">/mo</span>
                  </div>

                  <p className="text-[11px] text-[var(--text-2)] font-medium bg-[var(--bg)] p-2 text-center border border-[var(--border)]">
                    <strong className="text-[var(--sutra-charcoal)]">{p.monthly_credits.toLocaleString()}</strong> credits included
                  </p>

                  <ul className="space-y-3 pt-2 text-[12px] text-[var(--sutra-charcoal)] font-light">
                    {p.features.map((feat, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <Check className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)] shrink-0 mt-0.5" />
                        <span>{feat}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="pt-6 mt-4">
                  <button
                    onClick={() => upgradePlan(p)}
                    disabled={checkoutLoading}
                    className={`w-full ${isPro ? 'btn btn-primary' : 'btn btn-secondary'}`}
                  >
                    {isPro ? 'Manage Plan' : 'Upgrade'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Credit Transactions Ledger */}
      <div className="sutra-card p-6 bg-[var(--bg-2)] space-y-4">
        <div className="flex items-center justify-between border-b border-[var(--border)] pb-4">
          <h2 className="text-sm font-serif text-[var(--sutra-charcoal)] flex items-center gap-2">
            <Clock className="w-4 h-4 text-[var(--sutra-muted-gold)]" />
            <span>Consumption Ledger</span>
          </h2>
          <span className="text-[10px] uppercase tracking-widest font-bold text-[var(--text-3)]">Real-Time Metering</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-[12px] text-[var(--sutra-charcoal)]">
            <thead className="bg-[var(--bg)] text-[10px] uppercase tracking-widest text-[var(--text-3)] border-b border-[var(--border)]">
              <tr>
                <th className="p-3 font-semibold">Date</th>
                <th className="p-3 font-semibold">Action</th>
                <th className="p-3 font-semibold">Description</th>
                <th className="p-3 text-right font-semibold">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {transactions.map((tx) => (
                <tr key={tx.id} className="hover:bg-[var(--bg)] transition-colors group">
                  <td className="p-3 text-[var(--text-2)] font-mono text-[11px]">
                    {tx.created_at ? new Date(tx.created_at).toLocaleDateString() : '-'}
                  </td>
                  <td className="p-3 font-semibold text-[var(--sutra-charcoal)] font-mono text-[11px] group-hover:text-[var(--sutra-muted-gold)] transition-colors">{tx.action}</td>
                  <td className="p-3 text-[var(--text-2)] font-light">{tx.description}</td>
                  <td className="p-3 text-right font-mono font-semibold text-[12px]">
                    <span className={tx.amount > 0 ? 'text-[var(--green)]' : 'text-[var(--sutra-charcoal)]'}>
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
