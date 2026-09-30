import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";

/**
 * Content Security Policy.
 *
 * The app renders AI-generated content and mounts three inline bootstrap
 * scripts in `app/layout.tsx` (theme, direction, service worker). Those are
 * literal, non-interpolated strings, so they can be allow-listed by hash and the
 * policy stays strict. Without a CSP there is no second layer if an injection
 * path is ever found.
 *
 * `script-src` allows `'unsafe-inline'` because Next.js injects inline bootstrap
 * scripts whose hashes are not stable across builds. That is a real weakening,
 * and the trade is deliberate: the alternative is a nonce threaded through the
 * framework, which `output: "standalone"` plus the inline scripts do not
 * currently support. `strict-dynamic` is absent for the same reason — it would
 * be ignored alongside `'unsafe-inline'`.
 */
function cspDirectives(): string[] {
  const connect = [
    "'self'",
    // The API is same-origin in most deployments (rewrites proxy /api), but a
    // split-host deployment and the Capacitor build talk to it directly.
    "https://*.onrender.com",
    "http://127.0.0.1:*",
    "http://localhost:*",
    "https://*.vercel.app",
  ];
  if (!isDev) {
    // Auth0 needs its own tenant reachable for the redirect round-trip.
    connect.push("https://*.auth0.com");
  }

  return [
    "default-src 'self'",
    `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
    // Shiki injects a <style> per token, and the theme-toggle and skill
    // components set inline styles, so inline style has to be permitted.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob: https:",
    "font-src 'self' data:",
    `connect-src ${connect.join(" ")}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "worker-src 'self' blob:",
    "manifest-src 'self'",
    ...(isDev ? [] : ["upgrade-insecure-requests"]),
  ];
}

const nextConfig: NextConfig = {
  // Only use standalone output when self-hosting in Docker; Vercel handles packaging natively.
  ...(process.env.VERCEL ? {} : { output: "standalone" }),
  compress: false, // Prevents memory spikes from internal zlib compression buffers in 512MB RAM
  poweredByHeader: false,
  productionBrowserSourceMaps: false,

  // The app had no headers at all. These are the baseline set every deployment
  // should carry; `frame-ancestors 'none'` also removes the need for
  // X-Frame-Options, and HSTS is meaningless on plain-http local development.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: cspDirectives().join("; ") },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
          { key: "Permissions-Policy", value: "camera=(), geolocation=(), microphone=(self)" },
          ...(isDev
            ? []
            : [
                {
                  key: "Strict-Transport-Security",
                  value: "max-age=63072000; includeSubDomains; preload",
                },
              ]),
        ],
      },
    ];
  },

  // When deployed to Vercel, proxy API calls to the Render backend URL.
  // When running locally / in-container, proxy to http://127.0.0.1:8000.
  async rewrites() {
    const rawBackend =
      process.env.BACKEND_URL ||
      process.env.NEXT_PUBLIC_API_URL?.replace(/\/api\/v1\/?$/, "") ||
      (process.env.VERCEL
        ? (process.env.NEXT_PUBLIC_RENDER_BACKEND_URL || "https://ai-solution-builder.onrender.com")
        : "http://127.0.0.1:8000");
    const backendUrl = rawBackend
      .replace("ai-solution-builder-app.onrender.com", "ai-solution-builder.onrender.com")
      .replace(/\/+$/, "");

    return [
      {
        source: "/health",
        destination: `${backendUrl}/health`,
      },
      {
        source: "/ready",
        destination: `${backendUrl}/ready`,
      },
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
