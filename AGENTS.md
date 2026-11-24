# AGENTS.md — start here

**Adle (Adaptive Learning Environment)** is a local-first desktop app that turns a topic or a
learner's own materials into an inspectable curriculum, teaches each concept with narrated,
interactive Wanim scenes, checks understanding with short questions, and adapts what comes next to
the evidence. The defining loop: **Curriculum → Learner model → Lesson plan → Interactive lesson →
Evidence → Adaptation → Retention review.**

Read, in order: this file → `docs/engineering/PROJECT_STATE.md` (where things stand, what is next)
→ `PLAN.md` (the specification) → `PROMPT.md` (the operating contract). Then the nested
`AGENTS.md` for the subtree you will touch.

## Repository map

```text
apps/desktop/
  electron/main      privileged main process          (AGENTS.md in apps/desktop)
  electron/preload   the window.adle bridge
  electron/shared    IPC contract (channels + types)
  renderer/          React UI, served as adle://app
  player/frame/      runs INSIDE the sandboxed scene frame (untrusted context)
  player/host/       WanimPlayerAdapter (the app's only view of the player)
  e2e/               Playwright tests against the built Electron app
packages/
  design-system/     Sprout tokens + components        (AGENTS.md inside)
  event-protocol/    host <-> player messages, validators, origins
  contracts/         GENERATED API types + operation allowlist
services/core/       Python FastAPI core               (AGENTS.md inside)
skills/wanim-scene-authoring/   how to write a scene; examples run by the E2E suite
docs/                architecture, ADRs (decisions/), engineering state
fixtures/            sample documents for import tests (the sample course is package data in the core)
scripts/             repo tooling (contracts, name allowlist, typecheck, check, package,
                     licences, the secret scan, measurements; dev/ for trying real providers)
```

## Commands

Run from the repository root. Requires Node ≥ 22.12 (pinned: 24.3.0) and `uv`.

