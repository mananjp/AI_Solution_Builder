'use client';

import React, { useState, useEffect } from 'react';
import { Check, Eye, EyeOff, GitBranch, Lock, Rocket, ShieldCheck, Smartphone, Server, RefreshCw } from 'lucide-react';
import { authApi, getApiBaseUrl } from '@/lib/api';

export default function SettingsPage() {
  const [githubToken, setGithubToken] = useState('');
  const [renderApiKey, setRenderApiKey] = useState('');
  const [showTokens, setShowTokens] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<'idle' | 'saved' | 'error'>('idle');
  const [message, setMessage] = useState<string | null>(null);

  // Mobile & API Backend configuration
  const [customApiUrl, setCustomApiUrl] = useState('');
  const [currentApi, setCurrentApi] = useState('');
  const [apiSaveStatus, setApiSaveStatus] = useState<string | null>(null);
  const [isMobileApp, setIsMobileApp] = useState(false);

  useEffect(() => {
    setCurrentApi(getApiBaseUrl());
    const stored = localStorage.getItem('custom_backend_url') || '';
    setCustomApiUrl(stored);

    if (typeof window !== 'undefined') {
      const isCap = (window as unknown as { Capacitor?: unknown }).Capacitor !== undefined ||
        (window.location.protocol === 'https:' && window.location.hostname === 'localhost' && window.location.port === '');
      setIsMobileApp(isCap);
    }
  }, []);

  const handleSaveApiUrl = (e: React.FormEvent) => {
    e.preventDefault();
    if (customApiUrl.trim()) {
      localStorage.setItem('custom_backend_url', customApiUrl.trim());
      setApiSaveStatus('Backend URL updated successfully.');
    } else {
      localStorage.removeItem('custom_backend_url');
      setApiSaveStatus('Reset to default backend.');
    }
    setCurrentApi(getApiBaseUrl());
    setTimeout(() => setApiSaveStatus(null), 4000);
  };

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

      {/* Mobile App & API Backend Network Configuration */}
      <div className="sutra-card p-8 space-y-6 bg-[var(--bg)] border border-[var(--border)]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-sm bg-[var(--sutra-muted-gold)]/15 text-[var(--sutra-muted-gold)] border border-[var(--sutra-muted-gold)]/30">
              <Smartphone className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-[13px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)]">
                Mobile &amp; API Server Configuration
              </h2>
              <p className="text-xs text-[var(--text-2)] font-light mt-0.5">
                Configure backend API endpoint for Capacitor Android App and local development.
              </p>
            </div>
          </div>
          <span className={`px-2.5 py-1 text-[10px] font-mono uppercase font-bold rounded-sm border ${
            isMobileApp
              ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30'
              : 'bg-[var(--bg-2)] text-[var(--text-2)] border-[var(--border)]'
          }`}>
            {isMobileApp ? 'Capacitor Android Active' : 'Web Shell Active'}
          </span>
        </div>

        <form onSubmit={handleSaveApiUrl} className="space-y-4">
          <div className="space-y-1.5">
            <label className="flex items-center gap-2 text-[11px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)]">
              <Server className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />
              Active Backend Base URL
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={customApiUrl}
                onChange={(e) => setCustomApiUrl(e.target.value)}
                placeholder={currentApi || 'https://ai-solution-builder.onrender.com/api/v1'}
                className="flex-1 px-4 py-2.5 bg-[var(--bg-2)] border border-[var(--border)] text-[var(--sutra-charcoal)] text-[12px] font-mono focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors rounded-sm shadow-sm"
              />
              <button
                type="submit"
                className="btn btn-primary px-5 text-xs whitespace-nowrap"
              >
                Apply URL
              </button>
              {customApiUrl && (
                <button
                  type="button"
                  onClick={() => {
                    setCustomApiUrl('');
                    localStorage.removeItem('custom_backend_url');
                    setCurrentApi(getApiBaseUrl());
                    setApiSaveStatus('Reset to default backend.');
                    setTimeout(() => setApiSaveStatus(null), 3000);
                  }}
                  className="btn btn-secondary px-3 text-xs"
                  title="Reset to default"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
            <p className="text-[11px] text-[var(--text-3)] font-mono">
              Current resolved endpoint: <span className="text-[var(--sutra-muted-gold)]">{currentApi}</span>
            </p>
          </div>

          {apiSaveStatus && (
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs rounded-sm animate-fade-in flex items-center gap-2">
              <Check className="w-3.5 h-3.5" />
              {apiSaveStatus}
            </div>
          )}
        </form>
      </div>

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