import type { CapacitorConfig } from '@capacitor/cli';

// Hybrid shell: by default the WebView loads the live web app (the PWA build
// served by `next start` / container or deployed origin), so the app keeps
// its full dynamic solution routes, live API, SSE chat streaming, and real-time sandbox.
// Set CAP_SERVER_URL to custom origin (e.g., http://192.168.1.50:3000 or http://10.0.2.2:3000),
// or set CAP_LOCAL_ASSETS=1 to serve pre-exported bundled assets from `out`.
const isProd = process.env.NODE_ENV === 'production';
const serverUrl = process.env.CAP_SERVER_URL;
const useLocalAssets = process.env.CAP_LOCAL_ASSETS === '1';

// Default to localhost:3000 (paired with adb reverse for USB physical devices / emulators)
// or override via CAP_SERVER_URL (e.g. deployed cloud webapp origin)
const targetUrl = serverUrl
  ? serverUrl
  : useLocalAssets
  ? undefined
  : isProd
  ? (process.env.NEXT_PUBLIC_APP_URL || 'https://ai-solution-builder.onrender.com')
  : 'http://localhost:3000';

const config: CapacitorConfig = {
  appId: 'com.futurrizon.aisolutionbuilder',
  appName: 'AI Solution Builder',
  webDir: 'out',
  server: {
    androidScheme: 'https',
    cleartext: true,
    ...(targetUrl ? { url: targetUrl } : {}),
  },
  plugins: {
    // Native mobile hardware plugins config (camera scanning for PRDs, push notifications)
  },
};

export default config;
