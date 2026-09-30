"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth0 } from "@auth0/auth0-react";
import { toast } from "sonner";

import { authApi, setTokenProvider } from "@/lib/api";
import { isAuth0Configured } from "@/lib/auth0-client";
import { BYPASS_USER, isAuthBypassed } from "@/lib/auth-bypass";
import { ApiError } from "@/lib/errors";
import { logError } from "@/lib/logger";
import type { User } from "@/types";

/**
 * Session state for the whole app.
 *
 * Auth0's `useAuth0` answers "is there an identity?". It cannot answer "who is
 * the user": email, role and organisation come from `GET /auth/me`, which is
 * also where a first-time identity gets its local user row, organisation and
 * workspace provisioned. This provider owns that second step so no component
 * has to, and so the route guard has a single definition of "signed in".
 *
 * The access token is never stored in localStorage. It is handed to the API
 * layer as a callback, so Auth0 stays the only owner of the token and can
 * renew it behind the scenes.
 */

/**
 * Routes reachable without a session.
 *
 * `/` is the marketing landing page and is deliberately public. It was missing
 * here, so a signed-out visitor was redirected straight to `/login` and the
 * landing page was only ever seen by people already signed in. `/register`
 * belongs here for the same reason: the route exists, but without it the guard
 * treated it as private and made signup unreachable.
 *
 * The match is an exact path comparison, so guarding `/` does not open up
 * anything nested beneath it — the dashboard and its children stay protected.
 */
const PUBLIC_ROUTES = ["/", "/login", "/register", "/callback"];

export interface AuthSession {
  /** Auth0 reports a session and /auth/me has resolved. */
  isAuthenticated: boolean;
  /** True until both Auth0 and /auth/me have settled. Never gate on false. */
  isLoading: boolean;
  user: User | null;
  /**
   * Profile image from the Auth0 identity, if the connection provides one.
   *
   * Deliberately separate from `user`: `/auth/me` is this app's own record and
   * carries no avatar, while `picture` is an Auth0 claim that is often absent
   * (it only appears for connections that supply it, such as a linked social or
   * Gravatar account). Callers must fall back to initials, because a signed-in
   * user with no picture is the common case, not the exception.
   */
  avatarUrl: string | null;
  error: Error | null;
  login: (returnTo?: string) => Promise<void>;
  logout: () => Promise<void>;
  /** The build has no Auth0 env vars, so there is nothing to authenticate with. */
  isMisconfigured: boolean;
}

