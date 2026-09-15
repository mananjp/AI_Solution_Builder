'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowRight } from '@phosphor-icons/react/dist/ssr/ArrowRight';
import { authApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export default function RegisterPage() {
  const router = useRouter();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    full_name: '',
    org_name: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);
    try {
      await authApi.register({
        email: formData.email,
        password: formData.password,
        full_name: formData.full_name,
        org_name: formData.org_name,
      });
      router.push('/dashboard');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Registration failed');
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
            Architect your system.
            <br />
            <span className="text-muted-foreground">Deploy it the same day.</span>
          </h1>
          <p className="mt-6 text-[14px] text-muted-foreground max-w-sm leading-relaxed">
            Define domain boundaries, describe modules, and let the engine
            generate production schemas, APIs, and deployable code.
          </p>
        </div>

        <div className="flex flex-col gap-2 text-[11px] text-muted-foreground font-mono">
          <p>Setup time: ~5 minutes</p>
          <p>Credits: 10,000 on signup</p>
          <p>Agents: 6 specialized LLM workers</p>
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

          <h2 className="text-[20px] font-bold tracking-tight mb-1">Create your workspace</h2>
          <p className="text-[12px] text-muted-foreground mb-8">
            Set up an organization and get started immediately.
          </p>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] text-muted-foreground font-mono uppercase tracking-wider">
                Full name
              </label>
              <Input
                type="text"
                value={formData.full_name}
                onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                required
                placeholder="Jane Doe"
                className="bg-secondary border-border text-sm placeholder:text-muted-foreground/60 focus-visible:ring-primary/30"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] text-muted-foreground font-mono uppercase tracking-wider">
                Email
              </label>
              <Input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                required
                placeholder="architect@enterprise.io"
                className="bg-secondary border-border text-sm placeholder:text-muted-foreground/60 focus-visible:ring-primary/30"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] text-muted-foreground font-mono uppercase tracking-wider">
                Organization
              </label>
              <Input
                type="text"
                value={formData.org_name}
                onChange={(e) => setFormData({ ...formData, org_name: e.target.value })}
                placeholder="Acme Corp"
                className="bg-secondary border-border text-sm placeholder:text-muted-foreground/60 focus-visible:ring-primary/30"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] text-muted-foreground font-mono uppercase tracking-wider">
                Password
              </label>
              <Input
                type="password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                required
                placeholder="Min. 8 characters"
                className="bg-secondary border-border text-sm placeholder:text-muted-foreground/60 focus-visible:ring-primary/30"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] text-muted-foreground font-mono uppercase tracking-wider">
                Confirm password
              </label>
              <Input
                type="password"
                value={formData.confirmPassword}
                onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                required
                placeholder="Re-enter password"
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
              {loading ? 'Creating...' : 'Create account'}
              {!loading && <ArrowRight className="w-3.5 h-3.5 ml-1.5" />}
            </Button>
          </form>

          <p className="mt-6 text-center text-[12px] text-muted-foreground">
            Already have an account?{' '}
            <Link href="/login" className="text-primary hover:text-primary/80 transition-colors font-medium">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
