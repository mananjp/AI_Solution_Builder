'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { AlertCircle, Loader2 } from 'lucide-react';
import { useAuth0 } from '@auth0/auth0-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

/**
 * Auth0 redirect landing page.
 *
 * Two things are worth noting, because both were wrong before.
 *
 * First, this file lives in the `(auth)` route group, which is a grouping and
 * not a URL segment: it is served at `/callback`, not `/auth/callback`. The old
 * backend callback redirected to the latter, so the token never landed. The
 * `redirect_uri` the SDK sends must match, and the Auth0 dashboard's Allowed
 * Callback URLs must list the origin ending in `/callback` to match.
 *
 * Second, there is no token in the URL to read any more. The SDK exchanges the
 * authorization code for tokens itself, in memory, so there is nothing to copy
 * into localStorage and nothing to leak into browser history or a referrer.
 */
/**
 * Best available explanation for a failed sign-in.
 *
 * `useAuth0` types `error` as `Error`, but at runtime the SDK surfaces a
 * `WebAuthError` carrying the OAuth `error_description` ("Access Denied", or the
 * real reason the authorization server rejected the request). The context type
 * widens it, so the extra field is read defensively instead of asserted, and
 * the generic `Error.message` is the fallback.
 */
function readFailure(err: unknown): string | undefined {
  if (err && typeof err === 'object' && 'error_description' in err) {
    const description = (err as { error_description?: unknown }).error_description;
    if (typeof description === 'string' && description) return description;
  }
  return err instanceof Error && err.message ? err.message : undefined;
}

/**
 * Where to send the user after a successful exchange.
 *
 * The route guard sends a signed-out visitor to `/login?returnTo=…`, and
 * `AuthProvider.login` forwards that through Auth0 as `appState.returnTo`. This
 * page used to discard it and always land on `/dashboard`, so signing in from a
 * deep link silently dropped the user back at the dashboard root.
 *
 * `returnTo` is attacker-influenceable — it round-trips through a query string
 * and a third-party redirect — so an absolute or protocol-relative URL is
 * rejected. An unchecked value here is an open redirect.
 */
function landingPath(appState: unknown): string {
  const candidates: string[] = [];

  if (appState && typeof appState === 'object' && 'returnTo' in appState) {
    const value = (appState as { returnTo?: unknown }).returnTo;
    if (typeof value === 'string') candidates.push(value);
  }

  // `handleRedirectCallback` writes the state onto the history entry, but the
  // context value can lag by a render, so read it directly as a fallback.
  if (typeof window !== 'undefined') {
    const state = window.history.state as { returnTo?: unknown } | null;
    if (state && typeof state.returnTo === 'string') candidates.push(state.returnTo);
  }

  for (const candidate of candidates) {
    if (!candidate.startsWith('/')) continue;
    // `//evil.com` and `/\evil.com` are protocol-relative URLs, not local paths.
    if (candidate.startsWith('//') || candidate.startsWith('/\\')) continue;
    return candidate;
  }

  return '/dashboard';
}

export default function Auth0CallbackPage() {
  const router = useRouter();
  const { isLoading, isAuthenticated, error } = useAuth0();

  useEffect(() => {
    void (async () => {
      if (isLoading) return;
      if (isAuthenticated) {
        const state = window.history.state as { auth0AppState?: unknown } | null;
        router.replace(landingPath(state?.auth0AppState));
      }
    })();
  }, [isLoading, isAuthenticated, router]);

  const message = readFailure(error);

  if (message) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        <Card className="mx-auto w-full max-w-100">
          <CardContent className="space-y-4 p-8 text-center">
            <AlertCircle className="mx-auto size-6 text-destructive" />
            <h1 className="font-serif text-lg">Sign-in failed</h1>
            <p className="text-[13px] font-light text-muted">{message}</p>
            <Button asChild className="w-full">
              <a href="/login">Back to sign in</a>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="flex flex-col items-center gap-3 text-muted">
        <Loader2 className="size-5 animate-spin text-foreground" />
        <p className="text-[13px] font-light">Completing sign-in…</p>
      </div>
    </div>
  );
}