const AuthSessionContext = createContext<AuthSession | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const isMisconfigured = !isAuth0Configured;

  const {
    user: auth0User,
    isAuthenticated,
    isLoading: isAuth0Loading,
    loginWithRedirect,
    logout,
    getAccessTokenSilently,
  } = useAuth0();

  // The /auth/me result, tagged with the Auth0 identity it belongs to. Tagging
  // is what lets the exposed user and the loading flag be *derived* below
  // instead of reset from an effect: a result for a different `sub` is treated
  // as absent, so signing out or switching accounts cannot leave the previous
  // account's profile on screen for a frame.
  const [profile, setProfile] = useState<{
    sub: string;
    user: User | null;
    error: Error | null;
  } | null>(null);
  const identity = auth0User?.sub ?? null;

  // Adopt the access token into the API layer. Registered unconditionally and
  // torn down on unmount, so a hot reload cannot leave a stale closure holding
  // a token for the session the user has already abandoned. The call is wrapped
  // rather than passed by reference because `getAccessTokenSilently` is
  // overloaded, and the `detailedResponse` overload does not fit the plain
  // `() => Promise<string | undefined>` contract the API layer expects.
  useEffect(() => {
    if (!isAuthenticated) return;
    setTokenProvider(() => getAccessTokenSilently());
    return () => setTokenProvider(null);
  }, [isAuthenticated, getAccessTokenSilently]);

  useEffect(() => {
    if (!isAuthenticated || !identity) return;

    let cancelled = false;

    void (async () => {
      try {
        const me = await authApi.me();
        if (!cancelled) setProfile({ sub: identity, user: me, error: null });
      } catch (err) {
        if (cancelled) return;
        logError("failed to load the current user", err);
        const failure = err instanceof Error ? err : new Error("Could not load your profile.");
        setProfile({ sub: identity, user: null, error: failure });
        // A 403 here is almost always "this identity has no email claim",
        // which is an Auth0 connection setting rather than anything a retry can
        // fix. Naming it is more use than a generic failure toast.
        if (err instanceof ApiError && err.status === 403) {
          toast.error("This account cannot be used", { description: err.message });
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, identity]);

  const hasProfile = isAuthenticated && identity !== null && profile?.sub === identity;
  const isLoadingUser = isAuthenticated && identity !== null && !hasProfile;
  const user = hasProfile && profile ? profile.user : null;
  const error = hasProfile && profile ? profile.error : null;

  // Route guard. Deliberately gated on the settled state: checking while Auth0
  // is still restoring a session is what bounces returning users to /login.
  useEffect(() => {
    if (isAuthBypassed) return;
    if (isMisconfigured || isAuth0Loading || isLoadingUser) return;
    if (PUBLIC_ROUTES.includes(pathname)) return;
    if (isAuthenticated) return;

    const returnTo = `${pathname}${window.location.search}`;
    router.replace(`/login?returnTo=${encodeURIComponent(returnTo)}`);
  }, [isAuthenticated, isAuth0Loading, isLoadingUser, pathname, router, isMisconfigured]);

  const handleLogin = useCallback(
    async (returnTo?: string) => {
      if (isMisconfigured) {
        toast.error("Authentication is not configured", {
          description:
            "Set NEXT_PUBLIC_AUTH0_DOMAIN and NEXT_PUBLIC_AUTH0_CLIENT_ID, then rebuild.",
        });
        return;
      }
      await loginWithRedirect({
        appState: { returnTo: returnTo || `${pathname}${window.location.search}` },
      });
    },
    [loginWithRedirect, pathname, isMisconfigured],
  );

  const handleLogout = useCallback(async () => {
    try {
      // Destroy the Auth0 SSO session too. Logging out of the app while leaving
      // the Auth0 cookie behind means the next person to open this browser is
      // silently signed back in.
      await logout({
        logoutParams: { returnTo: window.location.origin },
      });
    } catch (err) {
      logError("logout failed", err);
      // Never strand someone in a signed-in shell they asked to leave, even if
      // the network call to Auth0 could not complete. There is no state to clear
      // here: the exposed user is derived from `isAuthenticated`, which Auth0
      // has already flipped.
      router.replace("/login");
    }
  }, [logout, router]);

    // A misconfigured build has no SdkProvider above it, so `useAuth0()` returns
    // the SDK's default context, whose `isLoading` is permanently `true`.
    // Forwarding that left every consumer spinning forever — the sign-in page
    // showed its heading and then a loader that never resolved, with no way to
    // reach the configuration error it should have been showing. There is no
    // session to wait for when there is no provider, so report settled
    // immediately and let the consumer render the "not configured" state.
    const sessionLoading = isMisconfigured ? false : isAuth0Loading || isLoadingUser;

    const value = useMemo<AuthSession>(() => {
      // A complete session, so `isLoading`, `user` and `user.role` consumers —
      // including the admin console's role check — all behave as they would for a
      // real administrator. Login and logout are inert because there is no Auth0
      // session to create or destroy.
      if (isAuthBypassed) {
        return {
          isAuthenticated: true,
          isLoading: false,
          user: BYPASS_USER,
          avatarUrl: null,
          error: null,
          login: async () => undefined,
          logout: async () => undefined,
          isMisconfigured: false,
        };
      }

      return {
        isAuthenticated: Boolean(isAuthenticated) && !isMisconfigured,
        isLoading: sessionLoading,
        user: isMisconfigured ? null : user,
        // Read defensively: `user` is typed as Auth0's User, but the claim is
        // only present on connections that supply it.
        avatarUrl:
          !isMisconfigured && typeof auth0User?.picture === "string" && auth0User.picture
            ? auth0User.picture
            : null,
        error: isMisconfigured ? null : error,
        login: handleLogin,
        logout: handleLogout,
        isMisconfigured,
      };
    }, [isAuthenticated, isMisconfigured, sessionLoading, user, auth0User, error, handleLogin, handleLogout]);

  return <AuthSessionContext.Provider value={value}>{children}</AuthSessionContext.Provider>;
}

export function useAuthSession(): AuthSession {
  const ctx = useContext(AuthSessionContext);
  if (!ctx) {
    throw new Error("useAuthSession must be used inside <AuthProvider>");
  }
  return ctx;
}
