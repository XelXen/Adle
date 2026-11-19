import { readFile } from 'node:fs/promises';
import path from 'node:path';

import { protocol } from 'electron';

import {
  ADLE_SCHEME,
  APP_HOST,
  APP_ORIGIN,
  isPlayerHost,
  PLAYER_ORIGIN_CSP_SOURCE,
} from '@adle/event-protocol';

import { paths } from './paths';

/**
 * The `adle://` scheme serves the application from separate origins:
 *
 * - `adle://app`              — the trusted React renderer.
 * - `adle://<instance>.player` — an isolated scene player, which executes
 *                                generated Wanim code and is treated as untrusted.
 *
 * Different hosts are different origins, so a player can never reach the
 * renderer's DOM or the preload bridge. Each kind of origin gets its own
 * Content Security Policy below. See docs/decisions/ADR-004-scene-isolation.md.
 */
export const APP_ENTRY_URL = `${APP_ORIGIN}/index.html`;

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.wasm': 'application/wasm',
  '.txt': 'text/plain; charset=utf-8',
};

/** Renderer policy: no inline or evaluated script, no network, frames only from a player. */
export const APP_CSP = [
  "default-src 'none'",
  "script-src 'self'",
  "style-src 'self'",
  "img-src 'self' data: blob:",
  "font-src 'self'",
  "connect-src 'self'",
  "media-src 'self' blob:",
  `frame-src ${PLAYER_ORIGIN_CSP_SOURCE}`,
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
  "frame-ancestors 'none'",
].join('; ');

/**
 * Player policy. Wanim compiles a scene to JavaScript and evaluates it, so
 * 'unsafe-eval' is unavoidable here; it is confined to player origins, which
 * have no preload bridge and no network.
 *
 * The "sandbox" directive is enforced even if the frame were ever embedded
 * without the attribute. "allow-same-origin" keeps the document on its own
 * adle://<instance>.player origin instead of an opaque one: Wanim evaluates
 * scene code inside a child about:blank frame and must be able to script it,
 * which an opaque origin forbids (verified with Wanim 0.1.3; see ADR-004). A
 * player origin is still a different origin from the renderer, so the
 * same-origin policy keeps it out of the app.
 */
export const PLAYER_CSP = [
  "default-src 'none'",
  "script-src 'self' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self'",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
  `frame-ancestors ${APP_ORIGIN}`,
  'sandbox allow-scripts allow-same-origin',
].join('; ');

const COMMON_HEADERS: Record<string, string> = {
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
  'Cache-Control': 'no-cache',
};

interface StaticSite {
  root: string;
  headers: Record<string, string>;
}

/** Pick the site for a request host, or `null` for an unknown host. Exported for tests. */
export function siteForHost(host: string): 'app' | 'player' | null {
  if (host === APP_HOST) return 'app';
  if (isPlayerHost(host)) return 'player';
  return null;
}

/**
 * Map a request path to a file inside `root`, or `null` if it would escape it.
 * Exported for unit tests.
 */
export function resolveStaticPath(root: string, requestPath: string): string | null {
  let decoded: string;
  try {
    decoded = decodeURIComponent(requestPath);
  } catch {
    return null;
  }
  if (decoded.includes('\0')) return null;
  const relative = decoded.replace(/^\/+/, '') || 'index.html';
  const resolved = path.resolve(root, relative);
  const rootWithSeparator = root.endsWith(path.sep) ? root : root + path.sep;
  if (!resolved.startsWith(rootWithSeparator)) return null;
  return resolved;
}

function notFound(): Response {
  return new Response('Not found', {
    status: 404,
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
}

async function serveStatic(site: StaticSite, requestPath: string): Promise<Response> {
  const filePath = resolveStaticPath(site.root, requestPath);
  if (!filePath) return notFound();
  const contentType = MIME_TYPES[path.extname(filePath).toLowerCase()];
  if (!contentType) return notFound();
  try {
    const body = await readFile(filePath);
    return new Response(new Uint8Array(body), {
      status: 200,
      headers: { ...site.headers, 'Content-Type': contentType },
    });
  } catch {
    return notFound();
  }
}

/** Must run before the app is ready. */
export function registerSchemes(): void {
  protocol.registerSchemesAsPrivileged([
    {
      scheme: ADLE_SCHEME,
      privileges: {
        standard: true,
        secure: true,
        supportFetchAPI: true,
        corsEnabled: true,
        codeCache: true,
      },
    },
  ]);
}

/** Must run after the app is ready. */
export function installProtocolHandler(): void {
  const sites: Record<'app' | 'player', StaticSite> = {
    app: {
      root: paths.rendererDir,
      headers: { ...COMMON_HEADERS, 'Content-Security-Policy': APP_CSP },
    },
    player: {
      root: paths.playerDir,
      headers: { ...COMMON_HEADERS, 'Content-Security-Policy': PLAYER_CSP },
    },
  };

  protocol.handle(ADLE_SCHEME, (request) => {
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      return new Response('Method not allowed', { status: 405 });
    }
    const url = new URL(request.url);
    const siteName = siteForHost(url.host);
    if (!siteName) return notFound();
    return serveStatic(sites[siteName], url.pathname);
  });
}