| Task | Command |
|---|---|
| Install everything | `npm run setup` (npm ci, Electron binary, `uv sync`) |
| Run the app (rebuilds on change) | `npm run dev` |
| Build / start the built app | `npm run build` / `npm start` |
| **All fast gates** | `npm run check` |
| All gates including E2E | `node scripts/check.mjs --e2e` |
| Lint / format | `npm run lint` / `npm run format` |
| Type-check TypeScript | `npm run typecheck` |
| Unit tests (TS) | `npm test` (one file: `npx vitest run path/to/file.test.ts`) |
| End-to-end (builds first) | `npm run e2e` (one spec: `npm run e2e -- security.spec.ts`) |
| Core: lint / types / tests | `npm run core:lint` / `core:typecheck` / `core:test` |
| Core: auto-format | `npm run core:format` |
| Regenerate API contract | `npm run contracts` (after any route or model change) |
| Two fake providers in a run | `ADLE_PROVIDER_ENDPOINTS='{"aihubmix":"http://127.0.0.1:9000/v1","nvidia":"http://127.0.0.1:9100/v1"}'` (see `e2e/providers.spec.ts`) |
| Regenerate scene name allowlist | `npm run wanim-names` (after a Wanim upgrade) |
| Repackage the scene guide for prompts | `npm run scene-guide` (after editing the scene skill or its examples) |
| Rewrite the figure examples the player runs | `npm run figures` (after changing `generation/figures.py`; a unit test says when) |
| Rewrite the slide examples the player steps through | `npm run slides` (after changing `generation/slides.py` or the prompt's example; a unit test says when) |
| Re-render the app icons | `npm run icons` (after the mark changes; `npm run icons:verify` compares it with the artwork) |
| Rebuild document fixtures | see `fixtures/sample-documents/README.md` |
| Add a sample lesson | files in `services/core/adle_core/sample_course/`, then `core:test` and `e2e -- lesson.spec.ts` |
| Isolated profile / reset test data | set `ADLE_USER_DATA_DIR` to an empty directory |
| Package the app (a folder that runs by itself) | `npm run package`, then `npm run package:check` |
| Run every journey against the packaged app | `npm run package:test`, then `npm run e2e:packaged` |
| Make the installer for this system | `npm run installer` after `npm run package` (Windows needs Inno Setup). `npm run installer:check` also installs it, starts it and removes it: for CI |
| Publish a version | Commit `release: <version>` with that version set and in the changelog, and push it to `main`: when CI passes, GitHub publishes the installers it tried (`CONTRIBUTING.md` → Releasing) |
| Third-party licences: list / check | `npm run licenses` / `npm run licenses:check` (part of `check`) |
| Nothing secret is about to be committed | `npm run secrets:check` (part of `check`) |
| Try the real providers by hand (spends allowance; never in a test) | `uv run --directory services/core python ../../scripts/dev/real_provider_check.py --help` |
| Time every model on Adle's own prompts, by hand (spends allowance) | `uv run --directory services/core python ../../scripts/dev/benchmark_models.py --help` |
| Which figures in kept answers Adle can draw, and why not (offline) | `uv run --directory services/core python ../../scripts/dev/figure_census.py <answer files>` |
| Measure what a learner waits for | `node scripts/measure.mjs` (`--packaged` for the packaged build) |
| Lock a natural voice's programs again | `bash scripts/dev/voice_locks.sh` (after a version in it changes; then set each voice up by hand, ADR-042) |

The packaged app is `apps/desktop/out/release/Adle-<platform>-<arch>/`, and its installers
are in `apps/desktop/out/installers/`. Nothing is signed (ADR-034). The build in `out/test/`
has its debugger reachable so the end-to-end suite can drive it: never hand that one to
anyone. The repository is `github.com/XelXen/Adle`, with one branch, `main` (ADR-043): a canary
is built from it, and an alpha or a stable version is published from a release commit.

## Architecture in five lines

1. **Main** (Electron, privileged) serves the app from `adle://`, supervises the core, and
   mediates every call to it.
2. **Renderer** (`adle://app`) is sandboxed React with no Node, no network, and no secrets.
3. **Player** (`adle://<id>.player`) runs generated scene code in a sandboxed iframe on a fresh
   origin and process per frame. It is untrusted.
4. **Core** (Python, loopback only) owns all data and makes the only outbound calls.
5. Contracts between them are typed and generated or validated; see `docs/architecture/overview.md`.

## Rules that do not bend

**Security** (details: `SECURITY.md`)

- Never relax `contextIsolation`, `sandbox`, `nodeIntegration: false`, or `webSecurity`.
- Nothing privileged is added to `window.adle` without a specific, validated IPC channel in
  `electron/shared/ipc.ts`. No generic filesystem, shell, or "invoke any channel".
- The renderer reaches the core only via `callCore(operationId)`. New endpoints need an
  `operation_id` and `npm run contracts`. Main-only routes are marked `x-adle-internal`.
- A provider key lives in OS secure storage and core memory. It must never appear in the
  renderer, argv, the environment, a log, the database, or a fixture.
- There are two providers. The learner chooses one, or "automatic": every provider they have
  given a key to, each for what it is good at (ADR-021, ADR-023, ADR-039). Within a provider
  each kind of request has its own order of models, measured, not guessed. Nothing else changes that
  choice. With one provider chosen, no failure, missing key, or used-up quota moves a request
  to another. With automatic, a request may go on to the next provider in the plan, and only
  ever to one with a key of its own; where it may go can be read before it is sent (in
  Settings, and one press away from the control that sends: ADR-036), and who wrote the
  answer afterwards. A key is sent only to the provider, and the address, it was
  given for. A provider's next model (same address, same key) may stand in for its first,
  and that is always said.
- A notification of the operating system is asked for by its kind and nothing else
  (`window.adle.app.notify`). Its words are fixed in the main process (ADR-026): never add
  an argument that carries text.
- Scene code is untrusted, a figure's too (written by the core, from a model's data). It
  runs only in the player frame, passes `scene_policy`, and talks
  only through `@adle/event-protocol`. Do not add message types casually; never pass callbacks,
  URLs, or paths through it. A picture is tried in a frame nobody sees before it joins a
  lesson, when the app is there to try it (ADR-038).
