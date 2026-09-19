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
    <div className="space-y-8 max-w-4xl mx-auto animate-fade-up py-4">
      {/* Header */}
      <div className="border-b border-[var(--border)] pb-4">
        <h1 className="text-2xl font-serif text-[var(--sutra-charcoal)]">Deployment Credentials</h1>
        <p className="text-[13px] text-[var(--text-2)] mt-1 font-light">Securely manage your deployment tokens for one-click MVP provisioning.</p>
      </div>

      <div className="sutra-card p-8 bg-[var(--bg-2)] flex items-start justify-between gap-6 flex-wrap relative overflow-hidden">
        <div className="space-y-4 max-w-xl relative z-10">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-[var(--sutra-charcoal)] text-[var(--sutra-warm-ivory)] text-[10px] uppercase tracking-widest font-bold">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>One-Click Deployer</span>
          </div>
          <p className="text-[13px] text-[var(--text-2)] leading-relaxed font-light">
            Save your GitHub Personal Access Token and Render API key to enable one-click deployment of generated MVP code. Credentials are encrypted at rest.
          </p>
        </div>
        <Rocket className="w-16 h-16 text-[var(--border)] absolute right-6 top-1/2 -translate-y-1/2 opacity-50 z-0" />
      </div>

      {/* Credentials Form */}
      <form
        onSubmit={handleSave}
        className="sutra-card p-8 space-y-6 bg-[var(--bg)]"
      >
        <div className="space-y-2">
          <label className="flex items-center gap-2 text-[11px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)]">
            <GitBranch className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />
            GitHub Personal Access Token (PAT)
          </label>
          <div className="relative">
            <input
              type={showTokens ? 'text' : 'password'}
              value={githubToken}
              onChange={(e) => setGithubToken(e.target.value)}
              placeholder="ghp_••••••••••••••••••••••••••"
              className="w-full px-4 py-3 pl-10 pr-12 bg-[var(--bg-2)] border border-[var(--border)] text-[var(--sutra-charcoal)] text-[13px] font-mono focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors rounded-sm shadow-sm"
              autoComplete="off"
            />
            <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-3)]" />
            <button
              type="button"
              onClick={() => setShowTokens(!showTokens)}
              className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[var(--text-3)] hover:text-[var(--sutra-charcoal)] transition-colors"
              title={showTokens ? 'Hide secrets' : 'Reveal secrets'}
            >
              {showTokens ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          <p className="text-[11px] text-[var(--text-2)] font-light mt-1">
            Scopes needed: <code className="text-[var(--sutra-charcoal)] bg-[var(--bg-2)] px-1.5 border border-[var(--border)] rounded-sm font-mono">repo</code>
          </p>
        </div>

        <div className="space-y-2">
          <label className="flex items-center gap-2 text-[11px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)]">
            <Rocket className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />
            Render API Key
          </label>
          <div className="relative">
            <input
              type={showTokens ? 'text' : 'password'}
              value={renderApiKey}
              onChange={(e) => setRenderApiKey(e.target.value)}
              placeholder="rnd_••••••••••••••••••••••"
              className="w-full px-4 py-3 pl-10 pr-12 bg-[var(--bg-2)] border border-[var(--border)] text-[var(--sutra-charcoal)] text-[13px] font-mono focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors rounded-sm shadow-sm"
              autoComplete="off"
            />
            <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-3)]" />
            <button
              type="button"
              onClick={() => setShowTokens(!showTokens)}
              className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[var(--text-3)] hover:text-[var(--sutra-charcoal)] transition-colors"
              title={showTokens ? 'Hide secrets' : 'Reveal secrets'}
            >
              {showTokens ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          <p className="text-[11px] text-[var(--text-2)] font-light mt-1">
            Optional — used to trigger an automatic Render deploy after push.
          </p>
        </div>

        {message && (
          <div
            className={`flex items-center gap-2 px-4 py-3 rounded-sm text-[12px] font-medium border shadow-sm ${status === 'saved'
                ? 'bg-[var(--bg-2)] border-[var(--green)] text-[var(--green)]'
                : 'bg-[var(--bg-2)] border-[var(--red)] text-[var(--red)]'
              }`}
          >
            {status === 'saved' && <Check className="w-4 h-4 shrink-0" />}
            {message}
          </div>
        )}

        <div className="pt-4 flex justify-end border-t border-[var(--border)]">
          <button
            type="submit"
            disabled={saving}
            className="btn btn-primary min-w-[160px] justify-center shadow-md"
          >
            {saving ? <span>Encrypting...</span> : <span>Save Credentials</span>}
          </button>
        </div>
      </form>

      {/* Guides */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Token Generation Guide */}
        <div className="sutra-card p-6 bg-[var(--bg-2)]">
          <h2 className="text-[12px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)] mb-4">How to generate tokens</h2>
          <div className="space-y-5">
            <div>
              <h3 className="text-[11px] font-bold text-[var(--sutra-charcoal)] mb-2 flex items-center gap-1.5"><GitBranch className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" /> GitHub PAT</h3>
              <ol className="space-y-2 text-[12px] text-[var(--text-2)] list-decimal list-inside font-light">
                <li>Go to <a href="https://github.com/settings/tokens/new" target="_blank" rel="noreferrer" className="text-[var(--sutra-muted-gold)] hover:underline font-medium">GitHub Developer Settings &rarr;</a></li>
                <li>Enter a descriptive note (e.g., &quot;Sutra AI Builder&quot;).</li>
                <li>Check the <code className="text-[var(--sutra-charcoal)] bg-[var(--bg)] px-1 border border-[var(--border)] rounded-sm font-mono text-[10px]">repo</code> scope to allow code pushes.</li>
                <li>Click <strong>Generate token</strong> and copy it here.</li>
              </ol>
            </div>
            <div className="border-t border-[var(--border)] pt-4">
              <h3 className="text-[11px] font-bold text-[var(--sutra-charcoal)] mb-2 flex items-center gap-1.5"><Rocket className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" /> Render API Key</h3>
              <ol className="space-y-2 text-[12px] text-[var(--text-2)] list-decimal list-inside font-light">
                <li>Go to your <a href="https://dashboard.render.com/user/settings#api-keys" target="_blank" rel="noreferrer" className="text-[var(--sutra-muted-gold)] hover:underline font-medium">Render Account Settings &rarr;</a></li>
                <li>Scroll down to the <strong>API Keys</strong> section.</li>
                <li>Click <strong>Create API Key</strong>.</li>
                <li>Copy the generated key and paste it here.</li>
              </ol>
            </div>
          </div>
        </div>

        {/* Usage hint */}
        <div className="sutra-card p-6 bg-[var(--bg-2)]">
          <h2 className="text-[12px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)] mb-4">How the deployer works</h2>
          <ol className="space-y-3 text-[13px] text-[var(--text-2)] list-decimal list-inside font-light">
            <li>Finish an MVP build for a solution (chat → blueprints → Build &amp; Deploy).</li>
            <li>On the MVP page, click <strong className="text-[var(--sutra-charcoal)] font-semibold">Deploy to GitHub</strong> and enter a repo name.</li>
            <li>The deployer pushes the project with <code className="text-[var(--sutra-charcoal)] bg-[var(--bg)] px-1.5 border border-[var(--border)] rounded-sm font-mono">render.yaml</code> and CI workflow.</li>
          </ol>
        </div>
      </div>
    </div>
  );
}