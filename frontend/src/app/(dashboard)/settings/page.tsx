'use client';

import React, { useState } from 'react';
import { Check, Eye, EyeSlash, GitBranch, Lock, Rocket, ShieldCheck } from '@phosphor-icons/react/dist/ssr';
import { cn } from '@/lib/utils';
import { authApi } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';

export default function SettingsPage() {
  const [githubToken, setGithubToken] = useState('');
  const [renderApiKey, setRenderApiKey] = useState('');
  const [showTokens, setShowTokens] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<'idle' | 'saved' | 'error'>('idle');
  const [message, setMessage] = useState<string | null>(null);

  const [emailNotifications, setEmailNotifications] = useState(true);
  const [deploymentAlerts, setDeploymentAlerts] = useState(true);
  const [weeklyDigest, setWeeklyDigest] = useState(false);
  const [theme, setTheme] = useState('dark');
  const [language, setLanguage] = useState('en');

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
    <div className="p-6 lg:p-8 gap-8 max-w-4xl mx-auto flex flex-col">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-6 flex-wrap">
            <div className="gap-2">
              <Badge variant="outline" className="gap-1.5 w-fit">
                <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                One-Click Deployer
              </Badge>
              <CardTitle>Deployment Credentials</CardTitle>
              <CardDescription>
                Save your GitHub Personal Access Token and Render API key to enable one-click deployment of generated MVP
                code. Credentials are stored per-account, encrypted at rest, and never exposed through the API.
              </CardDescription>
            </div>
            <Rocket className="h-12 w-12 text-primary/60" />
          </div>
        </CardHeader>
      </Card>

      {/* Credentials Form */}
      <form onSubmit={handleSave}>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">API Keys</CardTitle>
            <CardDescription>Configure your deployment provider credentials</CardDescription>
          </CardHeader>
          <CardContent className="gap-6">
            <div className="gap-2">
              <Label htmlFor="github-token" className="flex items-center gap-2">
                <GitBranch className="h-3.5 w-3.5 text-muted-foreground" />
                GitHub Personal Access Token (PAT)
              </Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="github-token"
                  type={showTokens ? 'text' : 'password'}
                  value={githubToken}
                  onChange={(e) => setGithubToken(e.target.value)}
                  placeholder="ghp_••••••••••••••••••••••••••"
                  className="pl-9 pr-11 font-mono"
                  autoComplete="off"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowTokens(!showTokens)}
                  className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                  title={showTokens ? 'Hide secrets' : 'Reveal secrets'}
                >
                  {showTokens ? <EyeSlash className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Scopes needed: <code className="text-primary">repo</code> to create the fresh repository and push files during deploy.
              </p>
            </div>

            <Separator />

            <div className="gap-2">
              <Label htmlFor="render-api-key" className="flex items-center gap-2">
                <Rocket className="h-3.5 w-3.5 text-muted-foreground" />
                Render API Key
              </Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="render-api-key"
                  type={showTokens ? 'text' : 'password'}
                  value={renderApiKey}
                  onChange={(e) => setRenderApiKey(e.target.value)}
                  placeholder="rnd_••••••••••••••••••••••"
                  className="pl-9 pr-11 font-mono"
                  autoComplete="off"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowTokens(!showTokens)}
                  className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                  title={showTokens ? 'Hide secrets' : 'Reveal secrets'}
                >
                  {showTokens ? <EyeSlash className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Optional — used to trigger an automatic Render deploy after the GitHub push.
              </p>
            </div>

            {message && (
              <div
                className={cn(
                  'flex items-center gap-2 px-4 py-3 rounded text-xs font-medium border',
                  status === 'saved'
                    ? 'bg-success/10 border-success/30 text-success'
                    : 'bg-destructive/10 border-destructive/30 text-destructive',
                )}
              >
                {status === 'saved' && <Check className="h-3.5 w-3.5 shrink-0" />}
                {message}
              </div>
            )}
          </CardContent>
          <CardFooter className="justify-end">
            <Button type="submit" disabled={saving}>
              {saving ? 'Saving...' : 'Save Credentials'}
            </Button>
          </CardFooter>
        </Card>
      </form>

      {/* Notifications */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Notifications</CardTitle>
          <CardDescription>Configure how you receive platform notifications</CardDescription>
        </CardHeader>
        <CardContent className="gap-4">
          <div className="flex items-center justify-between">
            <div className="gap-0.5">
              <Label htmlFor="email-notifications">Email Notifications</Label>
              <p className="text-xs text-muted-foreground">Receive email updates for important events</p>
            </div>
            <Switch id="email-notifications" checked={emailNotifications} onCheckedChange={setEmailNotifications} />
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <div className="gap-0.5">
              <Label htmlFor="deployment-alerts">Deployment Alerts</Label>
              <p className="text-xs text-muted-foreground">Get notified when deployments succeed or fail</p>
            </div>
            <Switch id="deployment-alerts" checked={deploymentAlerts} onCheckedChange={setDeploymentAlerts} />
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <div className="gap-0.5">
              <Label htmlFor="weekly-digest">Weekly Digest</Label>
              <p className="text-xs text-muted-foreground">Receive a weekly summary of platform activity</p>
            </div>
            <Switch id="weekly-digest" checked={weeklyDigest} onCheckedChange={setWeeklyDigest} />
          </div>
        </CardContent>
        <CardFooter className="justify-end">
          <Button variant="outline">Save Preferences</Button>
        </CardFooter>
      </Card>

      {/* Appearance */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Appearance</CardTitle>
          <CardDescription>Customize the look and feel of the dashboard</CardDescription>
        </CardHeader>
        <CardContent className="gap-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="gap-2">
              <Label htmlFor="theme-select">Theme</Label>
              <Select value={theme} onValueChange={(v) => v && setTheme(v)}>
                <SelectTrigger id="theme-select">
                  <SelectValue placeholder="Select theme" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="light">Light</SelectItem>
                  <SelectItem value="dark">Dark</SelectItem>
                  <SelectItem value="system">System</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="gap-2">
              <Label htmlFor="language-select">Language</Label>
              <Select value={language} onValueChange={(v) => v && setLanguage(v)}>
                <SelectTrigger id="language-select">
                  <SelectValue placeholder="Select language" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="en">English</SelectItem>
                  <SelectItem value="es">Spanish</SelectItem>
                  <SelectItem value="fr">French</SelectItem>
                  <SelectItem value="de">German</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
        <CardFooter className="justify-end">
          <Button variant="outline">Save Appearance</Button>
        </CardFooter>
      </Card>

      {/* Usage Hint */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">How the deployer uses these</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="flex flex-col gap-2 text-xs text-muted-foreground list-decimal list-inside">
            <li>Finish an MVP build for a solution (chat → blueprints → <span className="text-primary font-medium">Build &amp; Deploy</span>).</li>
            <li>
              On the MVP page, pick <span className="text-primary font-medium">Deploy to GitHub</span> and enter a repository name.
            </li>
            <li>
              The deployer creates a fresh private repository with your PAT and pushes the full generated project — including a
              Render blueprint (<code className="text-primary">render.yaml</code>) and CI workflow.
            </li>
            <li>Connect the repository to Render and it auto-deploys on green CI.</li>
          </ol>
        </CardContent>
      </Card>
    </div>
  );
}
