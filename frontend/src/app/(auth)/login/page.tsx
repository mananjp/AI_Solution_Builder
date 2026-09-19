'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Sparkles, Lock, Mail, AlertCircle, Loader2 } from 'lucide-react';
import { authApi, setDemoSession } from '@/lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [oauthLoading, setOauthLoading] = useState<string | null>(null);
  const [configuredProviders, setConfiguredProviders] = useState<string[]>([]);

  useEffect(() => {
    authApi.getProviders()
      .then((res) => setConfiguredProviders(res.providers || []))
      .catch(() => setConfiguredProviders([]));
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (email === 'demo@demo.com' && password === 'demo') {
        setDemoSession();
        router.push('/dashboard');
        return;
      }
      await authApi.login({ email, password });
      router.push('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid email or password.');
    } finally {
      setLoading(false);
    }
  };

  const handleOAuthClick = async (provider: 'github' | 'google') => {
    setError(null);
    setOauthLoading(provider);
    try {
      const res = await authApi.getOAuthAuthorizeUrl(provider);
      if (res.authorization_url) window.location.href = res.authorization_url;
      else throw new Error(`No redirect URL returned`);
    } catch (err) {
      setError(err instanceof Error ? err.message : `OAuth failed`);
      setOauthLoading(null);
    }
  };

  const handleDemoLogin = async () => {
    setError(null);
    setLoading(true);
    try {
      await authApi.anonymousLogin();
    } catch {
      setDemoSession(); // offline fallback
    } finally {
      setLoading(false);
      router.push('/dashboard');
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center p-4">
      <div className="w-full max-w-[380px] animate-fade-up">

        {/* Brand mark */}
        <div className="mb-8 text-center">
          <Link href="/" className="inline-flex items-center gap-2 mb-5 group">
            <div className="w-8 h-8 rounded-lg bg-[#6366f1] flex items-center justify-center text-white">
              <Sparkles className="w-4 h-4" />
            </div>
            <span className="font-semibold text-white text-sm tracking-tight">AI Solution Builder</span>
          </Link>
          <h1 className="text-xl font-semibold text-white">Sign in</h1>
          <p className="text-sm text-[#666] mt-1">to your architecture workspace</p>
        </div>

        {/* Card */}
        <div className="bg-[#111] border border-[#242424] rounded-xl p-6 space-y-4">

          {/* Error */}
          {error && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-[#ef444412] border border-[#ef444430] text-[#f87171] text-xs">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* One-click demo — top, prominent */}
          <button
            type="button"
            id="demo-login-btn"
            onClick={handleDemoLogin}
            disabled={loading || oauthLoading !== null}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-[#6366f1] hover:bg-[#5558dd] text-white text-sm font-medium transition-colors disabled:opacity-50"
          >
            {loading && !oauthLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            Continue as Guest
          </button>

          <p className="text-center text-[11px] text-[#555]">No account needed. Full demo access.</p>

          {/* Divider */}
          <div className="flex items-center gap-3">
            <div className="flex-1 border-t border-[#242424]" />
            <span className="text-[11px] text-[#555]">or</span>
            <div className="flex-1 border-t border-[#242424]" />
          </div>

          {/* OAuth */}
          {configuredProviders.length > 0 && (
            <div className="space-y-2">
              {configuredProviders.includes('github') && (
                <button
                  type="button"
                  onClick={() => handleOAuthClick('github')}
                  disabled={loading || oauthLoading !== null}
                  className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-[#161616] hover:bg-[#1c1c1c] border border-[#2e2e2e] text-white text-sm font-medium transition-colors disabled:opacity-50"
                >
                  {oauthLoading === 'github' ? <Loader2 className="w-4 h-4 animate-spin" /> : (
                    <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
                      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                    </svg>
                  )}
                  Continue with GitHub
                </button>
              )}
              {configuredProviders.includes('google') && (
                <button
                  type="button"
                  onClick={() => handleOAuthClick('google')}
                  disabled={loading || oauthLoading !== null}
                  className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-[#161616] hover:bg-[#1c1c1c] border border-[#2e2e2e] text-white text-sm font-medium transition-colors disabled:opacity-50"
                >
                  {oauthLoading === 'google' ? <Loader2 className="w-4 h-4 animate-spin" /> : (
                    <svg className="w-4 h-4" viewBox="0 0 24 24">
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
                    </svg>
                  )}
                  Continue with Google
                </button>
              )}
              <div className="flex items-center gap-3">
                <div className="flex-1 border-t border-[#242424]" />
                <span className="text-[11px] text-[#555]">or email</span>
                <div className="flex-1 border-t border-[#242424]" />
              </div>
            </div>
          )}

          {/* Email form */}
          <form onSubmit={handleLogin} className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-[#a1a1a1] mb-1.5">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#555]" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  className="w-full pl-9 pr-3 py-2.5 rounded-lg bg-[#0a0a0a] border border-[#2e2e2e] text-white text-sm placeholder:text-[#444] focus:outline-none focus:border-[#6366f1] transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-[#a1a1a1] mb-1.5">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#555]" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-9 pr-3 py-2.5 rounded-lg bg-[#0a0a0a] border border-[#2e2e2e] text-white text-sm placeholder:text-[#444] focus:outline-none focus:border-[#6366f1] transition-colors"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || oauthLoading !== null}
              className="w-full py-2.5 rounded-lg bg-[#161616] hover:bg-[#1c1c1c] border border-[#2e2e2e] text-white text-sm font-medium flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
            >
              {loading && !oauthLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Sign in with email'}
            </button>
          </form>

          <p className="text-[11px] text-[#444] text-center">
            Demo: <span className="text-[#666] font-mono">demo@demo.com</span> / <span className="text-[#666] font-mono">demo</span>
          </p>
        </div>

        <p className="mt-4 text-center text-xs text-[#555]">
          No account?{' '}
          <Link href="/register" className="text-[#a1a1a1] hover:text-white transition-colors">
            Create one
          </Link>
        </p>
      </div>
    </div>
  );
}