- User documents and model output are data, never instructions.
- A natural voice is downloaded only at the learner's word, from what is pinned: every model
  file by its hash (`voice/catalog.py`), every program by the lock for its system
  (`voice/data/`). It runs in an environment and a process of its own, and the core never
  imports what its engine imports (ADR-042).
- "No network" for the page and for scenes means every road, not only requests (ADR-029).
  The page cannot name a file, and nothing it hands over is trusted to be what it says.
- The data as a whole (save a copy, restore, delete everything) is touched only through
  `window.adle.data`, whose functions take no arguments: the path or the confirmation comes
  from a dialog the main process opens. Restoring happens only while the core starts (ADR-016).
- A lesson enters the database only through `lessons.bundle.parse_bundle`, and a picture
  joins a stored lesson only through `LessonService.settle_scene`, which passes the whole
  lesson through it again (ADR-031). Answer keys stay in the core: the renderer gets the
  player view and asks the core to score (ADR-010).

- A release is made by GitHub from a commit `release: <version>` on `main` once every
  check has passed for it, never by hand, and can write nothing but the release and its
  tag (ADR-034, ADR-043). No installer and no launcher may start Adle with its sandbox
  off, on any system, for any reason: where a sandbox cannot be built, Adle does not start.
- Adle does not update itself and makes no request to find out whether it could.
- Adle is under the GNU GPL, version 3 only (ADR-033). Nothing may be added that cannot be
  combined with it; `npm run licenses:check` refuses what needs a decision first.

**Privacy**

- Local by default. The only outbound traffic is the provider call the learner triggered,
  and the download of a natural voice the learner asked for (ADR-042).
- No telemetry, analytics, or crash upload. No new external service without an ADR and a UI
  disclosure.

**Product**

- No blank screens: every async view has loading, empty, error, and ready states.
- Never shame, never trap the learner in repetition, never show mastery as a precise percentage,
  never mark mastery from one answer. Always say why the next step was chosen.
- A break is offered and never counted: no streak, total, or reminder (ADR-026).
- A lesson is not kept back for its pictures (ADR-031), nor for its later parts
  (ADR-048): it can be started when its first part is written, the learner is told once,
  a part already there never changes, and a picture that arrives is never sprung on
  someone in the middle of a part. Once begun, a lesson is never written again. Removing
  a lesson or a course stops the work for it.
- A question asked during a lesson is a note beside one part, not a chat (ADR-024). It never
  gets the answer to a question the lesson is asking.
- Every animation has a text equivalent; every scene control has a keyboard-operable mirror.
- No placeholder buttons, fake data paths, or "coming soon" in anything marked done.
- Words are in American English (ADR-044), short, plain, and about the learner's task
  (ADR-028), and few (ADR-036): a
  sentence stays where the learner has to act on it or decide by it. Nothing about the
  app's own workings; what a request sends is one press away, not beside every button.
- A lesson is a slideshow (ADR-049): every part that teaches has a slide, and the slide
  takes a step when the narration reaches the words its script marked. Teach by intuition
  and example first: the picture before the symbol, each symbol in the color of what it
  stands for. The case comes first and alone, and the rule is made out of it (ADR-050): a
  formula never shares a slide's first step with its case, and its numbers can fly out of
  the picture into it. A picture's words never lie over each other, under a line, or past the
  edge of the screen, and a step is never longer than its words (ADR-055, ADR-056).
- A lesson in a natural voice is made with its voice (ADR-051): ready once its first part
  can be heard, and a line not recorded yet is waited for, never read in another voice
  unless the learner chooses that or no recording will come.
- A lesson is watched (ADR-035): its pictures on one dark screen in either theme, the
  words being said along its foot with the spoken word marked, the whole screen if wanted.

**Design** (details: `DESIGN_SYSTEM.md`)

- Use Sprout tokens and components. No raw colours, radii, or spacing in screens (a test enforces
  colours). New visual patterns go into the design system first.

