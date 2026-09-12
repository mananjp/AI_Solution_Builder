'use client';

import React, { useState } from 'react';
import { Check, Eye, EyeOff, GitBranch, Lock, Rocket, ShieldCheck } from 'lucide-react';
import { authApi } from '@/lib/api';

export default function SettingsPage() {
  const [githubToken, setGithubToken] = useState('');
  const [renderApiKey, setRenderApiKey] = useState('');
  const [showTokens, setShowTokens] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<'idle' | 'saved' | 'error'>('idle');
  const [message, setMessage] = useState<string | null>(null);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload: { github_token?: string; render_api_key?: string } = {};
    if (githubToken.trim()) payload.github_token = githubToken.trim();
    if (renderApiKey.trim()) payload.render_api_key = renderApiKey.trim();

    if (Object.keys(payload).length === 0) {
      setStatus('error');
      setMessage('Enter at least one credential to save.');
      return;
    }

    setSaving(true);
    setStatus('idle');
    setMessage(null);
    try {
      await authApi.updateSettings(payload);
      setStatus('saved');
      setMessage('Deployment credentials saved securely. Tokens stay server-side and are never returned to the client.');
      setGithubToken('');
      setRenderApiKey('');
    } catch (err) {
      setStatus('error');
      setMessage(err instanceof Error ? err.message : 'Failed to save deployment credentials.');
    } finally {
      setSaving(false);
      setTimeout(() => {
        setStatus('idle');
        setMessage(null);
      }, 5000);
    }
  };

  const inputClass =
    'w-full px-4 py-3 rounded-xl bg-slate-900 border border-white/10 text-white text-xs placeholder:text-slate-500 focus:outline-none focus:border-indigo-500 transition-colors shadow-inner font-mono';

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      {/* Header */}
      <div className="p-8 rounded-3xl bg-gradient-to-r from-indigo-950/60 via-slate-900/80 to-purple-950/40 border border-white/5 shadow-2xl relative overflow-hidden">
        <div className="relative z-10 flex items-start justify-between gap-6 flex-wrap">
          <div className="space-y-2 max-w-xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-semibold">
              <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
              <span>One-Click Deployer</span>
            </div>
            <h2 className="text-2xl font-extrabold text-white tracking-tight">Deployment Credentials</h2>
            <p className="text-xs text-slate-300 leading-relaxed">
              Save your GitHub Personal Access Token and Render API key to enable one-click deployment of generated MVP
              code. Credentials are stored per-account, encrypted at rest, and never exposed through the API.
            </p>
          </div>
          <Rocket className="w-12 h-12 text-indigo-400/60" />
        </div>
      </div>

      {/* Credentials Form */}
      <form
        onSubmit={handleSave}
        className="p-6 rounded-2xl bg-slate-900/40 border border-white/5 space-y-5"
      >
        <div className="space-y-1.5">
          <label className="flex items-center gap-2 text-xs font-semibold text-slate-200">
            <GitBranch className="w-3.5 h-3.5 text-slate-400" />
            GitHub Personal Access Token (PAT)
          </label>
          <div className="relative">
            <input
              type={showTokens ? 'text' : 'password'}
              value={githubToken}
              onChange={(e) => setGithubToken(e.target.value)}
              placeholder="ghp_••••••••••••••••••••••••••"
              className={`${inputClass} pr-11`}
              autoComplete="off"
            />
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-600" />
            <button
              type="button"
              onClick={() => setShowTokens(!showTokens)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
              title={showTokens ? 'Hide secrets' : 'Reveal secrets'}
            >
              {showTokens ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          <p className="text-[11px] text-slate-500">
            Scopes needed: <code className="text-indigo-300">repo</code> to create the fresh repository and push files
            during deploy.
          </p>
        </div>

        <div className="space-y-1.5">
          <label className="flex items-center gap-2 text-xs font-semibold text-slate-200">
            <Rocket className="w-3.5 h-3.5 text-slate-400" />
            Render API Key
          </label>
          <div className="relative">
            <input
              type={showTokens ? 'text' : 'password'}
              value={renderApiKey}
              onChange={(e) => setRenderApiKey(e.target.value)}
              placeholder="rnd_••••••••••••••••••••••"
              className={`${inputClass} pr-11`}
              autoComplete="off"
            />
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-600" />
            <button
              type="button"
              onClick={() => setShowTokens(!showTokens)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
              title={showTokens ? 'Hide secrets' : 'Reveal secrets'}
            >
              {showTokens ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          <p className="text-[11px] text-slate-500">
            Optional — used to trigger an automatic Render deploy after the GitHub push.
          </p>
        </div>

        {message && (
          <div
            className={`flex items-center gap-2 px-4 py-3 rounded-xl text-xs font-medium border ${
              status === 'saved'
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
            }`}
          >
            {status === 'saved' && <Check className="w-3.5 h-3.5 flex-shrink-0" />}
            {message}
          </div>
        )}

        <div className="pt-2 flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white text-xs font-semibold shadow-xl shadow-indigo-600/30 transition-all hover:scale-105 disabled:opacity-40"
          >
            {saving ? <span>saving…</span> : <span>Save Credentials</span>}
          </button>
        </div>
      </form>

      {/* Usage hint */}
      <div className="p-5 rounded-2xl bg-slate-900/40 border border-white/5">
        <h3 className="text-xs font-bold text-white mb-2">How the deployer uses these</h3>
        <ol className="space-y-2 text-xs text-slate-400 list-decimal list-inside">
          <li>Finish an MVP build for a solution(chat → blueprints → <span className="text-indigo-300">Build &amp; Deploy</span>).</li>
          <li>
            On the MVP page, pick <span className="text-indigo-300">Deploy to GitHub</span> and enter a repository name.
          </li>
          <li>
            The deployer creates a fresh private repository with your PAT and pushes the full generated project — including a
            Render blueprint (<code className="text-indigo-300">render.yaml</code>) and CI workflow.
          </li>
          <li>Connect the repository to Render and it auto-deploys on green CI.</li>
        </ol>
      </div>
    </div>
  );
}