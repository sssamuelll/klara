import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiBase = env.VITE_API_BASE_URL ?? "http://localhost:8000";
  const usePolling = env.VITE_USE_POLLING === "true";

  return {
    plugins: [
      react(),
      VitePWA({
        registerType: "autoUpdate",
        includeAssets: ["favicon.svg", "apple-touch-icon.png"],
        manifest: {
          name: "Klara",
          short_name: "Klara",
          description: "Aprende alemán leyendo historias",
          lang: "es",
          start_url: "/",
          display: "standalone",
          background_color: "#F4EFE6",
          theme_color: "#F4EFE6",
          icons: [
            { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
            { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
            {
              src: "/icon-maskable-512.png",
              sizes: "512x512",
              type: "image/png",
              purpose: "maskable",
            },
          ],
        },
        workbox: {
          // The Google OAuth callback (/api/v1/auth/google/callback) and every
          // other /api route are real server navigations — the SPA-shell
          // fallback must never swallow them.
          navigateFallbackDenylist: [/^\/api\//],
          runtimeCaching: [
            {
              urlPattern: /^https:\/\/fonts\.googleapis\.com\//,
              handler: "StaleWhileRevalidate",
              options: { cacheName: "google-fonts-css" },
            },
            {
              urlPattern: /^https:\/\/fonts\.gstatic\.com\//,
              handler: "CacheFirst",
              options: {
                cacheName: "google-fonts-webfonts",
                expiration: { maxEntries: 30, maxAgeSeconds: 31536000 },
                cacheableResponse: { statuses: [0, 200] },
              },
            },
          ],
        },
      }),
    ],
    server: {
      host: true,
      port: 5273,
      strictPort: true,
      watch: usePolling ? { usePolling: true, interval: 300 } : undefined,
      proxy: {
        "/api": {
          target: apiBase,
          changeOrigin: true,
          ws: true,
        },
      },
    },
    build: {
      sourcemap: true,
      // pcmWorklet must be a real emitted asset: audioWorklet.addModule(data:) is
      // unreliable cross-engine and CSP-hostile; everything else keeps the default.
      assetsInlineLimit: (filePath) =>
        filePath.endsWith("pcmWorklet.js") ? false : undefined,
    },
  };
});