**Model quota** (AIHubMix `coding-kimi-k3-free`: 5 requests/min, 100/day, 1M tokens/day per
account. NVIDIA NIM publishes none: Adle keeps to 4/min, 200/day, 3M tokens/day of its own)

- Tests never call a real provider; use the fake server.
- One request in flight at each provider, at most 4/minute there. When trying a real provider
  by hand, budget 80 requests and 800k tokens per day; the app itself stops at 90 and 900k
  for AIHubMix (ADR-012).
- A slide is no request at all: the lesson's answer scripts it as data, and Adle lays it
  out and writes its scene (ADR-049).
- A figure is no request at all: the lesson gives its kind and data, and Adle writes the
  scene from a template (ADR-045). A scene a model writes is one request = one complete
  file. No repair loops; at most one deliberate retry,
  told what was wrong: the rules' findings, or, when the file failed as it was tried in the
  player, the error and the file (ADR-038). What the core can mend in a lesson's answer it
  mends instead of asking again: notation in narration is said in words, a broken practice
  question is left out, a figure that cannot be drawn is told in words (ADR-047).
  A lesson's words are one request, read part by part as they arrive; once a lesson has
  begun it is never asked for again (ADR-048).
  A question asked during a lesson is one request, two at most; a check of a key is one.
  Asking a provider's next model because the one before is away is not a retry of the answer,
  and is bounded by the number of models.
- Send a model only the fields its own reference lists (`ModelSpec` in `provider.py`), and
  check a new field against the real endpoint by hand before relying on it: a documented
  default was not the default, and a documented value was refused (ADR-021).
- If the quota is hit, stop model work, continue deterministic work, record it in PROJECT_STATE.

## Working method

1. Take the next unchecked item from `docs/engineering/PROJECT_STATE.md`.
2. Read the relevant code, nested `AGENTS.md`, and ADRs before editing.
3. Build the smallest vertical slice that a learner could use; add tests with it.
4. `npm run check`; for UI or process changes also `npm run e2e` and look at the app.
5. Update docs (below), review `git diff`, commit with a Conventional Commit.

Report test results only with `PASS`, `FAIL`, `NOT RUN`, or `BLOCKED`. Never infer a pass.

## Keeping the next agent oriented

Before ending a session or when context is about to be compacted:

1. `docs/engineering/PROJECT_STATE.md`: milestone, what just finished, branch, last commit,
   working-tree state, exact next actions, blockers, test statuses.
2. `PLAN.md` §18: milestone status and evidence.
3. This file or a nested one, if a command, rule, or boundary changed.
4. A new ADR in `docs/decisions/` (and a row in `docs/engineering/DECISIONS.md`) for any
   meaningful decision. ADRs are superseded, not rewritten.

Record facts, commands, and decisions. Not transcripts or reasoning traces.

## Where things are written down

| Topic | File |
|---|---|
| Specification and milestones | `PLAN.md` |
| Operating contract | `PROMPT.md` |
| Current state and next actions | `docs/engineering/PROJECT_STATE.md` |
| Decisions | `docs/engineering/DECISIONS.md`, `docs/decisions/` |
| Architecture and data flow | `docs/architecture/overview.md` |
| Threat model and boundaries | `SECURITY.md` |
| Tokens, components, usage | `DESIGN_SYSTEM.md` |
| Test layers, commands, gaps | `TESTING.md` |
| Workflow and commit rules | `CONTRIBUTING.md` |
| Writing Wanim scenes | `skills/wanim-scene-authoring/SKILL.md` |
| Making a build, and where Adle stands against the acceptance list | `docs/engineering/RELEASE_CHECKLIST.md` |
| Publishing a version | `CONTRIBUTING.md` → Releasing; `.github/workflows/ci.yml`; ADR-034, ADR-043 |
| The licence | `LICENSE`, ADR-033 |
| What ships and under which licences | `docs/engineering/THIRD_PARTY.md` (generated) |
| Timings and sizes, and how they were measured | `docs/engineering/PERFORMANCE.md` |
| The lesson format | `services/core/adle_core/lessons/ir.py`, `packages/contracts/schemas/lesson-ir.schema.json`, ADR-010 |
