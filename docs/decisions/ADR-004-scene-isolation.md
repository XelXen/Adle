# ADR-004: Generated scenes run in a per-instance, sandboxed player origin

- **Status:** Accepted
- **Date:** 2026-11-19
- **Applies to:** `@wanimjs/wanim` 0.1.3. Re-validate when the pin changes.

## Context

A lesson's visualization is a Python file, possibly written by a model that has read untrusted
course material. Wanim compiles it to JavaScript and runs it in the page. The integration spike
(PLAN.md §10.2) established the following about the pinned runtime:

1. The compiled code is run with `eval`, inside a hidden same-origin `about:blank` iframe the
   bridge creates. The host page therefore needs `'unsafe-eval'`.
2. Scene source can reach arbitrary JavaScript: RapydScript has a raw-JavaScript literal
   (`v'...'`), and undeclared names resolve to browser globals (`window`, `fetch`, ...).
3. Under `sandbox="allow-scripts"` alone (an opaque origin) the bridge fails: its child frame gets
   a different opaque origin and cannot be scripted.
4. A scene that never yields (`while True:`) blocks its whole renderer process. A new frame on the
   **same** origin is placed in that same blocked process and never starts.
5. Wanim has no pause API, and fetches fonts from a public CDN by default.

So scene code must be treated as arbitrary script, and one bad scene must not be able to take the
lesson, the app, or later scenes down with it.

## Decision

### Where scenes run

- A dedicated document, `adle://<instance>.player/index.html`, loaded in an `<iframe>` inside the
  renderer. `<instance>` is 16 random hex characters, **new for every frame**.
- The iframe has `sandbox="allow-scripts allow-same-origin"`, and the same directive is repeated
  in the document's CSP header, so it holds even if the attribute were missing.
- The player's CSP: `default-src 'none'`; scripts, styles, fonts, images, and connections from
  `'self'` only; `'unsafe-eval'` for scripts; `frame-ancestors adle://app`.
- The Chromium session cancels every request that is not `adle:`, `data:`, `blob:`, `about:`, or
  `devtools:`. There is no network for the renderer or the player, whatever a CSP says.
- All web storage is cleared at startup; a player origin is never reused.

### What that buys

| Property | Mechanism | Test |
|---|---|---|
| No preload bridge in the player | Preload runs in the main frame only | `security.spec.ts` › player frame globals |
| Cannot read or script the app | Different origin (`*.player` vs `app`) | `security.spec.ts` › hostile scene |
| Cannot reach the network | CSP `connect-src 'self'` + session request filter | same |
| Cannot open windows or navigate the app | Sandbox without `allow-popups` / `allow-top-navigation`; `will-navigate` guards | same |
| Cannot call privileged IPC | `isTrustedSender` accepts only the top-level `adle://app` frame | `security-boundaries.test.ts` |
| A stuck scene does not freeze the app | Different site, so a different process | `scene-player.spec.ts` › stuck in a loop |
| A stuck scene does not poison the next | Fresh origin per frame, so a fresh process; the old one is reaped | same |
| Nothing persists between scenes | Fresh origin has empty storage; storage cleared at startup | design |

### The relaxations, and why they are acceptable

- **`'unsafe-eval'`** is required by the runtime. It applies only to player origins, which hold no
  secrets and have no capabilities beyond drawing on a canvas and posting validated messages.
- **`allow-same-origin`** is required for the bridge's child frame. The usual objection to
  combining it with `allow-scripts` is that same-origin content can remove its own sandbox; that
  needs the *embedder* to be same-origin, and here the embedder is `adle://app`. The frame keeps a
  real origin, which also lets the host check `event.origin` exactly instead of accepting `"null"`.
- Electron's own baseline is untouched: `contextIsolation`, `sandbox`, `nodeIntegration: false`,
  `webSecurity`, no `webviewTag`.

### The host protocol

`@adle/event-protocol` is the only channel. Both directions are parsed by hand-written validators:
closed message set, exact keys, bounded sizes, primitive payloads. Scene-originated events are
limited to `passed`, `explored`, `progress`. The host additionally requires the message to come
from its own frame's window and exact origin, and from the current run.

A scene can forge any *valid* message (for example claim `passed`). That is accepted: scene events
are weak evidence by design and never decide mastery on their own.

### Supplying what the runtime lacks

- **Pause/resume:** the player gates `requestAnimationFrame` (`frame-clock.ts`). This relies only
  on the documented fact that Wanim paces frames on it.
- **Liveness:** the host pings once a second while a scene is active; five seconds of silence is a
  failure. The adapter then discards the frame and reports `unresponsive`.
- **Fonts:** local WOFF1 files via `configure_fonts`; nothing is fetched from a CDN.
- **Static policy:** `adle_core.generation.scene_policy` rejects files that are not valid Python,
  import anything else, or reference a name outside the manim allowlist. This is defence in depth
  and a quality gate, not the boundary.

## Alternatives considered

- **Opaque-origin sandbox.** The strictest option; the runtime does not work in it (point 3).
- **One fixed player origin.** Simpler, and what the first version of the spike used. Rejected
  because of point 4 and because storage would persist between scenes.
- **Kill the stuck process from the main process.** Works, but needs privileged process control
  driven by renderer input. A fresh origin achieves the same with no new privileged surface.
- **Replace Wanim's `eval` iframe with our own evaluator.** Would mean building on internals of an
  early-preview library. Rejected.
- **Run scenes in a `<webview>` or a second `BrowserWindow`.** Heavier, and `<webview>` is
  discouraged. An out-of-process iframe already gives process isolation.

## Consequences

- Each player frame costs a renderer process and a runtime boot (measured at 160–240 ms). The lesson
  player keeps one frame alive and replaces it only after a failure.
- Not yet verified in a packaged build; that check belongs to the packaging spike (M8) and is
  listed as BLOCKED in `docs/engineering/PROJECT_STATE.md` until then.
- If a future Wanim release offers a worker-based or opaque-origin-safe runtime, supersede this ADR.
