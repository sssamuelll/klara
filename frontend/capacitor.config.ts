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
    SplashScreen: { launchAutoHide: false, backgroundColor: "#F4EFE6" },
    Keyboard: { resize: "native" },
  },
};

export default config;
