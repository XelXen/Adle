# ADR-003: One `adle://` protocol in development and production; no dev server

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

Electron apps commonly load `http://localhost:5173` in development and files in production. That
gives two security configurations: the development Content Security Policy must allow inline
script and WebSockets for hot reload, and the origin differs from the shipped one. The plan warns
that the Wanim integration must work "with the packaged build, not only the development server".

## Decision

- The app is always served from a custom, privileged, standard scheme: `adle://`.
  - `adle://app` — the renderer.
  - `adle://<instance>.player` — a scene player (ADR-004).
- The main process answers requests by reading built files from `dist/renderer` and `dist/player`,
  refusing any path that escapes its root, and attaching the Content Security Policy for that
  origin as a response header.
- `npm run dev` runs the same build in watch mode and restarts Electron when something is rebuilt.
  There is no Vite dev server and no hot module replacement.
- In the main process, origins of `adle://` URLs are derived with `adleOriginOf()`, never with
  `new URL(x).origin`: Node's URL parser treats custom schemes as non-special and returns `"null"`.

## Consequences

- Development and production share one loading path, one CSP, and one set of origins. The
  end-to-end tests exercise what ships.
- The renderer CSP has no `unsafe-inline` or `unsafe-eval`, in development too.
- Editing UI costs a rebuild and restart (about one second) instead of hot reload. Accepted for
  the fidelity; component work can be iterated with Vitest.
- A response header, not a `<meta>` tag, carries the CSP, so `frame-ancestors` and `sandbox`
  directives are available.
