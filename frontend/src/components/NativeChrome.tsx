import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { App as CapApp } from "@capacitor/app";
import { SplashScreen } from "@capacitor/splash-screen";
import { StatusBar, Style } from "@capacitor/status-bar";
import { isNative } from "../lib/native";
import { useTheme } from "../lib/preferences";

const PAPER = { light: "#F4EFE6", dark: "#16181C" } as const;

/** Renders nothing: it is the shell's side effects, gathered in one place. */
export default function NativeChrome() {
  const [theme] = useTheme();
  const navigate = useNavigate();
  const navigateRef = useRef(navigate);
  navigateRef.current = navigate;

  useEffect(() => {
    if (!isNative()) return;
    document.documentElement.classList.add("native");
    void SplashScreen.hide().catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!isNative()) return;
    // Two different mechanisms, on purpose. setStyle() controls the icon colour
    // and works everywhere. setBackgroundColor() only bites below Android 15;
    // from 15 on, edge-to-edge makes the bar transparent and the colour comes
    // from the page underneath — which global.css already paints `--paper`.
    // Both follow klara.theme, not prefers-color-scheme: the metas in
    // index.html stop matching as soon as the user picks a theme by hand.
    void StatusBar.setBackgroundColor({ color: PAPER[theme] });
    void StatusBar.setStyle({ style: theme === "dark" ? Style.Dark : Style.Light });
  }, [theme]);

  useEffect(() => {
    if (!isNative()) return;
    // Registered once. Depending on `navigate` would re-register on every route
    // change, and since add and remove are both async that leaves windows with
    // zero handlers (a back press that does nothing) or two (one press that
    // goes back twice).
    const handle = CapApp.addListener("backButton", ({ canGoBack }) => {
      if (canGoBack) navigateRef.current(-1);
      else void CapApp.exitApp();
    });
    return () => {
      void handle.then((h) => h.remove());
    };
  }, []);

  return null;
}
