import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "dev.sdar.klara",
  appName: "Klara",
  webDir: "dist",
  android: {
    allowMixedContent: false,
    // targetSdk 35+ forces edge-to-edge; without this the WebView sits under
    // the status bar. The safe-area CSS in global.css handles the rest.
    adjustMarginsForEdgeToEdge: "auto",
  },
  plugins: {
    SplashScreen: {
      // Belt and braces: NativeChrome hides it on first render, but if the
      // bundle never boots that effect never runs — and a splash with no exit
      // is indistinguishable from a frozen app.
      launchAutoHide: true,
      launchShowDuration: 3000,
      backgroundColor: "#F4EFE6",
    },
    Keyboard: { resize: "native" },
  },
};

export default config;
