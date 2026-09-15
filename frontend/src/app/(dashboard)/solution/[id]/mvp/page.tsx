'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Check,
  Cube,
  Download,
  Folder,
  FolderOpen,
  File,
  CircleNotch,
  Play,
  ArrowClockwise,
  Rocket,
  GearSix,
  Trash,
  Plus,
  X,
  Coins,
  Sparkle,
} from '@phosphor-icons/react/dist/ssr';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { mvpApi, solutionApi } from '@/lib/api';
import { MVPBuild, MVPBuildStatus, MVPTemplate, Solution } from '@/types';

const STATUS_CONFIG: Record<
  MVPBuildStatus,
  { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline'; className?: string }
> = {
  pending: { label: 'Pending', variant: 'outline' },
  building: { label: 'Building', variant: 'default', className: 'animate-pulse' },
  complete: { label: 'Complete', variant: 'secondary', className: 'text-success' },
  failed: { label: 'Failed', variant: 'destructive' },
  cancelled: { label: 'Cancelled', variant: 'outline' },
};


function StatusBadge({ status }: { status: MVPBuildStatus }) {
  const config = STATUS_CONFIG[status];
  return (
    <Badge variant={config.variant} className={cn('gap-1', config.className)}>
      {status === 'building' && <CircleNotch weight="bold" className="w-3 h-3 animate-spin" />}
      {config.label}
    </Badge>
  );
}

function FileIcon({ is_dir }: { is_dir: boolean }) {
  if (is_dir) return <Folder className="w-3.5 h-3.5 text-primary flex-shrink-0" />;
  return <File className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />;
}

function BuildLog({ build }: { build: MVPBuild }) {
  const logRef = useRef<HTMLDivElement>(null);
  const [logs, setLogs] = useState<string[]>([]);

  useEffect(() => {
    if (build.status === 'building' || build.status === 'pending') {
      setLogs((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        const msg = `[${new Date().toLocaleTimeString()}] ${build.status === 'building' ? 'Agent is generating code...' : 'Waiting for build to start...'}`;
        if (last !== msg) next.push(msg);
        return next;
      });
      return;
    }

    if (build.status === 'complete') {
      setLogs((prev) => {
        const msg = `[${new Date().toLocaleTimeString()}] Build complete — ${build.file_count} files generated.`;
        return prev[prev.length - 1] === msg ? prev : [...prev, msg];
      });
      return;
    }

    if (build.status === 'failed') {
      setLogs((prev) => {
        const msg = `[${new Date().toLocaleTimeString()}] Build failed: ${build.error_message || 'Unknown error'}`;
        return prev[prev.length - 1] === msg ? prev : [...prev, msg];
      });
    }
  }, [build.status, build.file_count, build.error_message]);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs]);

  const isActive = build.status === 'building' || build.status === 'pending';

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold text-muted-foreground">Build Log</span>
        {isActive && <CircleNotch weight="bold" className="w-3 h-3 animate-spin text-primary" />}
      </div>
      <div
        ref={logRef}
        className="rounded-lg bg-secondary border border-border p-3 max-h-48 overflow-y-auto"
      >
        {logs.length === 0 ? (
          <p className="text-xs text-muted-foreground font-mono">
            {build.status === 'complete'
              ? 'Build finished.'
              : build.status === 'failed'
                ? 'Build ended with an error.'
                : 'Initializing build...'}
          </p>
        ) : (
          <div className="flex flex-col gap-1">
            {logs.map((line, i) => (
              <p key={i} className="text-xs font-mono text-muted-foreground leading-relaxed">
                {line}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function FileTree({ build }: { build: MVPBuild }) {
  const [open, setOpen] = useState(false);
  const files = build.files || [];

  return (
    <div className="flex flex-col gap-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors"
      >
        {open ? (
          <FolderOpen className="w-3.5 h-3.5 text-primary" />
        ) : (
          <Folder className="w-3.5 h-3.5 text-primary" />
        )}
        <span>Generated Files ({build.file_count})</span>
        <span className="text-muted-foreground font-mono text-[10px]">{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <ScrollArea className="max-h-56 rounded-lg bg-secondary border border-border p-3">
          {files.length === 0 ? (
            <p className="text-xs text-muted-foreground font-mono">No file tree available.</p>
          ) : (
            <div className="flex flex-col gap-0.5">
              {files.map((f) => (
                <div key={f.path} className="flex items-center gap-2 text-xs font-mono py-0.5">
                  <FileIcon is_dir={f.is_dir} />
                  <span className={cn(f.is_dir ? 'font-semibold text-foreground' : 'text-muted-foreground')}>
                    {f.path}
                  </span>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      )}
    </div>
  );
}

function DeployModal({
  build,
  onClose,
  onDeployed,
}: {
  build: MVPBuild;
  onClose: () => void;
  onDeployed: (repoUrl: string) => void;
}) {
  const [repoName, setRepoName] = useState(`mvp-${build.build_id.slice(0, 8)}`);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDeploy = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await mvpApi.deploy(build.build_id, {
        repo_name: repoName.trim(),
        private: true,
      });
      onDeployed(res.repo_url);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Deploy failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Rocket className="w-4 h-4 text-primary" />
            Deploy to GitHub
          </DialogTitle>
          <DialogDescription>
            Push build #{build.build_number} to a new GitHub repository.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/30 px-3 py-2">
            <p className="text-xs text-destructive font-mono">{error}</p>
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-muted-foreground">Repository Name</label>
          <Input
            value={repoName}
            onChange={(e) => setRepoName(e.target.value)}
            placeholder="my-mvp-app"
            className="font-mono"
          />
        </div>

        <DialogFooter>
          <DialogClose render={<Button variant="ghost" size="sm" />}>Cancel</DialogClose>
          <Button
            size="sm"
            onClick={handleDeploy}
            disabled={loading || !repoName.trim()}
            className="gap-1.5"
          >
            {loading ? (
              <CircleNotch weight="bold" className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Rocket className="w-3.5 h-3.5" />
            )}
            <span>Deploy</span>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function deriveAppName(solution: Solution | null): string {
  const aiState = solution?.ai_state ?? {};

  const candidate =
    typeof aiState.solution_title === 'string' && aiState.solution_title.trim()
      ? aiState.solution_title.trim()
      : typeof aiState.app_name === 'string' && aiState.app_name.trim()
        ? aiState.app_name.trim()
        : typeof solution?.title === 'string' && solution.title.trim()
          ? solution.title.trim()
          : 'My MVP';

  return candidate
    .replace(/[_-]+/g, ' ')
    .replace(/[^a-zA-Z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .split(' ')
    .filter(Boolean)
    .slice(0, 6)
    .join(' ')
    .trim() || 'My MVP';
}

function deriveBuildBrief(solution: Solution | null): string {
  const aiState = solution?.ai_state ?? {};

  const directText =
    typeof aiState.business_description === 'string' && aiState.business_description.trim()
      ? aiState.business_description.trim()
      : typeof aiState.solution_summary === 'string' && aiState.solution_summary.trim()
        ? aiState.solution_summary.trim()
        : typeof aiState.summary === 'string' && aiState.summary.trim()
          ? aiState.summary.trim()
          : typeof aiState.value_proposition === 'string' && aiState.value_proposition.trim()
            ? aiState.value_proposition.trim()
            : '';

  if (directText) return directText;

  const moduleValues = [
    ...(Array.isArray(aiState.confirmed_modules) ? aiState.confirmed_modules : []),
    ...(Array.isArray(aiState.identified_solutions) ? aiState.identified_solutions : []),
  ]
    .filter((value): value is string => typeof value === 'string' && value.trim().length > 0)
    .slice(0, 4);

  if (moduleValues.length > 0) {
    const base = solution?.title ? `Build a ${solution.title} MVP` : 'Build an MVP';
    return `${base} with core modules: ${moduleValues.join(', ')}.`;
  }

  return solution?.description?.trim() || '';
}

function ConfigureModal({
  build,
  onClose,
  onConfigured,
}: {
  build: MVPBuild;
  onClose: () => void;
  onConfigured: () => void;
}) {
  const [appName, setAppName] = useState('');
  const [envPairs, setEnvPairs] = useState<{ key: string; value: string }[]>([
    { key: '', value: '' },
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addPair = () => setEnvPairs((prev) => [...prev, { key: '', value: '' }]);
  const removePair = (idx: number) => setEnvPairs((prev) => prev.filter((_, i) => i !== idx));
  const updatePair = (idx: number, field: 'key' | 'value', val: string) =>
    setEnvPairs((prev) => prev.map((p, i) => (i === idx ? { ...p, [field]: val } : p)));

  const handleConfigure = async () => {
    setLoading(true);
    setError(null);
    const env: Record<string, unknown> = {};
    for (const pair of envPairs) {
      const k = pair.key.trim();
      const v = pair.value.trim();
      if (!k) continue;
      if (k.includes(' ')) {
        setError(`Invalid key: "${k}". Keys must not contain spaces.`);
        setLoading(false);
        return;
      }
      env[k] = v;
    }
    try {
      await mvpApi.configure(build.build_id, {
        app_name: appName.trim() || undefined,
        env,
      });
      onConfigured();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Configure failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <GearSix className="w-4 h-4 text-primary" />
            Configure Build #{build.build_number}
          </DialogTitle>
          <DialogDescription>Override the app name and set environment variables.</DialogDescription>
        </DialogHeader>

        {error && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/30 px-3 py-2">
            <p className="text-xs text-destructive font-mono">{error}</p>
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-semibold text-muted-foreground">App Name (optional)</label>
          <Input
            value={appName}
            onChange={(e) => setAppName(e.target.value)}
            placeholder="my-production-app"
            className="font-mono"
          />
        </div>

        <Separator />

        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-muted-foreground">Environment Variables</label>
            <Button variant="ghost" size="xs" onClick={addPair} className="gap-1">
              <Plus className="w-3 h-3" />
              <span>Add</span>
            </Button>
          </div>
          <div className="flex flex-col gap-2">
            {envPairs.map((pair, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <Input
                  value={pair.key}
                  onChange={(e) => updatePair(idx, 'key', e.target.value)}
                  placeholder="KEY"
                  className="font-mono flex-1"
                />
                <Input
                  value={pair.value}
                  onChange={(e) => updatePair(idx, 'value', e.target.value)}
                  placeholder="value"
                  className="font-mono flex-1"
                />
                {envPairs.length > 1 && (
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    onClick={() => removePair(idx)}
                    className="flex-shrink-0"
                  >
                    <X className="w-3 h-3" />
                  </Button>
                )}
              </div>
            ))}
          </div>
          <p className="text-[11px] text-muted-foreground">Written to .env.local on deploy.</p>
        </div>

        <DialogFooter>
          <DialogClose render={<Button variant="ghost" size="sm" />}>Cancel</DialogClose>
          <Button size="sm" onClick={handleConfigure} disabled={loading} className="gap-1.5">
            {loading ? (
              <CircleNotch weight="bold" className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Check className="w-3.5 h-3.5" />
            )}
            <span>Save</span>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function MvpPage() {
  const params = useParams();
  const solutionId = (params?.id as string) || '';

  const [solution, setSolution] = useState<Solution | null>(null);
  const [builds, setBuilds] = useState<MVPBuild[]>([]);
  const [buildDetail, setBuildDetail] = useState<MVPBuild | null>(null);
  const [buildsLoaded, setBuildsLoaded] = useState(false);
  const [buildsLoading, setBuildsLoading] = useState(true);
  const [buildsError, setBuildsError] = useState<string | null>(null);
  const [appName, setAppName] = useState('');
  const [buildConcept, setBuildConcept] = useState('');
  const [starting, setStarting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [deployTarget, setDeployTarget] = useState<MVPBuild | null>(null);
  const [configureTarget, setConfigureTarget] = useState<MVPBuild | null>(null);

  const loadBuilds = useCallback(async (showLoading = false) => {
    if (showLoading) setBuildsLoading(true);
    setBuildsError(null);
    try {
      const nextBuilds = await mvpApi.listBuilds(solutionId);
      setBuilds((prev) => {
        if (nextBuilds.length === 0 && prev.length > 0) {
          return prev;
        }
        return nextBuilds;
      });
      setBuildsLoaded(true);
    } catch (err) {
      setBuildsError(err instanceof Error ? err.message : 'Could not load build history.');
      setBuildsLoaded(true);
    } finally {
      if (showLoading) setBuildsLoading(false);
    }
  }, [solutionId]);

  const loadBuildDetail = useCallback(async (buildId: string) => {
    try {
      const detail = await mvpApi.getStatus(buildId);
      setBuildDetail(detail);
      return detail;
    } catch {
      return null;
    }
  }, []);

  useEffect(() => {
    solutionApi
      .get(solutionId)
      .then((nextSolution) => {
        setSolution(nextSolution);
        const generatedName = deriveAppName(nextSolution);
        setAppName((prev) => (prev.trim() ? prev : generatedName));
        const recommendedBrief = deriveBuildBrief(nextSolution);
        setBuildConcept((prev) => (prev.trim() ? prev : recommendedBrief));
      })
      .catch(() => {
        setSolution(null);
      });
  }, [solutionId]);

  useEffect(() => {
    loadBuilds(true);
  }, [loadBuilds]);

  // Poll for active builds and fetch detail when complete
  useEffect(() => {
    const hasActive = builds.some((b) => b.status === 'pending' || b.status === 'building');
    if (!hasActive) {
      // If we just finished, fetch the detail for the latest complete build
      const latestComplete = builds.find((b) => b.status === 'complete');
      if (latestComplete && (!buildDetail || buildDetail.build_id !== latestComplete.build_id || !buildDetail.files?.length)) {
        loadBuildDetail(latestComplete.build_id);
      }
      return;
    }
    const timer = setInterval(async () => {
      await loadBuilds(false);
    }, 3000);
    return () => clearInterval(timer);
  }, [builds, loadBuilds, loadBuildDetail, buildDetail]);

  // Fetch detail for the visible build when it changes
  useEffect(() => {
    const target = builds.find((b) => b.status === 'complete' || b.status === 'building' || b.status === 'pending');
    if (target && target.files && target.files.length === 0 && target.status === 'complete') {
      loadBuildDetail(target.build_id);
    }
  }, [builds, loadBuildDetail]);

  const handleStartBuild = async () => {
    if (starting) return;
    setStarting(true);
    setActionError(null);
    try {
      const generatedBrief = deriveBuildBrief(solution);
      const generatedName = deriveAppName(solution);
      const buildConceptToUse = buildConcept.trim() || generatedBrief || undefined;
      const appNameToUse = appName.trim() || generatedName || undefined;

      const newBuild = await mvpApi.triggerBuild(solutionId, {
        app_name: appNameToUse,
        config: {
          build_concept: buildConceptToUse || undefined,
        },
        force: solution?.status !== 'complete' || Boolean(buildConceptToUse),
      });
      setAppName('');
      setBuildConcept('');
      setBuildDetail(newBuild);
      await loadBuilds(false);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to start build.';
      setActionError(
        message.includes('status 409') || message.includes('artifacts must be generated')
          ? 'This solution is not fully generated yet. Add a clear build brief below and start again.'
          : message
      );
    } finally {
      setStarting(false);
    }
  };

  const handleDownload = async (build: MVPBuild) => {
    try {
      await mvpApi.downloadBuild(
        build.build_id,
        `mvp_${build.solution_id.slice(0, 8)}_build${build.build_number}.zip`
      );
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Download failed.');
    }
  };

  const handleDestroy = async (build: MVPBuild) => {
    if (!window.confirm(`Destroy build #${build.build_number}? This cannot be undone.`)) return;
    try {
      await mvpApi.destroy(build.build_id);
      if (buildDetail?.build_id === build.build_id) {
        setBuildDetail(null);
      }
      await loadBuilds(false);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Destroy failed.');
    }
  };

  const handleDeployed = (repoUrl: string) => {
    setBuilds((prev) =>
      prev.map((b) =>
        b.status === 'complete' && b.build_id === deployTarget?.build_id
          ? { ...b, repo_url: repoUrl }
          : b
      )
    );
    if (buildDetail && buildDetail.build_id === deployTarget?.build_id) {
      setBuildDetail({ ...buildDetail, repo_url: repoUrl });
    }
  };

  const sortedBuilds = [...builds].sort((a, b) => b.build_number - a.build_number);
  const activeBuild = sortedBuilds.find((b) => b.status === 'pending' || b.status === 'building') || null;
  const latestComplete = sortedBuilds.find((b) => b.status === 'complete') || null;
  // Prefer buildDetail (fetched from /status endpoint) which includes files
  const visibleBuildResult = buildDetail && (buildDetail.status === 'complete' || buildDetail.status === 'building')
    ? buildDetail
    : latestComplete || activeBuild;
  const designReady = solution?.status === 'complete';
  const noBuildsYet = builds.length === 0 && buildsLoaded && !buildsLoading && !buildsError;

  return (
    <div className="p-6 lg:p-8 flex flex-col gap-6 max-w-[960px] mx-auto w-full">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Link
          href={`/solution/${solutionId}`}
          className="inline-flex items-center gap-2 text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Solution</span>
        </Link>
      </div>

      {/* Build Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Rocket className="w-4 h-4 text-primary" />
            <span>Build MVP</span>
          </CardTitle>
          <CardDescription>
            Start from the generated solution. Add a small tweak only if you want something specific.
          </CardDescription>
        </CardHeader>

        <CardContent className="flex flex-col gap-5">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-muted-foreground">Optional direction</label>
            <textarea
              value={buildConcept}
              onChange={(e) => setBuildConcept(e.target.value)}
              placeholder="Small tweak only: faster checkout flow, more premium UI, or different onboarding tone"
              className="min-h-20 w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-primary"
            />
          </div>

          {/* App Name + Build Button */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-end gap-3">
            <div className="flex-1 flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-muted-foreground">App Name (optional)</label>
              <Input
                value={appName}
                onChange={(e) => setAppName(e.target.value)}
                placeholder={solution?.title || 'my-app'}
                className="font-mono"
              />
            </div>
            <Button
              onClick={handleStartBuild}
              disabled={starting || Boolean(activeBuild)}
              className="gap-2 sm:w-auto"
            >
              {starting ? (
                <CircleNotch weight="bold" className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkle className="w-4 h-4" weight="fill" />
              )}
              <span>Start Build</span>
              <span className="ml-1 text-xs opacity-70 flex items-center gap-1">
                <Coins className="w-3 h-3" />
                Unlimited
              </span>
            </Button>
          </div>

          {actionError && (
            <div className="rounded-lg bg-destructive/10 border border-destructive/30 px-3 py-2">
              <p className="text-xs text-destructive font-mono">{actionError}</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Build Status */}
      {activeBuild && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <CardTitle className="text-sm">Build #{activeBuild.build_number}</CardTitle>
                <StatusBadge status={activeBuild.status} />
              </div>
              <Button variant="ghost" size="xs" onClick={() => loadBuilds(false)} className="gap-1">
                <ArrowClockwise className="w-3 h-3" />
                <span>Refresh</span>
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <BuildLog build={activeBuild} />
          </CardContent>
        </Card>
      )}

      {/* Build Results */}
      {visibleBuildResult && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <CardTitle className="text-sm">Build #{visibleBuildResult.build_number}</CardTitle>
                <StatusBadge status={visibleBuildResult.status} />
                {visibleBuildResult.repo_url && (
                  <a
                    href={visibleBuildResult.repo_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:text-primary/80 transition-colors"
                  >
                    <span>Deployed</span>
                  </a>
                )}
              </div>
              <div className="flex items-center gap-1.5">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDownload(visibleBuildResult)}
                  className="gap-1.5"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download ZIP</span>
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setConfigureTarget(visibleBuildResult)}
                  className="gap-1.5"
                >
                  <GearSix className="w-3.5 h-3.5" />
                  <span>Configure</span>
                </Button>
                <Button
                  size="sm"
                  onClick={() => setDeployTarget(visibleBuildResult)}
                  disabled={Boolean(visibleBuildResult.repo_url)}
                  className="gap-1.5"
                >
                  <Rocket className="w-3.5 h-3.5" />
                  <span>{visibleBuildResult.repo_url ? 'Deployed' : 'Deploy to GitHub'}</span>
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {visibleBuildResult.error_message && (
              <div className="rounded-lg bg-destructive/10 border border-destructive/30 px-3 py-2">
                <p className="text-xs text-destructive font-mono">{visibleBuildResult.error_message}</p>
              </div>
            )}
            <FileTree build={visibleBuildResult} />
          </CardContent>
        </Card>
      )}

      {/* All Builds List */}
      {buildsError && (
        <div className="rounded-lg bg-destructive/10 border border-destructive/30 px-3 py-2">
          <p className="text-xs text-destructive font-medium">{buildsError}</p>
          <p className="mt-1 text-[11px] text-destructive/80">
            The build service may be unavailable or the backend connection may be down.
          </p>
        </div>
      )}

      {noBuildsYet && (
        <Card className="border-dashed border-border bg-transparent">
          <CardContent className="py-8">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="rounded-md bg-primary/10 p-2">
                  <Rocket className="w-4 h-4 text-primary" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-foreground">
                    {designReady ? 'Design is complete — no MVP build exists yet' : 'MVP build not ready'}
                  </h3>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {designReady
                      ? 'Your solution has been generated, but the MVP has not been built yet.'
                      : 'Complete the solution design first, then generate the MVP.'}
                  </p>
                </div>
              </div>

              {designReady && (
                <Button
                  onClick={handleStartBuild}
                  disabled={starting || Boolean(activeBuild)}
                  className="gap-2 whitespace-nowrap"
                >
                  {starting ? (
                    <CircleNotch weight="bold" className="w-4 h-4 animate-spin" />
                  ) : (
                    <Sparkle className="w-4 h-4" weight="fill" />
                  )}
                  <span>Generate MVP</span>
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {sortedBuilds.length > 0 && (
        <div className="flex flex-col gap-3">
          <h3 className="text-sm font-semibold text-foreground">Build history</h3>
          <div className="flex flex-col gap-2">
            {sortedBuilds.map((build) => (
              <div
                key={build.build_id}
                className="flex items-center justify-between p-3 rounded-lg bg-card border border-border"
              >
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-muted-foreground">#{build.build_number}</span>
                  <StatusBadge status={build.status} />
                  <span className="text-xs text-muted-foreground font-mono">
                    {build.file_count} files
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  {build.status === 'complete' && (
                    <>
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        onClick={() => handleDownload(build)}
                      >
                        <Download className="w-3.5 h-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        onClick={() => setDeployTarget(build)}
                      >
                        <Rocket className="w-3.5 h-3.5" />
                      </Button>
                    </>
                  )}
                  {(build.status === 'failed' || build.status === 'cancelled') && (
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      onClick={() => handleDestroy(build)}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash className="w-3.5 h-3.5" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {buildsLoading && !buildsLoaded && (
        <div className="flex flex-col gap-3 rounded-lg border border-border p-4">
          <div className="h-4 w-32 animate-pulse rounded bg-secondary" />
          <div className="h-10 animate-pulse rounded bg-secondary" />
          <div className="h-10 animate-pulse rounded bg-secondary" />
        </div>
      )}

      {/* Modals */}
      {deployTarget && (
        <DeployModal
          build={deployTarget}
          onClose={() => setDeployTarget(null)}
          onDeployed={handleDeployed}
        />
      )}
      {configureTarget && (
        <ConfigureModal
          build={configureTarget}
          onClose={() => setConfigureTarget(null)}
          onConfigured={loadBuilds}
        />
      )}
    </div>
  );
}
