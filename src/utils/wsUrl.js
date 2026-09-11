/**
 * Robust WebSocket URL Resolver
 * -------------------------------------------------------------
 * Safely handles:
 * - https:// -> wss:// conversion
 * - http:// -> ws:// conversion
 * - Missing endpoint routes (/ws/live or /ws/telemetry)
 * - Trailing slashes
 * - Localhost development fallback
 */
export function getWebSocketUrl(endpoint = '/ws/live') {
  const envUrl =
    (typeof import.meta !== 'undefined' &&
      (import.meta.env?.VITE_WS_URL ||
        import.meta.env?.VITE_WS_BASE_URL ||
        import.meta.env?.VITE_API_BASE_URL)) ||
    '';

  const defaultRoute = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;

  if (envUrl) {
    let clean = envUrl.trim();

    // Protocol normalizations
    if (clean.startsWith('https://')) {
      clean = 'wss://' + clean.slice(8);
    } else if (clean.startsWith('http://')) {
      clean = 'ws://' + clean.slice(7);
    } else if (!clean.startsWith('ws://') && !clean.startsWith('wss://')) {
      clean = 'wss://' + clean;
    }

    // Strip trailing slashes
    clean = clean.replace(/\/+$/, '');

    // If already contains a valid WebSocket endpoint, return it
    if (clean.endsWith('/ws/live') || clean.endsWith('/ws/telemetry')) {
      return clean;
    }

    return `${clean}${defaultRoute}`;
  }

  // Automatic browser-side fallback if hosted on same domain / reverse proxy
  if (typeof window !== 'undefined' && window.location && window.location.hostname) {
    const host = window.location.hostname;
    if (host !== 'localhost' && host !== '127.0.0.1' && !host.includes('vercel.app') && !host.includes('netlify.app')) {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${proto}//${window.location.host}${defaultRoute}`;
    }
  }

  // Local development default
  return `ws://localhost:8000${defaultRoute}`;
}
