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

## Curriculum and what the learner knows

```mermaid
flowchart LR
  subgraph Pure rules
    G["curriculum.graph<br/>loops, order, layers"]
    T["learner_model.tracing<br/>BKT → state + reason"]
  end
  CS["CurriculumService"] -- "would this write leave a learnable graph?" --> G
  LS["LearnerService.record"] -- "fold one observation" --> T
  CS --> DB[("concepts, edges,<br/>objectives, source refs")]
  LS --> OBS[("learner_observations<br/>append-only")]
  LS --> ST[("learner_concept_states<br/>derived, rebuildable")]
  UI["Renderer"] -- "curriculum.* / learner.*" --> CS
  UI --> LS
```

- A course's concepts form a directed graph. Every write is checked first; a change that would
  close a loop is refused with the loop named. Reading validates again and reports problems.
- What a learner has shown about a concept is a list of observations. The state the interface
  shows (*Not assessed*, *Building understanding*, *Needs more evidence*, *Demonstrated for
  now*) is computed from them, with a sentence for each change. The numeric estimate behind it
  never leaves the core. See ADR-009.

## Taking a lesson

```mermaid
sequenceDiagram
  participant UI as Renderer (LessonScreen)
  participant C as Core
  participant P as Player frame
  UI->>C: lessons.get
  Note over C: lesson through the IR again,<br/>each scene through the policy again
  C-->>UI: player view (no answer keys) + scenes that may run
  UI->>P: load scene (held on its first frame)
  Note over UI: learner presses Start
  UI->>UI: narrator speaks beat 1 … n (the narrator is the clock)
  UI->>P: play / pause with the narration, "next" on a cue
  P-->>UI: explored / passed (weak evidence only)
  UI->>C: lessons.answer (question id + response)
  Note over C: score, store attempt + observation,<br/>fold into the knowledge state
  C-->>UI: outcome, feedback, explanation, what changed
  UI->>C: lessons.save_progress (at each part)
```

- The **Lesson IR** (`adle_core/lessons/ir.py`) is the one definition of a lesson. Whatever wrote
  it, a lesson is stored only through `parse_bundle`.
- The renderer's `LessonController` decides what is on screen; it takes its timing from a
  `Narrator`. Today that is silent captions at reading pace; speech arrives in M5 behind the
  same interface.
- If a scene fails in the player, or the core withholds it, the part shows its description in
  words and the lesson continues.
- Answers are judged in the core. See ADR-010.
- Narration is read by a voice installed on the computer (`lesson/speech.ts`), or shown as text
  at reading pace. Either way the narrator is the lesson's clock. See ADR-013.

## Deciding what next

```mermaid
flowchart LR
  subgraph Pure rules
    M["learner_model.misconceptions<br/>answers + dismissals → hypotheses"]
    P["learner_model.practice<br/>which questions, and why"]
    N["learner_model.next_step<br/>one step, its reason, alternatives"]
  end
  A[("attempts<br/>with what each question could reveal")] --> L
  E[("learner_events<br/>set aside, did not help, finished")] --> L
  S[("states, lessons, progress")] --> L
  L["LearningService<br/>gathers; decides nothing"] --> M --> N
  L --> P
  N --> UI["Renderer: Learn tab,<br/>end of a lesson, end of practice"]
  P --> PR["Renderer: practice screen<br/>(questions without answers)"]
  PR -- "lessons.answer" --> AS["AssessmentService<br/>score, fold, record"] --> A
```

- A hypothesis about a mistake is never stored. It is computed from the answers and from what
  the learner set aside, every time, so it cannot disagree with the record.
- The next step is chosen by rules over states, counts, and dates. It comes with a reason and
  with alternatives, and the learner may ignore it.
- Practice and review answer through the same operation as a lesson's questions. There is one
  scoring path and one place where evidence is recorded. See ADR-014.

## Asking the model

```mermaid
sequenceDiagram
  participant UI as Renderer
  participant G as GenerationService (job)
  participant Q as ModelGateway
  participant P as Provider
  UI->>G: generation.generate_lesson (concept)
  G-->>UI: job (queued)
  loop the lesson, then each scene (fixed, small number)
    G->>Q: complete(request)
    Note over Q: allowed? wait? used up for today?<br/>write the request down, then send
    Q->>P: POST /chat/completions (key in one header)
    P-->>Q: streamed answer
    Q-->>G: text + usage
    Note over G: draft -> Lesson IR (ids, citations,<br/>durations assigned here) -> validate
  end
  G->>G: parse_bundle, store
  UI->>G: jobs.get (polling): progress, then result
```

- The model writes a forgiving draft. The core compiles it into the Lesson IR, so no identifier
  or citation comes from the model.
- The gateway keeps a local count under the provider's limits. The interface shows it as an
  estimate.
- A curriculum proposal works the same way, in one request, and adds nothing until the learner
  has chosen from it. See ADR-012.

