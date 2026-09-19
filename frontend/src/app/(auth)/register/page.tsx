'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Sparkles, Lock, Mail, Building, User, AlertCircle, Loader2 } from 'lucide-react';
import { authApi, setDemoSession } from '@/lib/api';

export default function RegisterPage() {
  const router = useRouter();
  const [orgName, setOrgName] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [oauthLoading, setOauthLoading] = useState<string | null>(null);

  const [configuredProviders, setConfiguredProviders] = useState<string[]>([]);
  const [allowAnonymous, setAllowAnonymous] = useState(true);

  useEffect(() => {
    authApi
      .getProviders()
      .then((res) => {
        setConfiguredProviders(res.providers || []);
        setAllowAnonymous(res.allow_anonymous);
      })
      .catch(() => {
        setConfiguredProviders([]);
        setAllowAnonymous(true);
      });
  }, []);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await authApi.register({
        email,
        password,
        org_name: orgName,
        full_name: fullName,
      });
      router.push('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed. Please verify your info.');
    } finally {
      setLoading(false);
    }
  };

  const handleOAuthClick = async (provider: 'github' | 'google') => {
    setError(null);
    setOauthLoading(provider);
    try {
      const res = await authApi.getOAuthAuthorizeUrl(provider);
      if (res.authorization_url) {
        window.location.href = res.authorization_url;
      } else {
        throw new Error(`Failed to get authorization redirect for ${provider}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to connect with ${provider}`);
      setOauthLoading(null);
    }
  };

  const handleDemoLogin = async () => {
    setError(null);
    setLoading(true);
    try {
      await authApi.anonymousLogin();
    } catch {
      // Backend offline — fall back to client-side demo session
      setDemoSession();
    } finally {
      setLoading(false);
      router.push('/dashboard');
    }
  };

  return (
    <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center p-6 relative overflow-hidden">
      <div className="w-full max-w-md relative z-10 animate-fade-up">
        
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center justify-center mb-6 group w-full">
            <div className="flex items-center justify-center shrink-0">
              <span className="text-[var(--sutra-muted-gold)] font-sanskrit font-bold text-5xl leading-none drop-shadow-sm">सूत्र</span>
            </div>
          </Link>
          <h2 className="text-2xl font-serif text-[var(--sutra-charcoal)]">Create your workspace</h2>
          <p className="text-[13px] text-[var(--text-2)] mt-2 font-light">Get 200 credits to generate and build MVPs</p>
        </div>

        <div className="sutra-card p-8 space-y-6 bg-[var(--bg-2)]">
          {error && (
            <div className="flex items-start gap-2 p-3 bg-[var(--bg)] border border-[var(--red)] text-[var(--red)] text-[12px] shadow-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Social OAuth options if configured */}
          {configuredProviders.length > 0 && (
            <div className="space-y-3">
              {configuredProviders.includes('github') && (
                <button
                  type="button"
                  onClick={() => handleOAuthClick('github')}
                  disabled={loading || oauthLoading !== null}
                  className="btn btn-secondary w-full justify-center py-2.5"
                >
                  {oauthLoading === 'github' ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <svg className="w-4 h-4 fill-current text-[var(--sutra-charcoal)]" viewBox="0 0 24 24">
                      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                    </svg>
                  )}
                  <span>Sign up with GitHub</span>
                </button>
              )}

              {configuredProviders.includes('google') && (
                <button
                  type="button"
                  onClick={() => handleOAuthClick('google')}
                  disabled={loading || oauthLoading !== null}
                  className="btn btn-secondary w-full justify-center py-2.5"
                >
                  {oauthLoading === 'google' ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <svg className="w-4 h-4" viewBox="0 0 24 24">
                      <path
                        fill="#4285F4"
                        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                      />
                      <path
                        fill="#34A853"
                        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                      />
                      <path
                        fill="#FBBC05"
                        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                      />
                      <path
                        fill="#EA4335"
                        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                      />
                    </svg>
                  )}
                  <span>Sign up with Google</span>
                </button>
              )}

              <div className="flex items-center gap-4 pt-2 pb-2">
                <div className="flex-1 border-t border-[var(--border)]" />
                <span className="text-[10px] uppercase tracking-widest font-bold text-[var(--text-3)]">or email</span>
                <div className="flex-1 border-t border-[var(--border)]" />
              </div>
            </div>
          )}

          <form onSubmit={handleRegister} className="space-y-4">
            <div>
              <label className="block text-[11px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)] mb-2">Organization / Company</label>
              <div className="relative">
                <Building className="w-4 h-4 text-[var(--text-3)] absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  required
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  placeholder="Acme Technologies"
                  className="w-full pl-10 pr-4 py-3 bg-[var(--bg)] border border-[var(--border)] text-[var(--sutra-charcoal)] text-[13px] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors rounded-sm shadow-sm"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)] mb-2">Your Full Name</label>
              <div className="relative">
                <User className="w-4 h-4 text-[var(--text-3)] absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Sarah Chen"
                  className="w-full pl-10 pr-4 py-3 bg-[var(--bg)] border border-[var(--border)] text-[var(--sutra-charcoal)] text-[13px] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors rounded-sm shadow-sm"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)] mb-2">Work Email</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-[var(--text-3)] absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  className="w-full pl-10 pr-4 py-3 bg-[var(--bg)] border border-[var(--border)] text-[var(--sutra-charcoal)] text-[13px] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors rounded-sm shadow-sm"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)] mb-2">Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-[var(--text-3)] absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Minimum 8 characters"
                  className="w-full pl-10 pr-4 py-3 bg-[var(--bg)] border border-[var(--border)] text-[var(--sutra-charcoal)] text-[13px] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors rounded-sm shadow-sm"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || oauthLoading !== null}
              className="btn btn-primary w-full justify-center py-3 mt-2"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <span>Create Account</span>}
            </button>
          </form>

          {allowAnonymous && (
            <div className="pt-2 border-t border-[var(--border)] mt-4">
              <div className="flex items-center gap-4 pb-4">
                <div className="flex-1 border-t border-[var(--border)]" />
                <span className="text-[10px] uppercase tracking-widest font-bold text-[var(--text-3)]">No Registration Needed</span>
                <div className="flex-1 border-t border-[var(--border)]" />
              </div>

              <button
                type="button"
                onClick={handleDemoLogin}
                disabled={loading || oauthLoading !== null}
                className="btn btn-secondary w-full justify-center py-3"
              >
                <Sparkles className="w-4 h-4" />
                <span>Try Demo As Guest (Unlimited Credits)</span>
              </button>
            </div>
          )}
        </div>

        <div className="mt-6 text-center text-[12px] text-[var(--text-2)]">
          Already have an account?{' '}
          <Link href="/login" className="text-[var(--sutra-charcoal)] hover:text-[var(--sutra-muted-gold)] transition-colors font-semibold border-b border-[var(--sutra-charcoal)] hover:border-[var(--sutra-muted-gold)] pb-0.5">
            Sign In
          </Link>
        </div>
      </div>
    </div>
  );
}
