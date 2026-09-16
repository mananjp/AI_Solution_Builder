import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",

  // When the app and API run in the same container, the browser should
  // call Next.js on port 3000 which proxies backend requests to 127.0.0.1:8000.
  // The build-time env NEXT_PUBLIC_API_URL should be set to "/api/v1".
  async rewrites() {
    return [
      // Proxy Next.js health check requests to FastAPI so the Render
      // blueprint healthCheckPath (/) already covers the backend too.
      {
        source: "/ready",
        destination: "http://127.0.0.1:8000/ready",
      },
      // Route all /api/* traffic to the FastAPI sidecar.
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
