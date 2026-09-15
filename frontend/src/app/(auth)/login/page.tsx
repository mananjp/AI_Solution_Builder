'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowRight } from '@phosphor-icons/react/dist/ssr/ArrowRight';
import { authApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await authApi.login({ email, password });
      router.push('/dashboard');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

  const handleSampleLogin = async () => {
    setError('');
    setLoading(true);
    try {
      // quick reachability check to surface network errors clearly
      const apiRoot = (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1').replace('/api/v1', '');
      const res = await fetch(`${apiRoot}/`, { method: 'GET' });
      if (!res.ok) {
        throw new Error(`Backend responded with status ${res.status}`);
      }
      await authApi.login({
        email: 'demo@aibuilder.example',
        password: 'DemoPass123!',
      });
      router.push('/dashboard');
    } catch (err: any) {
      const msg = err?.message || err?.response?.data?.detail || 'Sample user login failed';
      setError(`Unable to reach backend: ${msg}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex grain">
      {/* Left: brand */}
      <div className="hidden lg:flex lg:w-[55%] relative flex-col justify-between p-10 border-r border-border">
        <div>
          <Link href="/" className="inline-flex items-center gap-2 mb-20">
            <span className="font-semibold text-[15px] tracking-tight">
              AI Solution<span className="text-primary ml-1 font-mono text-[10px] tracking-[0.15em] uppercase">Builder</span>
            </span>
          </Link>

          <h1 className="text-[clamp(2rem,4vw,3.5rem)] font-bold tracking-tight leading-[0.95]">
            From a rough prompt
            <br />
            to running software.
          </h1>
          <p className="mt-6 text-[14px] text-muted-foreground max-w-sm leading-relaxed">
            Six autonomous agents. Production schemas, APIs, wireframes, and
            deployable code. Not mockups.
          </p>
        </div>

        <div className="flex items-center gap-5 text-[11px] text-muted-foreground font-mono">
          <span>backend / fastapi</span>
          <span className="text-primary">|</span>
          <span>agents / langgraph</span>
          <span className="text-primary">|</span>
          <span>frontend / next.js</span>
        </div>
      </div>

      {/* Right: form */}
      <div className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="lg:hidden mb-10">
            <Link href="/" className="font-semibold text-[15px] tracking-tight">
              AI Solution<span className="text-primary ml-1 font-mono text-[10px] tracking-[0.15em] uppercase">Builder</span>
            </Link>
          </div>

          <h2 className="text-[20px] font-bold tracking-tight mb-1">Welcome back</h2>
          <p className="text-[12px] text-muted-foreground mb-8">
            Sign in to your workspace
          </p>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] text-muted-foreground font-mono uppercase tracking-wider">
                Email
              </label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="architect@enterprise.io"
                className="bg-secondary border-border text-sm placeholder:text-muted-foreground/60 focus-visible:ring-primary/30"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] text-muted-foreground font-mono uppercase tracking-wider">
                Password
              </label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="Enter password"
                className="bg-secondary border-border text-sm placeholder:text-muted-foreground/60 focus-visible:ring-primary/30"
              />
            </div>

            {error && (
              <p className="text-[12px] text-destructive">{error}</p>
            )}

            <Button
              type="submit"
              disabled={loading}
              className="w-full bg-primary text-primary-foreground hover:bg-primary/90 font-semibold text-[13px]"
              size="default"
            >
              {loading ? 'Signing in...' : 'Sign in'}
              {!loading && <ArrowRight className="w-3.5 h-3.5 ml-1.5" />}
            </Button>

            <Button
              type="button"
              variant="outline"
              onClick={handleSampleLogin}
              disabled={loading}
              className="w-full border-border bg-secondary/50 hover:bg-secondary text-sm"
            >
              Use sample user
            </Button>
          </form>

          <p className="mt-6 text-center text-[12px] text-muted-foreground">
            No account?{' '}
            <Link href="/register" className="text-primary hover:text-primary/80 transition-colors font-medium">
              Create one
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
