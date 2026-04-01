// src/config.js
// Automatically uses Cloudflare tunnel URL when not on localhost.
// No manual switching needed — works for both laptop and phone.

const LOCALHOST       = 'http://localhost:8000';
const CLOUDFLARE_URL  = 'https://ensure-fifty-difference-prefix.trycloudflare.com';

// If the app is opened from localhost → use localhost backend
// If opened from any other URL (phone via tunnel) → use Cloudflare backend
const BASE_URL = window.location.hostname === 'localhost'
  ? LOCALHOST
  : CLOUDFLARE_URL;

export const TUNNEL_HEADERS = {
  'ngrok-skip-browser-warning': 'true',
  'CF-Access-Client-Id':        'bypass',
};

export function apiFetch(url, options = {}) {
  const isTunnel = !url.startsWith('http://localhost') &&
                   !url.startsWith('http://127.0.0.1');
  return fetch(url, {
    ...options,
    headers: {
      ...(isTunnel ? TUNNEL_HEADERS : {}),
      ...(options.headers || {}),
    },
  });
}

export default BASE_URL;
