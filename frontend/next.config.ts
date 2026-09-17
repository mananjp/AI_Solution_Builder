import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Only use standalone output when self-hosting in Docker; Vercel handles packaging natively.
  ...(process.env.VERCEL ? {} : { output: "standalone" }),
  compress: false, // Prevents memory spikes from internal zlib compression buffers in 512MB RAM
  poweredByHeader: false,
  productionBrowserSourceMaps: false,

  // When deployed to Vercel, proxy API calls to the Render backend URL.
  // When running locally / in-container, proxy to http://127.0.0.1:8000.
  async rewrites() {
    const rawBackend =
      process.env.BACKEND_URL ||
      process.env.NEXT_PUBLIC_API_URL?.replace(/\/api\/v1\/?$/, "") ||
      "http://127.0.0.1:8000";
    const backendUrl = rawBackend.replace(/\/+$/, "");

    return [
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
