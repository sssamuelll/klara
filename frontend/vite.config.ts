import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiBase = env.VITE_API_BASE_URL ?? "http://localhost:8000";
  const usePolling = env.VITE_USE_POLLING === "true";

  return {
    plugins: [react()],
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
