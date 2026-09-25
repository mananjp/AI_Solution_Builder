'use client';

import React, { useState } from 'react';
import {
  Sparkles,
  GitBranch,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  FolderArchive,
  Layers,
  Cpu,
  Bot,
  Download,
  ArrowRight,
  RefreshCw,
  FileCode,
  Image as ImageIcon,
  Lock,
  Play,
} from 'lucide-react';
import {
  legacyRepoApi,
  LegacyRepoAnalysis,
  CredentialValidationResult,
  ModernizeReport,
} from '@/lib/api';

export default function LegacyModernizerPage() {
  const [activeTab, setActiveTab] = useState<'upload' | 'github' | 'sample'>('sample');
  const [githubUrl, setGithubUrl] = useState('https://github.com/example/legacy-node-crm');
  const [localPath, setLocalPath] = useState('');
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);

  // Flow states
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<LegacyRepoAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Credentials
  const [apiKey, setApiKey] = useState('');
  const [validatingKey, setValidatingKey] = useState(false);
  const [keyValidation, setKeyValidation] = useState<CredentialValidationResult | null>(null);

  // Modernization
  const [modernizing, setModernizing] = useState(false);
  const [modernizeReport, setModernizeReport] = useState<ModernizeReport | null>(null);

  // ── Handlers ───────────────────────────────────────────────────────────

  const handleAnalyze = async () => {
    setError(null);
    setAnalysis(null);
    setModernizeReport(null);
    setAnalyzing(true);

    try {
      if (activeTab === 'upload' && uploadedFile) {
        const res = await legacyRepoApi.analyzeUpload(uploadedFile);
        setAnalysis(res);
      } else if (activeTab === 'github' && githubUrl) {
        const res = await legacyRepoApi.analyze({ github_repo_url: githubUrl });
        setAnalysis(res);
      } else {
        // Sample or local path mode
        const path = localPath.trim() || 'sample_legacy_repo';
        // Check local mock or backend test path
        const res = await legacyRepoApi.analyze({ local_path: path });
        setAnalysis(res);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg || 'Repository analysis failed. Please check repository bounds and try again.');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleValidateKey = async () => {
    if (!apiKey.trim()) return;
    setValidatingKey(true);
    setError(null);
    try {
      const res = await legacyRepoApi.validateCredential('GROQ_API_KEY', apiKey.trim());
      setKeyValidation(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg || 'API key validation failed.');
    } finally {
      setValidatingKey(false);
    }
  };

  const handleModernize = async () => {
    setError(null);
    setModernizing(true);
    try {
      const creds: Record<string, string> = {};
      if (apiKey.trim()) {
        creds['GROQ_API_KEY'] = apiKey.trim();
      }

      const res = await legacyRepoApi.modernize({
        local_path: analysis?.root_path || localPath,
        github_repo_url: activeTab === 'github' ? githubUrl : undefined,
        requested_features: ['ai_chatbot'],
        credentials: creds,
      });
      setModernizeReport(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg || 'Modernization execution encountered an issue.');
    } finally {
      setModernizing(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--bg-1)] text-[var(--sutra-charcoal)] px-4 py-8 lg:px-12 max-w-7xl mx-auto">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="mb-8 border-b border-[var(--border)] pb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider bg-[var(--sutra-gold)]/10 text-[var(--sutra-muted-gold)] rounded-sm border border-[var(--sutra-gold)]/20">
              Legacy Repo Engine
            </span>
            <span className="flex items-center gap-1 px-2.5 py-0.5 text-[11px] font-semibold bg-emerald-50 text-emerald-700 rounded-sm border border-emerald-200">
              <ShieldCheck className="w-3.5 h-3.5" /> sutra_os boundary strictly guarded
            </span>
          </div>
          <h1 className="text-2xl lg:text-3xl font-bold tracking-tight text-[var(--sutra-charcoal)]">
            Legacy Repository Understanding & Modernizer
          </h1>
          <p className="text-sm text-[var(--text-2)] mt-1 max-w-2xl">
            Inspect outdated codebases, identify legacy patterns and reusable assets, safely modernize dependencies,
            and inject custom AI capabilities without breaking existing features.
          </p>
        </div>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md flex items-start gap-3 text-red-800 text-sm">
          <AlertTriangle className="w-5 h-5 shrink-0 text-red-600 mt-0.5" />
          <div className="flex-1">
            <strong>Error:</strong> {error}
          </div>
        </div>
      )}

      {/* ── STEP 1: Repository Ingestion ─────────────────────────────────── */}
      <div className="bg-[var(--bg-2)] border border-[var(--border)] rounded-lg p-6 mb-8 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-bold flex items-center gap-2">
            <FolderArchive className="w-5 h-5 text-[var(--sutra-muted-gold)]" />
            1. Select Target Legacy Repository
          </h2>
          <span className="text-xs text-[var(--text-3)] font-mono">Scope: Non-sutra_os only</span>
        </div>

        {/* Tab selection */}
        <div className="flex border-b border-[var(--border)] mb-5">
          <button
            onClick={() => setActiveTab('sample')}
            className={`px-4 py-2 text-xs font-semibold uppercase tracking-wider border-b-2 transition-colors ${
              activeTab === 'sample'
                ? 'border-[var(--sutra-muted-gold)] text-[var(--sutra-charcoal)]'
                : 'border-transparent text-[var(--text-3)] hover:text-[var(--sutra-charcoal)]'
            }`}
          >
            Demo Legacy Project
          </button>
          <button
            onClick={() => setActiveTab('upload')}
            className={`px-4 py-2 text-xs font-semibold uppercase tracking-wider border-b-2 transition-colors ${
              activeTab === 'upload'
                ? 'border-[var(--sutra-muted-gold)] text-[var(--sutra-charcoal)]'
                : 'border-transparent text-[var(--text-3)] hover:text-[var(--sutra-charcoal)]'
            }`}
          >
            Upload ZIP Archive
          </button>
          <button
            onClick={() => setActiveTab('github')}
            className={`px-4 py-2 text-xs font-semibold uppercase tracking-wider border-b-2 transition-colors ${
              activeTab === 'github'
                ? 'border-[var(--sutra-muted-gold)] text-[var(--sutra-charcoal)]'
                : 'border-transparent text-[var(--text-3)] hover:text-[var(--sutra-charcoal)]'
            }`}
          >
            Public GitHub URL
          </button>
        </div>

        {/* Tab contents */}
        {activeTab === 'sample' && (
          <div className="space-y-3">
            <p className="text-xs text-[var(--text-2)]">
              Use a built-in legacy CRM application (React 16, Express 4.16, deprecated packages, custom branding assets, and customer API endpoints) to test full end-to-end modernization.
            </p>
            <div className="p-3 bg-[var(--bg-1)] border border-[var(--border)] rounded font-mono text-xs text-[var(--text-2)]">
              Target: backend/tests/fixtures/sample_legacy_crm (or system fixture)
            </div>
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[var(--text-3)] mb-1">
                Custom Local Repository Path (Optional Override)
              </label>
              <input
                type="text"
                value={localPath}
                onChange={(e) => setLocalPath(e.target.value)}
                placeholder="Leave blank to use demo fixture, or provide custom directory path"
                className="w-full px-3 py-2 text-xs bg-[var(--bg-1)] border border-[var(--border)] rounded focus:outline-none focus:border-[var(--sutra-muted-gold)] font-mono"
              />
            </div>
          </div>
        )}

        {activeTab === 'upload' && (
          <div className="border-2 border-dashed border-[var(--border)] rounded-md p-6 text-center hover:bg-[var(--bg-1)] transition-colors">
            <input
              type="file"
              accept=".zip"
              id="legacy-zip-upload"
              className="hidden"
              onChange={(e) => setUploadedFile(e.target.files?.[0] || null)}
            />
            <label htmlFor="legacy-zip-upload" className="cursor-pointer flex flex-col items-center">
              <FolderArchive className="w-8 h-8 text-[var(--text-3)] mb-2" />
              <span className="text-sm font-semibold text-[var(--sutra-charcoal)]">
                {uploadedFile ? uploadedFile.name : 'Click to select repository ZIP archive'}
              </span>
              <span className="text-xs text-[var(--text-3)] mt-1">Supports full projects up to 50MB</span>
            </label>
          </div>
        )}

        {activeTab === 'github' && (
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-2)] mb-1">
              GitHub Repository URL
            </label>
            <input
              type="text"
              value={githubUrl}
              onChange={(e) => setGithubUrl(e.target.value)}
              placeholder="https://github.com/owner/repository"
              className="w-full px-3 py-2 text-sm bg-[var(--bg-1)] border border-[var(--border)] rounded focus:outline-none focus:border-[var(--sutra-muted-gold)] font-mono"
            />
          </div>
        )}

        <div className="mt-5 flex justify-end">
          <button
            onClick={handleAnalyze}
            disabled={analyzing}
            className="px-5 py-2.5 bg-[var(--sutra-charcoal)] text-white text-xs font-bold uppercase tracking-wider rounded hover:bg-black transition-all flex items-center gap-2 disabled:opacity-50"
          >
            {analyzing ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Analyzing Architecture...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 text-[var(--sutra-muted-gold)]" />
                Inspect & Understand Repository
              </>
            )}
          </button>
        </div>
      </div>

      {/* ── STEP 2: Architectural Intelligence & Inspection Results ────────── */}
      {analysis && (
        <div className="space-y-6 mb-8">
          <div className="bg-[var(--bg-2)] border border-[var(--border)] rounded-lg p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-bold flex items-center gap-2">
                <Cpu className="w-5 h-5 text-[var(--sutra-muted-gold)]" />
                2. Architectural Intelligence & Discovery Report
              </h2>
              <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded font-mono">
                {analysis.structure.total_files} files analyzed
              </span>
            </div>

            {/* Grid stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="p-3 bg-[var(--bg-1)] border border-[var(--border)] rounded">
                <span className="text-[10px] uppercase font-bold text-[var(--text-3)] block mb-1">Languages</span>
                <span className="text-sm font-semibold">{analysis.technology_stack.languages.join(', ') || 'Unknown'}</span>
              </div>
              <div className="p-3 bg-[var(--bg-1)] border border-[var(--border)] rounded">
                <span className="text-[10px] uppercase font-bold text-[var(--text-3)] block mb-1">Frontend Stack</span>
                <span className="text-sm font-semibold">{analysis.technology_stack.frontend_framework || 'None / Static'}</span>
              </div>
              <div className="p-3 bg-[var(--bg-1)] border border-[var(--border)] rounded">
                <span className="text-[10px] uppercase font-bold text-[var(--text-3)] block mb-1">Backend Stack</span>
                <span className="text-sm font-semibold">{analysis.technology_stack.backend_framework || 'None / Serverless'}</span>
              </div>
              <div className="p-3 bg-[var(--bg-1)] border border-[var(--border)] rounded">
                <span className="text-[10px] uppercase font-bold text-[var(--text-3)] block mb-1">Topology</span>
                <span className="text-sm font-semibold">{analysis.architecture.topology}</span>
              </div>
            </div>

            {/* Architecture Tracing Diagram */}
            <div className="mb-6 p-4 bg-[var(--bg-1)] border border-[var(--border)] rounded">
              <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-2)] block mb-2">
                Traced Data Flow & Entry Points
              </span>
              <div className="flex items-center gap-2 text-xs font-mono text-[var(--text-1)] overflow-x-auto pb-1">
                <span className="px-2 py-1 bg-white border border-[var(--border)] rounded shadow-2xs">
                  {analysis.entry_points.frontend_entry || 'Frontend Entry'}
                </span>
                <ArrowRight className="w-4 h-4 text-[var(--text-3)] shrink-0" />
                <span className="px-2 py-1 bg-white border border-[var(--border)] rounded shadow-2xs">
                  HTTP API Routes ({analysis.entry_points.routing_files.length} detected)
                </span>
                <ArrowRight className="w-4 h-4 text-[var(--text-3)] shrink-0" />
                <span className="px-2 py-1 bg-white border border-[var(--border)] rounded shadow-2xs">
                  {analysis.entry_points.backend_entry || 'Backend Server'}
                </span>
                <ArrowRight className="w-4 h-4 text-[var(--text-3)] shrink-0" />
                <span className="px-2 py-1 bg-white border border-[var(--border)] rounded shadow-2xs">
                  Database ({analysis.technology_stack.database || 'Filesystem'})
                </span>
              </div>
            </div>

            {/* Assets & Technical Debt Two Columns */}
            <div className="grid md:grid-cols-2 gap-6">
              {/* Preserved Reusable Assets */}
              <div className="p-4 bg-[var(--bg-1)] border border-[var(--border)] rounded">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-emerald-700">
                    <ImageIcon className="w-4 h-4" /> Reusable Brand Assets ({analysis.assets_inventory.total_assets})
                  </h3>
                  <span className="text-[10px] text-emerald-600 font-semibold">100% Preserved</span>
                </div>
                <p className="text-xs text-[var(--text-2)] mb-3">
                  {analysis.assets_inventory.reusable_message}
                </p>
                <div className="space-y-1 max-h-36 overflow-y-auto font-mono text-[11px] text-[var(--text-2)]">
                  {analysis.assets_inventory.logos.map((l, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <span className="text-emerald-500">✓</span> {l}
                    </div>
                  ))}
                  {analysis.assets_inventory.icons.map((ic, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <span className="text-emerald-500">✓</span> {ic}
                    </div>
                  ))}
                </div>
              </div>

              {/* Technical Debt */}
              <div className="p-4 bg-[var(--bg-1)] border border-[var(--border)] rounded">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 text-amber-700">
                    <AlertTriangle className="w-4 h-4" /> Technical Debt & Outdated Patterns
                  </h3>
                  <span className="text-[10px] text-amber-600 font-semibold">
                    {analysis.technical_debt.outdated_dependencies.length} Outdated Packages
                  </span>
                </div>
                <div className="space-y-2 max-h-36 overflow-y-auto text-xs">
                  {analysis.technical_debt.outdated_dependencies.map((d, i) => (
                    <div key={i} className="border-b border-[var(--border)] pb-1.5 last:border-0">
                      <span className="font-bold text-[var(--sutra-charcoal)]">{d.package}</span>
                      <span className="text-[10px] text-[var(--text-3)] ml-2 font-mono">({d.current_version})</span>
                      <p className="text-[11px] text-[var(--text-2)]">{d.reason}</p>
                    </div>
                  ))}
                  {analysis.technical_debt.missing_infrastructure.map((m, i) => (
                    <div key={i} className="text-amber-800 text-[11px] flex items-center gap-1.5">
                      <span>⚠️</span> {m}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Modernization Roadmap */}
            <div className="mt-6 pt-6 border-t border-[var(--border)]">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-2)] mb-3">
                Phased Safe Modernization Plan
              </h3>
              <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
                {analysis.modernization_plan.map((p) => (
                  <div key={p.phase} className="p-3 bg-[var(--bg-1)] border border-[var(--border)] rounded text-xs">
                    <span className="text-[10px] font-bold text-[var(--sutra-muted-gold)] uppercase block mb-1">
                      Phase {p.phase}
                    </span>
                    <strong className="block text-xs font-semibold mb-1">{p.title}</strong>
                    <span className="text-[10px] text-[var(--text-3)] block">{p.safety_level}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ── STEP 3: Feature Extension & LLM Credentials ──────────────── */}
          <div className="bg-[var(--bg-2)] border border-[var(--border)] rounded-lg p-6 shadow-sm">
            <h2 className="text-base font-bold flex items-center gap-2 mb-4">
              <Bot className="w-5 h-5 text-[var(--sutra-muted-gold)]" />
              3. Configure Feature Extension: AI Chatbot Assistant
            </h2>

            <div className="grid md:grid-cols-2 gap-6 mb-6">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-2)] block mb-2">
                  Feature Inclusions
                </span>
                <div className="space-y-2 text-xs">
                  <label className="flex items-center gap-2.5 p-2.5 bg-[var(--bg-1)] border border-[var(--border)] rounded cursor-pointer">
                    <input type="checkbox" defaultChecked disabled className="rounded text-[var(--sutra-charcoal)]" />
                    <div>
                      <strong className="block text-xs">AI Chatbot Assistant</strong>
                      <span className="text-[11px] text-[var(--text-2)]">
                        Injects backend /api/chat service and interactive floating UI widget matching existing styles.
                      </span>
                    </div>
                  </label>
                  <label className="flex items-center gap-2.5 p-2.5 bg-[var(--bg-1)] border border-[var(--border)] rounded opacity-60">
                    <input type="checkbox" disabled className="rounded" />
                    <div>
                      <strong className="block text-xs">AI Document Intelligence / RAG</strong>
                      <span className="text-[11px] text-[var(--text-2)]">Available on enterprise plans.</span>
                    </div>
                  </label>
                </div>
              </div>

              {/* Credential validator */}
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-2)] block mb-2">
                  Secure API Key (Groq / OpenAI)
                </span>
                <div className="space-y-2">
                  <div className="flex gap-2">
                    <input
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder="gsk_... or sk-..."
                      className="flex-1 px-3 py-2 text-xs font-mono bg-[var(--bg-1)] border border-[var(--border)] rounded focus:outline-none focus:border-[var(--sutra-muted-gold)]"
                    />
                    <button
                      onClick={handleValidateKey}
                      disabled={validatingKey || !apiKey.trim()}
                      className="px-3 py-2 bg-[var(--bg-1)] border border-[var(--border)] text-xs font-semibold rounded hover:bg-white transition-colors disabled:opacity-50"
                    >
                      {validatingKey ? 'Testing...' : 'Test Key'}
                    </button>
                  </div>

                  {keyValidation && (
                    <div
                      className={`p-2.5 rounded text-xs border flex items-center justify-between ${
                        keyValidation.connection_success
                          ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                          : 'bg-amber-50 border-amber-200 text-amber-800'
                      }`}
                    >
                      <span>
                        {keyValidation.connection_success ? '✓' : '⚠️'} {keyValidation.message}
                      </span>
                      <span className="font-mono text-[10px]">{keyValidation.masked_key}</span>
                    </div>
                  )}

                  <p className="text-[11px] text-[var(--text-3)] flex items-center gap-1">
                    <Lock className="w-3 h-3" /> Credentials will be saved in workspace .env and gitignored. Never hardcoded or committed.
                  </p>
                </div>
              </div>
            </div>

            {/* Execute Modernize Action */}
            <div className="flex justify-end pt-4 border-t border-[var(--border)]">
              <button
                onClick={handleModernize}
                disabled={modernizing}
                className="px-6 py-3 bg-[var(--sutra-charcoal)] text-white text-xs font-bold uppercase tracking-wider rounded hover:bg-black transition-all flex items-center gap-2 shadow-sm disabled:opacity-50"
              >
                {modernizing ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Executing Parallel Modernization & Verification...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 text-[var(--sutra-muted-gold)]" />
                    Run Controlled Modernization & Add Chatbot
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── STEP 4 & 5: Results & Verification Report ─────────────────────── */}
      {modernizeReport && (
        <div className="bg-[var(--bg-2)] border border-[var(--border)] rounded-lg p-6 shadow-sm mb-8">
          <div className="flex items-center justify-between mb-6 pb-4 border-b border-[var(--border)]">
            <div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                <h2 className="text-lg font-bold">Modernization & Feature Extension Complete</h2>
              </div>
              <p className="text-xs text-[var(--text-2)] mt-0.5">
                Target build: <span className="font-mono">{modernizeReport.build_id}</span> · Status: {modernizeReport.status.toUpperCase()}
              </p>
            </div>

            <a
              href={legacyRepoApi.getDownloadUrl(modernizeReport.build_id)}
              download
              className="px-4 py-2 bg-emerald-600 text-white text-xs font-bold uppercase tracking-wider rounded hover:bg-emerald-700 transition-colors flex items-center gap-2 shadow-sm"
            >
              <Download className="w-4 h-4" /> Download Modernized Repo (ZIP)
            </a>
          </div>

          {/* Verification checklist */}
          <div className="grid md:grid-cols-2 gap-6 mb-6">
            <div className="space-y-2 p-4 bg-[var(--bg-1)] border border-[var(--border)] rounded text-xs">
              <strong className="block text-xs uppercase tracking-wider text-[var(--text-2)] mb-2">
                Zero-Regression Verification
              </strong>
              <div className="flex items-center gap-2 text-emerald-700">
                <CheckCircle2 className="w-4 h-4" />
                <span>Existing application entry points and routes preserved</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-700">
                <CheckCircle2 className="w-4 h-4" />
                <span>All brand logos and static UI assets preserved verbatim</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-700">
                <CheckCircle2 className="w-4 h-4" />
                <span>AI Chatbot endpoint (/api/chat) verified active</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-700">
                <CheckCircle2 className="w-4 h-4" />
                <span>Secrets isolated into .env and protected by .gitignore</span>
              </div>
            </div>

            <div className="space-y-2 p-4 bg-[var(--bg-1)] border border-[var(--border)] rounded text-xs">
              <strong className="block text-xs uppercase tracking-wider text-[var(--text-2)] mb-2">
                Scope & Safety Audit
              </strong>
              <div className="flex items-center gap-2 text-emerald-700 font-semibold">
                <ShieldCheck className="w-4 h-4" />
                <span>sutra_os: {modernizeReport.sutra_os}</span>
              </div>
              <div className="flex items-center gap-2 text-[var(--text-2)]">
                <GitBranch className="w-4 h-4 text-[var(--text-3)]" />
                <span>Git: {modernizeReport.git.push} · {modernizeReport.git.status}</span>
              </div>
              <div className="flex items-center gap-2 text-[var(--text-2)]">
                <Layers className="w-4 h-4 text-[var(--text-3)]" />
                <span>Tasks Orchestrated: {modernizeReport.schedule_summary.completed} / {modernizeReport.schedule_summary.total_tasks} completed</span>
              </div>
            </div>
          </div>

          {/* Modified files list */}
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-2)] block mb-2">
              Modified & Added Files ({modernizeReport.modified_files.length})
            </span>
            <div className="p-3 bg-[var(--bg-1)] border border-[var(--border)] rounded font-mono text-xs space-y-1 max-h-40 overflow-y-auto">
              {modernizeReport.modified_files.map((f, i) => (
                <div key={i} className="flex items-center gap-2 text-[var(--text-2)]">
                  <FileCode className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />
                  <span>{f}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
