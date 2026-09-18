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

  return (
    <div className="space-y-6 max-w-4xl mx-auto animate-fade-up">
      {/* Header */}
      <div className="p-6 rounded-xl bg-[#111] border border-[#1a1a1a] flex items-start justify-between gap-4 flex-wrap">
        <div className="space-y-1.5 max-w-xl">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#161616] border border-[#242424] text-[#818cf8] text-xs font-medium">
            <ShieldCheck className="w-3.5 h-3.5 text-[#6366f1]" />
            <span>One-Click Deployer</span>
          </div>
          <h1 className="text-xl font-semibold text-white">Deployment Credentials</h1>
          <p className="text-xs text-[#555] leading-relaxed">
            Save your GitHub Personal Access Token and Render API key to enable one-click deployment of generated MVP
            code. Credentials are encrypted at rest.
          </p>
        </div>
        <Rocket className="w-8 h-8 text-[#6366f1] opacity-80" />
      </div>

      {/* Credentials Form */}
      <form
        onSubmit={handleSave}
        className="p-5 rounded-xl bg-[#111] border border-[#1a1a1a] space-y-4"
      >
        <div className="space-y-1.5">
          <label className="flex items-center gap-2 text-xs font-medium text-[#a1a1a1]">
            <GitBranch className="w-3.5 h-3.5 text-[#666]" />
            GitHub Personal Access Token (PAT)
          </label>
          <div className="relative">
            <input
              type={showTokens ? 'text' : 'password'}
              value={githubToken}
              onChange={(e) => setGithubToken(e.target.value)}
              placeholder="ghp_••••••••••••••••••••••••••"
              className="w-full px-3 py-2 pl-8 pr-10 rounded-lg bg-[#0a0a0a] border border-[#2e2e2e] text-white text-xs font-mono focus:outline-none focus:border-[#6366f1] transition-colors"
              autoComplete="off"
            />
            <Lock className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#555]" />
            <button
              type="button"
              onClick={() => setShowTokens(!showTokens)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[#555] hover:text-white transition-colors"
              title={showTokens ? 'Hide secrets' : 'Reveal secrets'}
            >
              {showTokens ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          <p className="text-[11px] text-[#555]">
            Scopes needed: <code className="text-[#818cf8] font-mono">repo</code>
          </p>
        </div>

        <div className="space-y-1.5">
          <label className="flex items-center gap-2 text-xs font-medium text-[#a1a1a1]">
            <Rocket className="w-3.5 h-3.5 text-[#666]" />
            Render API Key
          </label>
          <div className="relative">
            <input
              type={showTokens ? 'text' : 'password'}
              value={renderApiKey}
              onChange={(e) => setRenderApiKey(e.target.value)}
              placeholder="rnd_••••••••••••••••••••••"
              className="w-full px-3 py-2 pl-8 pr-10 rounded-lg bg-[#0a0a0a] border border-[#2e2e2e] text-white text-xs font-mono focus:outline-none focus:border-[#6366f1] transition-colors"
              autoComplete="off"
            />
            <Lock className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#555]" />
            <button
              type="button"
              onClick={() => setShowTokens(!showTokens)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[#555] hover:text-white transition-colors"
              title={showTokens ? 'Hide secrets' : 'Reveal secrets'}
            >
              {showTokens ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          <p className="text-[11px] text-[#555]">
            Optional — used to trigger an automatic Render deploy after push.
          </p>
        </div>

        {message && (
          <div
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium ${status === 'saved'
                ? 'bg-[#22c55e10] border border-[#22c55e20] text-[#4ade80]'
                : 'bg-[#ef444410] border border-[#ef444420] text-[#f87171]'
              }`}
          >
            {status === 'saved' && <Check className="w-3.5 h-3.5 shrink-0" />}
            {message}
          </div>
        )}

        <div className="pt-2 flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#6366f1] hover:bg-[#5558dd] text-white text-xs font-medium transition-colors disabled:opacity-40"
          >
            {saving ? <span>Saving…</span> : <span>Save Credentials</span>}
          </button>
        </div>
      </form>

      {/* Usage hint */}
      <div className="p-5 rounded-xl bg-[#111] border border-[#1a1a1a]">
        <h2 className="text-xs font-semibold text-white mb-2">How the deployer works</h2>
        <ol className="space-y-1.5 text-xs text-[#a1a1a1] list-decimal list-inside">
          <li>Finish an MVP build for a solution (chat → blueprints → Build &amp; Deploy).</li>
          <li>On the MVP page, click <strong className="text-white">Deploy to GitHub</strong> and enter a repo name.</li>
          <li>The deployer pushes the project with <code className="text-[#818cf8] font-mono">render.yaml</code> and CI workflow.</li>
        </ol>
      </div>
    </div>
  );
}