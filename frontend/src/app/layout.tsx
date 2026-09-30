import type { Metadata, Viewport } from "next";
import {
  Geist,
  Noto_Sans_Devanagari,
  Geist_Mono,
} from "next/font/google";

import { I18nProvider } from "@/components/I18nProvider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { Auth0Wrapper } from "@/components/auth/Auth0Wrapper";

import "./globals.css";

/* Every font is exposed as a CSS variable only. globals.css maps the
   Tailwind theme tokens (--font-sans, --font-heading, --font-mono) onto these
   in an `@theme inline` block, so no font class is needed in the markup.

   The design theme is neutral sans, so the UI and headings both resolve to
   Geist and the old display face is gone. The Devanagari face stays for one
   reason only: the सूत्र wordmark is the product's name, and dropping its font
   would render the logo as fallback glyphs on any device without a Devanagari
   system font installed. */
const geist = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const devanagari = Noto_Sans_Devanagari({
  variable: "--font-sanskrit",
  weight: ["400", "700"],
  subsets: ["devanagari"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Sutra OS — Autonomous Architecture",
  description:
    "Turn business logic into production software blueprints, PostgreSQL schemas, and mounted live applications in minutes.",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Sutra OS",
  },
  icons: {
    icon: "/icon.svg",
    apple: "/icon-192.png",
  },
};

export const viewport: Viewport = {
  themeColor: "#FAF8F3",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      // The pre-paint scripts below deliberately write `data-theme`, `dir` and
      // `style.color-scheme` onto this element before React hydrates, which is
      // the only way to avoid a flash of the wrong theme. Those writes are
      // therefore guaranteed to differ from the server-rendered attributes, and
      // React would report a hydration mismatch for the whole document on every
      // load. `suppressHydrationWarning` is the documented opt-out for exactly
      // this case; it applies to this element's attributes only.
      suppressHydrationWarning
      className={`${geist.variable} ${devanagari.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <link rel="manifest" href="/manifest.json" />
        <meta name="mobile-web-app-capable" content="yes" />
        {/* Apply the saved language + RTL direction before hydration to avoid a
            flash of the wrong UI language/layout.
            `async` tells React these are deferred bootstraps rather than
            render-blocking content, which is also what silences its
            "script inside a React component" warning. */}
        <script
          async
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var l=localStorage.getItem('sutra.lang');if(!l)return;var rtl=['ar','ur','fa','he'];var d=rtl.indexOf(l)>-1?'rtl':'ltr';var e=document.documentElement;e.lang=l;e.dir=d;}catch(e){}})();`,
          }}
        />
        {/* Resolve the colour scheme before first paint. globals.css pairs every
            token with light-dark(), so a value is only correct once
            color-scheme is settled -- if this runs after hydration the page
            paints light, then snaps dark, which is the flash this avoids.
            Saved choice wins; otherwise defer to the system. Writing the
            attribute (rather than only the CSS media query) is what lets the
            @custom-variant dark block match, and it means the system can change
            later without a reload. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('sutra.theme');if(t!=='light'&&t!=='dark'){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}document.documentElement.setAttribute('data-theme',t);document.documentElement.style.colorScheme=t;}catch(e){}})();`,
          }}
        />
      </head>
      {/* Colour comes from --bg / --text in globals.css. Setting it here with a
          hardcoded class would win over the token and put the page background
          out of step with every component on it. */}
      <body className="min-h-full flex flex-col">
        {/* `LanguageProvider` used to sit here. It was a second, parallel
            translation system — its own language list and a hardcoded
            `UI_TRANSLATIONS` table of 14 strings — whose `useLanguage` hook had no
            consumers at all. It also wrote `document.documentElement.lang` a
            second time, competing with `I18nProvider` for the same attribute.
            `I18nProvider` is the single source of truth. */}
        <I18nProvider>
          <Auth0Wrapper>
            <TooltipProvider>
              {children}
              <Toaster position="bottom-right" richColors closeButton />
            </TooltipProvider>
          </Auth0Wrapper>
        </I18nProvider>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              if ('serviceWorker' in navigator) {
                window.addEventListener('load', function() {
                  navigator.serviceWorker.register('/sw.js').catch(function(err) {
                    console.warn('[sutra] service worker registration failed', err);
                  });
                });
              }
            `,
          }}
        />
      </body>
    </html>
  );
}
