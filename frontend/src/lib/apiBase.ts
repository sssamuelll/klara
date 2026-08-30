/** Streaming subpath, relative to the API base. */
export const STREAM_SUBPATH = "/pronunciation/stream";

/**
 * Base of the API. Relative (same-origin) on the web, absolute in the native
 * build, where the WebView origin is https://localhost and there is no proxy.
 *
 * NOTE: the env var is VITE_API_BASE, not VITE_API_BASE_URL — the latter is the
 * Vite dev-proxy target (an origin, no /api/v1) and reusing it breaks `npm run dev`.
 */
export function apiBase(): string {
  const configured = import.meta.env.VITE_API_BASE as string | undefined;
  if (!configured) return "/api/v1";
  return configured.replace(/\/+$/, "");
}

export function deriveWsUrl(
  base: string = apiBase(),
  loc: { protocol: string; host: string } = window.location,
): string {
  if (/^https?:\/\//i.test(base)) {
    return base.replace(/^http/i, "ws") + STREAM_SUBPATH;
  }
  const proto = loc.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${loc.host}${base}${STREAM_SUBPATH}`;
}
