import type { CapacitorConfig } from '@capacitor/cli';

// Hybrid shell: by default the WebView loads the live web app (the PWA build
// served by `next start` / container), so the app keeps its dynamic solution
// routes and live API. Set CAP_SERVER_URL to your deployed origin, or run a
// bundled local export (`NEXT_EXPORT=1 next build`) and point webDir at `out`.
const serverUrl = process.env.CAP_SERVER_URL || 'http://localhost:3000';

const config: CapacitorConfig = {
  appId: 'com.futurrizon.aisolutionbuilder',
  appName: 'AI Solution Builder',
  webDir: 'out',
  server: {
    androidScheme: 'https',
    cleartext: true,
    url: serverUrl,
  },
  plugins: {
    // Native mobile hardware plugins config (camera scanning for PRDs, push notifications)
  },
};

export default config;
