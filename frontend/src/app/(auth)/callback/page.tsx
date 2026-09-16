'use client';

import React, { Suspense, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2, AlertCircle } from 'lucide-react';
import { setAuthToken } from '@/lib/api';

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');
  const err = searchParams.get('error');

  useEffect(() => {
    if (token) {
      setAuthToken(token);
      router.replace('/dashboard');
    }
  }, [token, router]);

  const error = err ?? (!token ? 'No authentication token received from OAuth provider.' : null);

  if (error) {
    return (
      <div className="p-8 rounded-2xl bg-slate-900/80 border border-rose-500/20 text-center max-w-sm">
        <AlertCircle className="w-8 h-8 text-rose-400 mx-auto mb-3" />
        <h2 className="text-base font-bold text-white mb-1">Authentication Failed</h2>
        <p className="text-xs text-slate-400 mb-4">{error}</p>
        <button
          onClick={() => router.push('/login')}
          className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-xs font-semibold text-white transition-colors"
        >
          Return to Sign In
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-3">
      <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
      <p className="text-xs text-slate-300 font-medium">Securing session and entering workspace...</p>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <div className="min-h-screen bg-[#070a13] flex items-center justify-center p-6">
      <Suspense
        fallback={
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
            <p className="text-xs text-slate-300 font-medium">Authorizing...</p>
          </div>
        }
      >
        <CallbackContent />
      </Suspense>
    </div>
  );
}
