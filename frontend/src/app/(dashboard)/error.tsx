'use client';

import { useEffect } from 'react';
import { RefreshCw, TriangleAlert } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { logError } from '@/lib/logger';

/**
 * Route-level error boundary for the dashboard group.
 *
 * Without this, any uncaught error during render or in an effect unmounts the
 * whole tree and the user gets a blank white page with no indication of what
 * happened and nothing in the console to report. This catches it at the segment
 * boundary, keeps the rest of the shell (including the sidebar) mounted, and
 * shows a recoverable state.
 */
export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // `digest` is the server-side correlation id; without error tracking wired up
    // it is the only handle a user can quote when reporting a failure.
    logError('unhandled error in the dashboard shell', error, { digest: error.digest });
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-8 text-center">
      <TriangleAlert className="size-8 text-[var(--amber)]" aria-hidden />
      <div>
        <h1 className="font-serif text-xl text-foreground">This screen hit an error</h1>
        <p className="mx-auto mt-2 max-w-md text-[13px] font-light leading-relaxed text-muted">
          The rest of the app is still usable. You can retry this screen, or move to
          another one from the sidebar.
        </p>
      </div>
      {error.digest && (
        <p className="font-mono text-[10px] text-[var(--text-3)]">Reference: {error.digest}</p>
      )}
      <div className="flex gap-2">
        <Button onClick={reset}>
          <RefreshCw />
          Try again
        </Button>
        <Button asChild variant="outline">
          <a href="/dashboard">Go to dashboard</a>
        </Button>
      </div>
    </div>
  );
}