## Reading and writing the database

Every unit of work is one of two kinds. One that may write (`Database.session()`) takes
SQLite's write lock when it begins, so writers queue instead of colliding. One that only reads
(`Database.read()`) runs on connections that cannot write; it sees a consistent snapshot and
never waits. The interface's polling and first loads are reads, so a job that is writing never
holds the screen up. See ADR-015.

## The data as a whole: copy, restore, delete

Three actions in Settings → Privacy & data act on everything at once (ADR-016). The page asks
for one with `window.adle.data.*`, which takes no arguments; the main process asks the learner
the question that goes with it in a window of the operating system.

- **Save a copy.** Main opens a save dialog and passes the chosen path to the internal
  operation `data.save_copy`. The core writes one self-contained SQLite file (`.adle`) with
  the online backup, under a temporary name, and renames it when complete.
- **Restore from a copy.** Main opens an open dialog, stops the core, and starts it again with
  `restore_from` in the handshake line. Before opening anything the core checks the file,
  upgrades a working copy of it, keeps the current data in `data/backups/`, and swaps the
  working copy in. The `ready` line says how it went; if the copy was refused, the core is
  running on the data as it was.
- **Delete everything.** Main asks for confirmation, stops the core and holds it stopped,
  removes `data/`, and starts the core on an empty folder. The key and `ui-state.json` stay.

## Data on disk

Everything lives under the profile directory (`ADLE_USER_DATA_DIR`, or the OS default):

| Path | Owner | Contents |
|---|---|---|
| `ui-state.json` | Main | Theme and whether the welcome was seen |
| `credentials.bin` | Main | The provider key, encrypted by the OS |
| `data/adle.db` (+ `-wal`, `-shm`) | Core | Courses, sources, sections, chunks, jobs, settings, curriculum, learner preferences, observations, derived states, lessons with their scenes, lesson progress, and answers |
| `data/sources/<source id>.<ext>` | Core | A copy of each imported original, named by its generated id |
| `data/assets/` | Core | Reserved for generated lesson assets (M5) |
| `data/backups/` | Core | Safety copies: `adle-before-*` made before a migration and `adle-replaced-*` made before a restore (the newest five of each are kept). Each is one file and can itself be restored |
| `logs/core.log` | Main | The core's log output (no document text, answers, or secrets) |

## Code map

| Path | Responsibility |
|---|---|
| `apps/desktop/electron/main` | App lifecycle, protocol, session hardening, core supervision, IPC handlers, key and UI-state storage; `data.ts` for copy, restore, and delete everything |
| `apps/desktop/electron/preload` | The `window.adle` bridge: fixed channels only |
| `apps/desktop/electron/shared` | The IPC contract (channel names and types) |
| `apps/desktop/renderer` | React app: router, screens, core client, `ScenePlayer`, `MathText`; `src/lesson` holds lesson playback (controller, narrators, scene cues, answers) |
| `apps/desktop/player/frame` | Code that runs inside the sandboxed frame: frame clock, scene run, control mirroring |
| `apps/desktop/player/host` | `WanimPlayerAdapter`: the only thing the app knows about the player |
| `apps/desktop/e2e` | Playwright tests against the built app |
| `packages/design-system` | Sprout tokens and components |
| `packages/event-protocol` | Host ↔ player message types, validators, and origin helpers |
| `packages/contracts` | Generated API types and operation table; the Lesson IR as JSON Schema |
| `services/core/adle_core/api` | FastAPI app, auth, error contract, routes |
| `services/core/adle_core/application` | The service container; courses, sources (import and search), background jobs, curriculum, learner, retrieval, lessons, assessment, the sample-course installer, saving and restoring a copy of the data (`data_copy.py`) |
| `services/core/adle_core/lessons` | The Lesson IR, the validating gateway for lesson bundles, and the answer-free view for the player |
| `services/core/adle_core/evaluation` | Deterministic scoring of answers |
| `services/core/adle_core/sample_course` | The sample course: outline, lesson templates, scene files (package data) |
| `services/core/adle_core/curriculum` | Pure rules for the concept graph and for drafting an outline from headings |
| `services/core/adle_core/learner_model` | Pure rules: knowledge tracing, mastery states, review scheduling, preferences |
| `services/core/adle_core/infrastructure` | SQLite engine, ORM models, migrations with backup, asset store |
| `services/core/adle_core/ingestion` | Type detection, parsers, chunking, and the parser worker process |
| `services/core/adle_core/generation` | Provider credentials, scene policy (model client and quota manager arrive in M5) |
| `skills/wanim-scene-authoring` | How to write a scene; tested examples |

Layering rule for the core: `domain` depends on nothing; `application` and `generation` depend on
`domain`; `api` depends on all of them and contains no domain logic; `infrastructure` implements
interfaces that `domain` and `application` define.
