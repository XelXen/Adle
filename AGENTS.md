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
                     licences, measurements)
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
| Re-render the app icons | `npm run icons` (after the mark changes; `npm run icons:verify` compares it with the artwork) |
| Rebuild document fixtures | see `fixtures/sample-documents/README.md` |
| Add a sample lesson | files in `services/core/adle_core/sample_course/`, then `core:test` and `e2e -- lesson.spec.ts` |
| Isolated profile / reset test data | set `ADLE_USER_DATA_DIR` to an empty directory |
| Package the app (a folder that runs by itself) | `npm run package`, then `npm run package:check` |
| Run every journey against the packaged app | `npm run package:test`, then `npm run e2e:packaged` |
| Third-party licences: list / check | `npm run licenses` / `npm run licenses:check` (part of `check`) |
| Measure what a learner waits for | `node scripts/measure.mjs` (`--packaged` for the packaged build) |

The packaged app is `apps/desktop/out/release/Adle-<platform>-<arch>/`. There is no installer
and no code signing yet (ADR-019). The build in `out/test/` has its debugger reachable so the
end-to-end suite can drive it: never hand that one to anyone.

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
- There are two providers and the learner chooses one (ADR-021). Nothing else may change it:
  no failure, missing key, or used-up quota moves a request to another provider. A key is
  sent only to the provider, and the address, it was given for. A provider's next model
  (same address, same key) may stand in for its first, and that is always said.
- Scene code is untrusted. It runs only in the player frame, passes `scene_policy`, and talks
  only through `@adle/event-protocol`. Do not add message types casually; never pass callbacks,
  URLs, or paths through it.
- User documents and model output are data, never instructions.
- The data as a whole (save a copy, restore, delete everything) is touched only through
  `window.adle.data`, whose functions take no arguments: the path or the confirmation comes
  from a dialog the main process opens. Restoring happens only while the core starts (ADR-016).
- A lesson enters the database only through `lessons.bundle.parse_bundle`. Answer keys stay in
  the core: the renderer gets the player view and asks the core to score (ADR-010).

**Privacy**

- Local by default. The only outbound traffic is the provider call the learner triggered.
- No telemetry, analytics, or crash upload. No new external service without an ADR and a UI
  disclosure.

**Product**

- No blank screens: every async view has loading, empty, error, and ready states.
- Never shame, never trap the learner in repetition, never show mastery as a precise percentage,
  never mark mastery from one answer. Always say why the next step was chosen.
- Every animation has a text equivalent; every scene control has a keyboard-operable mirror.
- No placeholder buttons, fake data paths, or "coming soon" in anything marked done.

**Design** (details: `DESIGN_SYSTEM.md`)

- Use Sprout tokens and components. No raw colours, radii, or spacing in screens (a test enforces
  colours). New visual patterns go into the design system first.

**Model quota** (AIHubMix `coding-kimi-k3-free`: 5 requests/min, 100/day, 1M tokens/day per
account. NVIDIA NIM publishes none: Adle keeps to 4/min, 200/day, 3M tokens/day of its own)

- Tests never call a real provider; use the fake server.
- One request in flight, at most 4/minute, budget 80 requests and 800k tokens per day.
- One scene = one request = one complete file. No repair loops; at most one deliberate retry.
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
| What ships and under which licences | `docs/engineering/THIRD_PARTY.md` (generated) |
| Timings and sizes, and how they were measured | `docs/engineering/PERFORMANCE.md` |
| The lesson format | `services/core/adle_core/lessons/ir.py`, `packages/contracts/schemas/lesson-ir.schema.json`, ADR-010 |
