import type { User } from "@/types";

/**
 * TEMPORARY development escape hatch.
 *
 * Lets routes render as a signed-in user without Auth0, so the UI can be worked
 * on while the tenant is unfinished or the backend is unreachable.
 *
 * Two independent conditions must both hold, so this cannot be switched on by
 * accident in a deployed build:
 *
 *   1. `NODE_ENV !== "production"` — a production bundle takes the `false`
 *      branch at build time and the dead code is dropped.
 *   2. `NEXT_PUBLIC_BYPASS_AUTH === "true"` — off by default even in dev, so
 *      nobody is silently signed in without asking for it.
 *
 * ## This is not just a suppressed route guard
 *
 * The first attempt at this bypassed only `AuthProvider`'s guard and appeared to
 * work — `/dashboard` returned 200 — but every API call then 401'd, because the
 * bypass has no real access token, and `src/lib/api.ts` responds to a 401 by
 * hard-navigating to `/login`. The user was bounced straight back out.
 *
 * So the bypass has to cover that path too. `api.ts` skips the 401 redirect
 * while this is on; without it the flag is useless.
 *
 * ## Turning it off
 *
 * Delete `NEXT_PUBLIC_BYPASS_AUTH=true` from `frontend/.env.local` and restart
 * the dev server. `.env.local` is only read at startup, so a reload is not
 * enough.
 *
 * ## A complete session, not a skipped check
 *
 * A real session object is supplied rather than just letting the guard pass, so
 * every consumer of `isLoading`, `user` and `user.role` — including the admin
 * console's role check — behaves exactly as it would for a signed-in
 * administrator, and nothing renders half-initialised.
 */
export const isAuthBypassed =
  process.env.NODE_ENV !== "production" &&
  process.env.NEXT_PUBLIC_BYPASS_AUTH === "true";

/**
 * A deliberately plausible administrator, so role-gated screens (admin, billing,
 * workspace) are reachable. Narrow `role` here to exercise a restricted account.
 */
export const BYPASS_USER: User = {
  id: "dev-bypass-user",
  email: "dev@localhost",
  full_name: "Dev Bypass",
  role: "admin",
  org_id: "dev-org",
  auth_provider: "bypass",
  email_verified: true,
  is_anonymous: false,
  created_at: new Date(0).toISOString(),
};
