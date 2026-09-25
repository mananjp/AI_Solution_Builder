/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  async rewrites() {
    // When ENABLE_BACKEND_PROXY is explicitly true or BACKEND_URL is set, proxy to FastAPI backend
    if (process.env.ENABLE_BACKEND_PROXY === "true" || process.env.BACKEND_URL) {
      const backendUrl = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
      return [
        {
          source: "/api/:path*",
          destination: `${backendUrl}/api/:path*`,
        },
      ];
    }
    // In unified container mode (FastAPI + Next.js together), proxy to loopback FastAPI
    const isUnified =
      process.env.CONTAINER_ROLE === "unified" ||
      Boolean(process.env.INTERNAL_API_PORT);
    if (isUnified) {
      return [
        {
          source: "/api/:path*",
          destination: "http://127.0.0.1:8000/api/:path*",
        },
      ];
    }
    // In Next-only fullstack mode, native Next.js Route Handlers serve /api/ requests directly
    return [];
  },
};

export default nextConfig;