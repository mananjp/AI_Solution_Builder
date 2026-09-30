'use client';

import type { ReactNode } from 'react';
import type { AppState } from '@auth0/auth0-react';
import { Auth0Provider as SdkProvider } from '@auth0/auth0-react';

import { AuthProvider } from '@/components/auth/AuthProvider';
import { auth0Config, isAuth0Configured } from '@/lib/auth0-client';

/**
 * Auth0 + app session, wired together.
 *
 * The SDK is skipped entirely when the build has no Auth0 env vars. Handing the
 * provider an empty domain makes it throw during its first hook call, which
 * would take down every page including the login page whose whole job is to
 * explain the problem. Rendering only the local `AuthProvider` in that case
 * lets the app boot and show the configuration error instead.
 *
 * `auth0Config` needs no client-side adjustment: server and browser each
 * evaluate the module separately, so `redirect_uri` is populated in the bundle
 * that actually performs the redirect and `undefined` in the one that only
 * renders markup.
 */
export function Auth0Wrapper({ children }: { children: ReactNode }) {
  if (!isAuth0Configured) {
    return <AuthProvider>{children}</AuthProvider>;
  }

  return (
    <SdkProvider
      {...auth0Config}
      onRedirectCallback={(appState?: AppState) => {
        // The SDK completes the code exchange before this callback. Preserve
        // its return path for /callback, and remove OAuth parameters from the
        // address bar without discarding that state.
        window.history.replaceState(
          { ...window.history.state, auth0AppState: appState },
          document.title,
          window.location.pathname,
        );
      }}
    >
      <AuthProvider>{children}</AuthProvider>
    </SdkProvider>
  );
}
