# Architecture overview

Adle is a modular monolith in four operating-system processes. This document describes what
exists today; milestones not yet built are listed in `PLAN.md` §16 and
`docs/engineering/PROJECT_STATE.md`.

## Processes and trust

```mermaid
flowchart LR
  subgraph Electron
    Main["Main process<br/>(Node, privileged)"]
    Renderer["Renderer: adle://app<br/>(React, sandboxed)"]
    Player["Player: adle://&lt;id&gt;.player<br/>(Wanim, sandboxed iframe,<br/>own process)"]
  end
  Core["Python core<br/>(FastAPI on 127.0.0.1)"]
  Provider[("AI provider<br/>(only on request)")]

  Renderer -- "window.adle (typed IPC)" --> Main
  Main -- "HTTP + launch token" --> Core
  Renderer -- "postMessage<br/>(validated protocol)" --> Player
  Core -. "HTTPS, user-configured" .-> Provider
```

| Process | Trust | May | May not |
|---|---|---|---|
| **Main** (`apps/desktop/electron/main`) | Trusted | Spawn the core, hold the token, read/write OS secure storage, serve app files | Execute scene code, hold learner data |
| **Renderer** (`apps/desktop/renderer`) | Trusted code, hostile-input-facing | Render UI, call allowlisted core operations | Use Node, the network, the filesystem, or see the provider key |
| **Player** (`apps/desktop/player/frame`) | **Untrusted** (runs generated code) | Draw on a canvas, post validated messages | Anything else |
| **Core** (`services/core`) | Trusted | Own the database and files, call the provider | Listen beyond loopback, persist the provider key |

## How a request travels

```mermaid
sequenceDiagram
  participant R as Renderer
  participant P as Preload bridge
  participant M as Main
  participant C as Core
  R->>P: adle.core.invoke("provider.status")
  P->>M: ipc invoke (fixed channel)
  M->>M: sender is top-level adle://app?<br/>operation in generated table, not internal?<br/>parameters well-formed and bounded?
  M->>C: GET /v1/provider (Authorization: Bearer token)
  C->>C: Pydantic validation
  C-->>M: 200 JSON or {error:{code,message}}
  M-->>R: { ok: true, data } or { ok: false, error }
```

The operation table and the TypeScript types come from the core's OpenAPI document
(`npm run contracts`, ADR-005).

## Startup

1. Main registers the `adle` scheme, applies the saved theme, locks the session down (no network,
   no permissions, storage cleared), and opens the window on `adle://app/index.html`.
2. The renderer reads app info and UI state through the bridge and shows the welcome screen or the
   library. It is usable immediately.
3. In parallel, main starts the core (ADR-002). On `ready` it pushes the stored provider key to the
   core. Status changes are broadcast to the renderer.
4. On quit, main closes the core's stdin, waits for it to exit, then quits.

## Playing a scene

```mermaid
sequenceDiagram
  participant S as ScenePlayer (React)
  participant A as WanimPlayerAdapter
  participant F as Player frame
  participant W as Wanim runtime
  S->>A: load({ source, theme })
  A->>F: create iframe on a fresh origin
  F->>W: install frame clock, load runtime, local fonts
  F-->>A: ready
  A->>F: load (runId, source, theme)
  F->>W: runPythonOnCanvas(...)
  F-->>A: loaded, first-frame, state, controls
  A-->>S: status "interactive", controls
  S->>A: setControl("weight", 1.8)
  A->>F: set-control
  F-->>A: controls, scene-event "explored"
  loop every second while active
    A->>F: ping
    F-->>A: pong
  end
  Note over A,F: error, timeout, or no pong for 5 s<br/>→ discard frame, emit failure,<br/>ScenePlayer shows the text fallback
```

See ADR-004 for why the frame is arranged this way and `skills/wanim-scene-authoring/` for what a
scene may contain.

## Importing course materials

```mermaid
sequenceDiagram
  participant R as Renderer
  participant M as Main
  participant C as Core (API)
  participant J as Job worker thread
  participant W as Parser worker process
  R->>M: sources.importWithPicker(courseId)<br/>or importDropped(courseId, files)
  M->>M: OS file dialog, or paths of the dropped files<br/>validate: absolute, bounded, at most 50
  M->>C: sources.import_paths (internal)
  C-->>R: job (queued)
  loop each file
    J->>J: detect type from content, check limits, hash
    J->>W: JSON request over stdin
    W-->>J: JSON document (sections, warnings) or error code
    J->>J: validate reply, chunk, store copy + rows<br/>(FTS index updated by triggers)
  end
  R->>C: jobs.get (polled)
  C-->>R: progress, then per-file outcome
```

Text search (`sources.search`) reads the FTS5 index and returns each passage with its source,
page or heading path, and highlighted segments. See ADR-007.

## Data on disk

Everything lives under the profile directory (`ADLE_USER_DATA_DIR`, or the OS default):

| Path | Owner | Contents |
|---|---|---|
| `ui-state.json` | Main | Theme and whether the welcome was seen |
| `credentials.bin` | Main | The provider key, encrypted by the OS |
| `data/adle.db` (+ `-wal`, `-shm`) | Core | Courses, sources, sections, chunks, jobs, settings |
| `data/sources/<source id>.<ext>` | Core | A copy of each imported original, named by its generated id |
| `data/assets/` | Core | Reserved for generated lesson assets (M5) |
| `data/backups/` | Core | Automatic database copies made before a migration (five kept) |
| `logs/core.log` | Main | The core's log output (no document text, answers, or secrets) |

## Code map

| Path | Responsibility |
|---|---|
| `apps/desktop/electron/main` | App lifecycle, protocol, session hardening, core supervision, IPC handlers, key and UI-state storage |
| `apps/desktop/electron/preload` | The `window.adle` bridge: fixed channels only |
| `apps/desktop/electron/shared` | The IPC contract (channel names and types) |
| `apps/desktop/renderer` | React app: router, screens, core client, `ScenePlayer` |
| `apps/desktop/player/frame` | Code that runs inside the sandboxed frame: frame clock, scene run, control mirroring |
| `apps/desktop/player/host` | `WanimPlayerAdapter`: the only thing the app knows about the player |
| `apps/desktop/e2e` | Playwright tests against the built app |
| `packages/design-system` | Sprout tokens and components |
| `packages/event-protocol` | Host ↔ player message types, validators, and origin helpers |
| `packages/contracts` | Generated API types and operation table |
| `services/core/adle_core/api` | FastAPI app, auth, error contract, routes |
| `services/core/adle_core/application` | The service container; courses, sources (import and search), background jobs |
| `services/core/adle_core/infrastructure` | SQLite engine, ORM models, migrations with backup, asset store |
| `services/core/adle_core/ingestion` | Type detection, parsers, chunking, and the parser worker process |
| `services/core/adle_core/generation` | Provider credentials, scene policy (model client and quota manager arrive in M5) |
| `skills/wanim-scene-authoring` | How to write a scene; tested examples |

Layering rule for the core: `domain` depends on nothing; `application` and `generation` depend on
`domain`; `api` depends on all of them and contains no domain logic; `infrastructure` implements
interfaces that `domain` and `application` define.
