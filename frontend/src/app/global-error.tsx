'use client';

import { useEffect } from 'react';
import { Button } from "@/components/ui/button";

/**
 * Last-resort boundary for errors thrown by the root layout itself.
 *
 * `app/error.tsx` cannot catch a failure in `app/layout.tsx`, because the
 * boundary would be rendered *inside* the layout that failed. This file replaces
 * the entire document when that happens, so it has to render its own `<html>`
 * and `<body>` and cannot rely on any app styling, provider or font.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Nothing app-level is safe to import here: the providers may be part of what
    // broke, so this reports to the console directly.
    console.error('unhandled error in the root layout', error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '2rem',
          fontFamily:
            'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
          background: '#ffffff',
          color: '#171717',
        }}
      >
        <div style={{ textAlign: 'center', maxWidth: '32rem' }}>
          <h1 style={{ fontSize: '1.25rem', margin: 0 }}>
            The application failed to start
          </h1>
          <p style={{ fontSize: '0.875rem', lineHeight: 1.6, color: '#525252', marginTop: '0.5rem' }}>
            A problem outside any single screen stopped the app from rendering. Reloading
            usually clears it; if it persists, the deployment needs to be checked.
          </p>
          {error.digest && (
            <p style={{ fontSize: '0.7rem', color: '#8a8a8a', marginTop: '0.75rem' }}>
              Reference: {error.digest}
            </p>
          )}
          <Button variant="ghost" size="default"
            type="button"
            onClick={reset}
            style={{
              marginTop: '1.25rem',
              padding: '0.5rem 1rem',
              fontSize: '0.875rem',
              borderRadius: '0.5rem',
              border: '1px solid #171717',
              background: '#171717',
              color: '#ffffff',
              cursor: 'pointer',
            }}
           className="">
            Reload
          </Button>
        </div>
      </body>
    </html>
  );
}
