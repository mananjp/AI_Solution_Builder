import type { CapacitorConfig } from '@capacitor/cli';

// Hybrid shell: by default the WebView loads the live web app (the PWA build
// served by `next start` / container), so the app keeps its dynamic solution
// routes and live API. Set CAP_SERVER_URL to your deployed origin, or run a
// bundled local export (`NEXT_EXPORT=1 next build`) and point webDir at `out`.
const isProd = process.env.NODE_ENV === 'production';
const serverUrl = process.env.CAP_SERVER_URL;

if (isProd && !serverUrl) {
  throw new Error(
    'CAP_SERVER_URL environment variable is required in production builds to prevent insecure localhost fallback'
  );
}

const config: CapacitorConfig = {
  appId: 'com.futurrizon.aisolutionbuilder',
  appName: 'AI Solution Builder',
  webDir: 'out',
  server: {
    androidScheme: 'https',
    cleartext: !isProd && (serverUrl ? serverUrl.startsWith('http://') : true),
    ...(serverUrl ? { url: serverUrl } : !isProd ? { url: 'http://localhost:3000' } : {}),
  },
  plugins: {
    // Native mobile hardware plugins config (camera scanning for PRDs, push notifications)
  },
};

export default config;
