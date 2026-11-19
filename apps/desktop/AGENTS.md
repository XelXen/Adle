# apps/desktop — Electron shell, renderer, and scene player

Read the root `AGENTS.md` first. This file adds the rules specific to this subtree.

## Four contexts, four sets of rules

| Directory | Runs in | May import | Must not |
|---|---|---|---|
| `electron/main` | Node, privileged | `electron`, `node:*`, `@adle/contracts`, `@adle/event-protocol`, `electron/shared` | Execute or evaluate scene code; log secrets |
| `electron/preload` | Sandboxed preload | `electron` (`contextBridge`, `ipcRenderer`), `electron/shared` | Expose `ipcRenderer`, Node APIs, or a generic "invoke" |
| `renderer` | Browser, sandboxed | React, `@adle/*`, **types** from `electron/shared`, `player/host` | Import `electron`, `node:*`, `electron/main`; use `fetch` or web storage |
| `player/frame` | Sandboxed iframe, **untrusted** | `@adle/event-protocol`, `@wanimjs/wanim` | Trust anything from the scene; talk to anything but its parent |

ESLint enforces the import rules (`no-restricted-imports`, `no-restricted-globals`).

## Adding a capability to the bridge

1. Add a channel and types to `electron/shared/ipc.ts` (the complete list of what the renderer can
   ask for).
2. Handle it in `electron/main/ipc.ts` through the local `handle()` helper, which rejects any
   sender that is not the top-level `adle://app` frame. Validate every argument as untrusted.
3. Expose a narrowly typed function in `electron/preload/index.ts`.
4. Add a unit test for the validation and an E2E assertion to
   `e2e/security.spec.ts` (the exact bridge surface is asserted there).

Prefer a core operation (`callCore`) over a new IPC channel whenever the work belongs to the core.

## File paths

Renderer script must never be able to name a file. A path may enter the app in two ways only,
both in `electron/main/ipc.ts` (`registerImportHandlers`):

- the operating system's file dialog, opened by the main process;
- files the learner dropped, turned into paths by the preload with `webUtils.getPathForFile`
  (a `File` constructed by script has no path and is rejected).

Paths are validated by `parseImportPaths` (`electron/main/imports.ts`) and handed to an
**internal** core operation. Do not add an IPC channel or a public core operation that takes a
path, a URL, or a directory from the renderer.

## URLs and origins

- Never use `new URL(x).origin` for `adle://` URLs in main-process code: Node reports `"null"` for
  custom schemes. Use `adleOriginOf()` from `@adle/event-protocol`.
- The Content Security Policies live in `electron/main/protocol.ts` and are asserted in
  `security-boundaries.test.ts`. Do not add `unsafe-inline` or `unsafe-eval` to the app policy.
- Inline `style` props are fine (React sets them through the CSSOM); HTML strings with `style`
  attributes are not.

## The scene player

- The rest of the app uses `ScenePlayer` (React) or `WanimPlayerAdapter`. Nothing else may touch
  the iframe or import Wanim.
- A change to messages between host and frame is a change to `packages/event-protocol`: update
  both validators, both sides, and the tests in one commit.
- Any behaviour of Wanim you rely on must be written into
  `skills/wanim-scene-authoring/reference.md` as Verified, with a test.

## Build and run

- `scripts/build.mjs` bundles main and preload with esbuild (CommonJS, `electron` external) and
  builds the renderer and player with Vite. Output goes to `dist/` (not committed).
- There is no dev server (ADR-003). `npm run dev` rebuilds and restarts Electron.
- `ADLE_USER_DATA_DIR=<dir>` runs against an isolated profile. Tests always set it.

## Tests

- Unit tests sit next to the code as `*.test.ts(x)`. Main-process tests mock `electron`.
- `e2e/` drives the built app. Use the `adle` or `profileDir` fixture from `e2e/support/app.ts`;
  never launch against the default profile. `mountRawPlayer` tests the frame at the protocol level.
- Set a theme with `launchApp(dir, { theme })`, not media emulation: it exercises the real path.
- `getByRole(role, { name })` matches substrings. Add `exact: true` for short names such as
  navigation items; a card on the same screen may contain the same word.
- Never drive a native dialog. Replace `dialog.showOpenDialog` in the main process with
  `app.evaluate` (see `course-materials.spec.ts`).
