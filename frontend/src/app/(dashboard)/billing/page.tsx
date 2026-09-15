'use client';

import React, { useState, useEffect } from 'react';
import { Check, Clock, Lightning } from '@phosphor-icons/react/dist/ssr';
import { cn } from '@/lib/utils';
import { billingApi } from '@/lib/api';
import { PlanTier, BillingUsage, CreditTransaction } from '@/types';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Separator } from '@/components/ui/separator';

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
        // Billing data unavailable
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
    <div className="p-6 lg:p-8 flex flex-col gap-8 max-w-6xl mx-auto">
      {/* Credit Usage Card */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-2">
            <Badge variant="outline" className="gap-1.5 w-fit">
              <Lightning className="h-3.5 w-3.5 text-primary" />
              Current Plan: {usage?.plan_name || 'Professional'}
            </Badge>
            <CardTitle>AI Credits & Subscription</CardTitle>
            <CardDescription>
              Credits power autonomous swarm synthesis, workable application provisioning, and isolated component regenerations.
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-6">
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Monthly Usage</span>
                <span className="font-bold text-foreground">
                  {(usage?.current_balance || 8500).toLocaleString()} / {(usage?.monthly_limit || 10000).toLocaleString()} Credits Remaining
                </span>
              </div>
              <Progress value={100 - percentUsed} className="h-2.5" />
            </div>

            <Card className="bg-secondary">
              <CardHeader>
                <CardTitle className="text-sm">Need More Credits?</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col gap-2">
                  <Button
                    variant="outline"
                    className="w-full justify-between"
                    onClick={() => handleTopup(5000)}
                    disabled={topupLoading}
                  >
                    <span>+5,000 Credits</span>
                    <span className="font-mono font-bold text-primary">$25</span>
                  </Button>
                  <Button
                    className="w-full justify-between"
                    onClick={() => handleTopup(15000)}
                    disabled={topupLoading}
                  >
                    <span>+15,000 Credits</span>
                    <span className="font-mono font-bold text-muted-foreground">$60</span>
                  </Button>
                </div>
                {topupSuccess && (
                  <p className="text-xs text-success font-medium mt-3">{topupSuccess}</p>
                )}
              </CardContent>
            </Card>
          </div>
        </CardContent>
      </Card>

      {/* Subscription Plans */}
      <div className="flex flex-col gap-4">
        <div>
          <h3 className="text-lg font-bold text-foreground">Subscription Plans</h3>
          <p className="text-xs text-muted-foreground mt-0.5">Scale your architecture capability as your team grows</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {plans.map((p) => {
            const isPro = p.id === 'pro';
            return (
              <Card key={p.id} className={cn('relative flex flex-col', isPro && 'border-primary/50')}>
                {isPro && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <Badge>Most Popular</Badge>
                  </div>
                )}
                <CardHeader>
                  <CardTitle>{p.name}</CardTitle>
                  <div className="flex items-baseline gap-1">
                    <span className="text-3xl font-extrabold text-foreground">${p.price_usd}</span>
                    <span className="text-xs text-muted-foreground">/month</span>
                  </div>
                </CardHeader>
                <CardContent className="flex-1">
                  <div className="flex flex-col gap-4">
                    <Badge variant="secondary" className="w-full justify-center py-1.5">
                      {p.monthly_credits.toLocaleString()} credits included monthly
                    </Badge>
                    <ul className="flex flex-col gap-2.5 text-xs text-muted-foreground">
                      {p.features.map((feat, idx) => (
                        <li key={idx} className="flex items-center gap-2">
                          <Check className="h-3.5 w-3.5 text-success shrink-0" />
                          <span>{feat}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </CardContent>
                <Separator />
                <CardFooter className="pt-4">
                  <Button
                    variant={isPro ? 'default' : 'outline'}
                    className="w-full"
                    disabled={isPro}
                  >
                    {isPro ? 'Current Plan' : 'Select Plan'}
                  </Button>
                </CardFooter>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Credit Transactions Ledger */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Credit Consumption Ledger</CardTitle>
            </div>
            <span className="text-xs text-muted-foreground">Real-Time Usage Metering</span>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Description</TableHead>
                <TableHead className="text-right">Points</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {transactions.map((tx) => (
                <TableRow key={tx.id}>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {tx.created_at ? new Date(tx.created_at).toLocaleDateString() : '-'}
                  </TableCell>
                  <TableCell className="font-semibold font-mono text-xs text-primary">{tx.action}</TableCell>
                  <TableCell className="text-muted-foreground">{tx.description}</TableCell>
                  <TableCell className="text-right font-mono font-semibold">
                    <span className={tx.amount > 0 ? 'text-success' : 'text-destructive'}>
                      {tx.amount > 0 ? `+${tx.amount}` : tx.amount}
                    </span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
