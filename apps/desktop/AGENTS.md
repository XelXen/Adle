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
- `assets/brand/` holds the logo artwork and its vector form; `assets/icons/` is rendered from
  it by `npm run icons` and committed. The window reads its icon from `assets/icons/` at run
  time (`paths.windowIcon`), so packaging must ship that folder (M8).

## Tests

- Unit tests sit next to the code as `*.test.ts(x)`. Main-process tests mock `electron`.
- `e2e/` drives the built app. Use the `adle` or `profileDir` fixture from `e2e/support/app.ts`;
  never launch against the default profile. `mountRawPlayer` tests the frame at the protocol level.
- Set a theme with `launchApp(dir, { theme })`, not media emulation: it exercises the real path.
- `getByRole(role, { name })` matches substrings. Add `exact: true` for short names such as
  navigation items; a card on the same screen may contain the same word.
- Never drive a native dialog. Replace `dialog.showOpenDialog` in the main process with
  `app.evaluate` (`chooseInFileDialog` in `e2e/support/courses.ts`, which also has the shared
  steps for creating a course, importing, running axe, and saving a screenshot).
- `getByLabel` also matches `aria-label`s that contain the text ("Objective 1" matches "Remove
  objective 1"). Ask for the role: `getByRole('textbox', { name: 'Objective 1' })`.
- Never call `show()` on the app window from a test (ADR-008).

## Lessons

- `renderer/src/lesson/` is plain TypeScript with unit tests and no React: `LessonController`
  (what is on screen), `Narrator` engines, `SceneCues` (narration to scene), `answers`.
  `screens/lesson/` only draws what they say.
- **The narrator is the clock.** Do not add timers to the controller or the screen; a new way of
  reading a lesson is a new `Narrator`.
- A narrator calls `onWord` only if it really knows the position. Never fake word highlighting.
- The renderer has no answer keys. Anything that needs one (what was right, why) comes back from
  `lessons.answer`. Do not add a field to the player view to "save a round trip".
- Lesson text is shown with `MathText`, never `dangerouslySetInnerHTML`.
- A segment with a scene must render something useful in three cases: the scene runs, the scene
  fails in the player (`ScenePlayer` shows the fallback), and the core withheld the scene
  (no artifact for the reference).
- Assets are files. Both Vite configs set `assetsInlineLimit: 0`; a `data:` URI would be
  refused by the Content Security Policy.
- React's lint rules forbid writing to a ref passed in as a prop or during render. State that
  outlives a render and is not React state belongs in a small class created once in
  `useState(() => …)` (see `openSession` in `LessonScreen.tsx`).

## What next, practice, and progress

- The renderer shows what the core decided and decides nothing: the step, its reason, the
  alternatives, the questions, and every sentence about a hypothesis come from
  `learning.overview` and `learning.start_practice`. `lib/learning.ts` only maps a step to a
  destination and puts counts and waits into words.
- Show a plan with `NextSteps` wherever there is one. Do not build a second way of presenting a
  suggestion.
- Practice reuses `CheckpointPanel` and `lessons.answer`. A practice question is answered at the
  lesson it belongs to (`lesson_id` comes with it).
- Opening a route again must be able to start afresh: `useRouter().visit` goes up with every
  navigation; key a screen on it when "the same place again" means "a new run"
  (`PracticeScreen`).
- Words for progress are states and counts. No percentage, no bar that reads as a score.
- "This did not help" is recorded first and never argued with. What it offers must not include
  the same content again.
- A course with concepts opens on the Learn tab. End-to-end journeys that are about the
  curriculum call `openCourseTab(page, 'Curriculum')`.

## Generation and narration

- Work the AI provider does is a **job**. Start it and follow it with `useGeneration`
  (`lib/use-generation.ts`), which also picks up work that was already under way. Show it with
  `GenerationStatus`, which has every state: waiting, running with a way to cancel, refused
  before it started, failed with what to do next, cancelled.
- Read a job's `result` only through `lib/generation.ts`. It is free-form in the contract and is
  checked there.
- Say what will be sent before it is sent, beside the control that sends it, and name the
  provider by the name the core gives (`provider.status`), never a hard-coded one.
- Speech uses **local voices only** (`loadLocalVoices`). Do not list or use a voice whose
  `localService` is false.
- End-to-end journeys that are not about speech call `showNarrationAsText(page)` first.
- No end-to-end test reaches the real provider: start `startFakeProvider()` and pass its
  address in `ADLE_PROVIDER_BASE_URL`. The app keeps its real limit of four requests a minute,
  so a journey that needs a fifth will see the app wait: test that, or stay under it.

## Renderer conventions

- Logic that can be pure lives beside its screen in a `*-model.ts` file with unit tests
  (`screens/course/curriculum-model.ts`). Components stay thin.
- A mutation that returns the whole resource updates it with `setData`; do not refetch.
- A dialog that contains a form is mounted only while open, so its fields start from the current
  data, and it marks its first field with `data-autofocus`.
- A control whose selection *records* something (a self-rating) is a set of buttons with
  `aria-pressed`, never a radio group or select: those change as the arrow keys pass over them.
