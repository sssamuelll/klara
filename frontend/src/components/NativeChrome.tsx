import { useEffect } from "react";
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

  useEffect(() => {
    if (!isNative()) return;
    document.documentElement.classList.add("native");
    void SplashScreen.hide();
  }, []);

  useEffect(() => {
    if (!isNative()) return;
    // index.html's theme-color metas follow prefers-color-scheme, which stops
    // matching once the user picks a theme by hand. The bar follows the app's
    // choice (klara.theme), not the system's.
    void StatusBar.setBackgroundColor({ color: PAPER[theme] });
    void StatusBar.setStyle({ style: theme === "dark" ? Style.Dark : Style.Light });
  }, [theme]);

  useEffect(() => {
    if (!isNative()) return;
    const handle = CapApp.addListener("backButton", ({ canGoBack }) => {
      if (canGoBack) navigate(-1);
      else void CapApp.exitApp();
    });
    return () => {
      void handle.then((h) => h.remove());
    };
  }, [navigate]);

  return null;
}
