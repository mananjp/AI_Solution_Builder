/**
 * Auth0 SPA configuration.
 *
 * Only two values are required, and both are public identifiers: a SPA client
 * ID is not a secret (it is visible in the browser bundle and in the OIDC
 * discovery document by design), and there is no client secret. Confidentiality
 * comes from the PKCE flow and short-lived access tokens, not from hiding the
 * client ID.
 *
 * This module deliberately exports plain options rather than an SDK client
 * instance. `@auth0/auth0-react` v2 has no `Auth0Client` export, and the
 * provider builds its own client from the props it is given. Keeping the values
 * here as data means the "is this configured?" check and the provider props
 * cannot disagree.
 */

import type { Auth0ClientOptions } from '@auth0/auth0-spa-js';

const domain = (process.env.NEXT_PUBLIC_AUTH0_DOMAIN ?? '').trim();
const clientId = (process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID ?? '').trim();
const audience = (process.env.NEXT_PUBLIC_AUTH0_AUDIENCE ?? '').trim();

/**
 * True when the build received both required env vars. Used to render a precise
 * configuration error instead of an opaque SDK exception, and to skip guarding
 * routes in a checkout that has no tenant yet.
 */
export const isAuth0Configured = Boolean(domain && clientId);

/**
 * Where Auth0 should return the browser to.
 *
 * This must be the `/callback` route, not the origin root: the SDK's implicit
 * default is `window.location.origin`, which would land the authorization code
 * on `/` where nothing reads it. The route lives in the `(auth)` route group,
 * which is a grouping and not a URL segment, so its path is `/callback`.
 *
 * It can only be resolved in the browser. Returning `undefined` during SSR is
 * deliberate and safe: the SDK reads this option when a redirect is initiated,
 * long after hydration, by which time the client-side value applies.
 */
export function getCallbackUrl(): string | undefined {
  const explicit = (process.env.NEXT_PUBLIC_AUTH0_CALLBACK_URL ?? '').trim();
  if (explicit) return explicit;
  if (typeof window === 'undefined') return undefined;
  return `${window.location.origin}/callback`;
}

export const auth0Config: Auth0ClientOptions = {
  domain,
  clientId,
  authorizationParams: {
    redirect_uri: getCallbackUrl(),
    // `audience` is what makes Auth0 issue an *access* token for our API rather
    // than an *ID* token describing the user. The backend rejects tokens
    // without it, so this must match `AUTH0_AUDIENCE` exactly.
    audience: audience || undefined,
    // Ask for the claims the API reads. `roles` is namespaced by an Auth0
    // Action, not by a connection, so it is not requested here.
    scope: 'openid profile email',
  },
  // Tokens are held in memory only. Nothing about the session is written to
  // localStorage, so closing the tab ends it and no token is left in storage
  // for another script to read. This costs a silent re-auth on return visits
  // when no refresh token is available, which is the intended trade.
  cacheLocation: 'memory',
  useRefreshTokens: true,
  // Only reached if the refresh-token exchange fails, e.g. the rotating refresh
  // token expired. Without it, that situation reads as "signed out".
  useRefreshTokensFallback: true,
  // Background renewal happens on a slow connection often enough that a tight
  // budget reads as a random sign-out. Raising it lets the renewal finish
  // instead of surfacing an error the user cannot act on.
  authorizeTimeoutInSeconds: 15,
};
