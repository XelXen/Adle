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

## Providers and their keys

- `window.adle.provider.*` take a provider's **name** and, for `setApiKey`, the key. The name
  is checked against `PROVIDER_IDS`; where the provider is comes from the core
  (`parseProviders` in `electron/main/providers.ts`). Never add an argument that is, or could
  carry, an address.
- `ProviderKeyStore` keeps a key by provider **and** address and returns it only for that
  pair. Do not add a way to read "the key" without both.
- `syncProviders` is part of starting the core (`CoreProcess`'s `afterReady`), so it runs on
  every start there is: the learner's choice first (one provider, or `'auto'`), then the
  keys, and only then is anyone told the core is ready. If the choice cannot be applied no
  key is handed over and the start fails (ADR-029). Do not hand a key over anywhere else,
  and do not publish "ready" before it has run.
- Only the handler of the learner's own click calls `provider.select`. Nothing may change the
  choice because something failed. "Automatic" is itself a choice the learner made.
- Where a request will go is what the core plans (`provider.status` → `routes`): say it with
  `destination(status, work)` from `lib/provider.ts`, never with one provider's name.
- Name a provider and a model in the interface by the names the core gives
  (`provider.status`, a job's `written_by`). Who wrote something is what its job recorded,
  not whichever provider is in use now (`authorName` in `lib/generation.ts`).

## File paths

Renderer script must never be able to name a file. A path may enter the app in two ways only:

- a dialog of the operating system, opened by the main process: to choose files to import
  (`registerImportHandlers` in `electron/main/ipc.ts`), where to save a copy of the data, or
  which copy to restore (`electron/main/data.ts`);
- files the learner dropped, turned into paths by the preload with `webUtils.getPathForFile`
  (a `File` constructed by script has no path and is rejected).

The preload calls **no method** of anything the page hands it (`electron/preload/dropped.ts`):
a value from the page can carry functions of its own, and `files.map(...)` was once a way to
name any path. Take it apart by index and by type.

Paths are validated (`parseImportPaths` in `imports.ts`; `parseSavePath` and
`parseRestorePath` in `data-copy.ts`) and handed to an **internal** core operation or to the
core's start-up. Do not add an IPC channel or a public core operation that takes a path, a URL,
or a directory from the renderer, and do not return a path to it: say what happened and, at
most, a file's name.

## The data as a whole

- `window.adle.data.*` (save a copy, restore, delete everything, show safety copies) take
  **no arguments**. The question each one needs answered is asked by the main process in a
  window of the operating system. Keep it that way: an argument is a way for the page to answer.
- Anything that deletes or replaces the core's files runs inside `core.whileStopped(...)`,
  which also keeps anything else from starting the core meanwhile. Start it again afterwards
  and call `afterStart` (the new core needs the provider key).
- A restore is `core.restart({ restoreFrom })`; read `core.lastRestore` afterwards. `null`
  means the core said nothing about it, which is never reported as success.
- Rules about paths are pure functions in `data-copy.ts` with unit tests; `data.ts` has the
  dialogs. In end-to-end tests the dialogs are replaced with `app.evaluate` (see
  `e2e/data.spec.ts`), never driven.

## A course as a file

- `window.adle.courses.*` (ADR-063) take what the learner chose in the page and
  nothing else: `saveFile(courseId, { kind, holds })`, `chooseFile()`,
  `bringIn(token, holds)`. Their arguments are checked in `course-file-rules.ts`
  (pure, unit tested): exactly the four choices, each true or false; a kind Adle
  makes; a course's id. Never add an argument that is, or could carry, a path.
- **Saving:** the core writes the file in its own folder and says its name; the
  main process asks where in a save dialog and moves the file there
  (`handedOverPath` finds it only by a name of the kind the core makes), or removes
  it if the learner backs out. The core is never told the place.
- **Bringing in:** the file is chosen in an open dialog. The page is told its name
  and what it holds, and is given a token; the path stays in the main process, for
  that one file, for half an hour. `bringIn` works only with the token last given.
- In the page, `SaveCourseDialog` (a course's page) and `ImportCourseDialog` (the
  library) show the choices; what either kind holds is `holdsFor` in
  `lib/course-files.ts`, and the rarely needed choices sit under `Disclosure`
  ("Advanced"). A course that came in a file says "Imported" (`originLabel`).
- A journey replaces both dialogs with `app.evaluate` (`e2e/course-files.spec.ts`).

## Settings as a file

- `window.adle.settings.*` (ADR-064): `saveFile(parts, password)`, `chooseFile()`,
  `bringIn(token, parts, { password, setUpVoice })`. Checked in `settings-file.ts`
  (pure, unit tested): exactly the five parts, a password of a sensible length or
  none, and nothing that could carry a path.
- **The main process puts the file together and takes it apart**, because it alone
  reads the keys. Keys are written only locked (`lockKeys`: scrypt, then
  AES-256-GCM) and only when a password was given; a wrong password is found before
  anything is applied. A key is never returned to the page: `chooseFile` says whose
  keys a file has. A key brought in is saved with `keyStore.save(id, address)` for
  the address the core gives for that provider now, then handed to the core as any
  key is. Do not add a way to save keys without a password, and do not read an
  address out of a file.
- The costs a file names for unlocking are bounded (`parseLocked`): a file cannot ask
  this computer for more work than a password needs.
- The provider chosen in a file is applied only if the core offers it here, through
  the same `provider.select` the learner's click goes through; otherwise nothing
  changes and that is said.
- In the page: `SaveSettingsDialog` and `ImportSettingsDialog` (Settings → Privacy &
  data). The import says, before anything changes, what a voice that is not on this
  computer would be here and what setting it up downloads (`setUpNote`); afterwards it
  lists what is different, and the page begins again when the learner presses Done.

## A film of a course

- A course's **Film** tab (`FilmPanel`, ADR-065) shows where its film stands, as the core
  says it (`films.get`, `films.maker_status`; `filmStage` in `lib/films.ts`): the film
  maker to set up (what it downloads, and from where, said first: it is downloaded only
  when the learner presses it), what stands in the way, the film to make (what is sent,
  and the most requests it may cost, one press away with `WhatIsSent`; where each
  chapter's pictures go to be checked when the core plans to, `checks_pictures` and
  `routes.storyboard`, in `filmRequests`, ADR-066), the film being made chapter by
  chapter, one left unfinished to continue, and one made.
- **A film is played from what the core holds**: `fetchFilm` asks for its video a part at
  a time (`films.video_part`) and makes a `blob:` of it; its words come as cues
  (`films.captions`) and become WebVTT in the page, as plain text (`vttOf`). The page names
  a film by its id and nothing else, and never names a place.
- **Saving a film** is `window.adle.films.saveFile(filmId)`, checked in
  `film-file-rules.ts` (pure, unit tested): the core writes it into its own folder
  (`films.save_file`, internal), the main process asks where in a save dialog and moves
  it there, its subtitles beside it unless a file of that name is there already.
- A film takes an hour or more, so it is watched app-wide by `FilmWatch` (the rail's
  "Making a film", a toast and the notification `film_ready` when it is ready, a toast and
  `writing_stopped` when it could not be finished), not by `WritingProvider`. A screen that
  starts a film calls its `refresh()`.
- **Each chapter being made says what it is doing, in its own row** (ADR-076): the job's
  `progress_detail.chapters` (`chaptersAtWork`), shown by `chapterState` in place of
  "Being written"; the bar above says how many chapters are written. Several are made at
  once at NVIDIA (ADR-068): never show one line for all of them.
- A journey uses a stand-in film engine and the stand-in provider (`e2e/film.spec.ts`),
  never a real download.

## When the app itself fails

- What to do about a crashed or hung page, an uncaught error, or a core that died is decided
  in `electron/main/recovery.ts`, in functions that do not import Electron and are unit
  tested. `index.ts` connects them to events. Keep it that way round.
- Every message says what happened in plain words, that the learner's work is safe, and what
  they can do. No error names, codes, or stack traces in front of the learner.
- `appLog.record(event, detail)` takes an event name and a few named facts. Never pass it
  anything the learner typed, opened, or answered, or a path they chose. Nothing is ever sent
  anywhere: do not add a crash reporter, and do not call `crashReporter.start` (ADR-018).
- A real renderer crash kills Playwright's handle on the page. After one, read the window
  through the main process (`reloadedPage` in `e2e/recovery.spec.ts`).

## The window

- The window has no title bar of the operating system's on Windows and macOS (ADR-030):
  `titleBarStyle` hidden, the system's own buttons laid over the page in the app's colours
  (`window.ts`). The page cannot minimise, maximise or close the window: do not add a
  channel for it.
- The page keeps `WindowStrip` along its top to move the window by. **Nothing that can be
  pressed may lie in the top 40 pixels**, where a press moves the window instead. A screen
  that draws itself outside `AppShell` leaves that much room at its top. What has to appear
  there (a dialog, the link that skips to the content) says `app-region: no-drag`, which
  cuts its box out of the strip. `expectNoAccessibilityViolations` fails on anything
  pressable left under the strip, so every screen a journey checks is checked for this; a
  test's clicks do not pass through the window's frame, so only where things lie can be
  checked.
- To see the window as a person does, with the system's buttons on it, draw the app's own
  window into a picture (`PrintWindow`); a screenshot of the page has no buttons in it.

## Themes

- The learner's theme is kept by the main process (`UiStateStore`, checked by
  `parseUiStatePatch`), with Pastel's color (`pastelHue`, a whole hue 0 to 359).
  `colorSchemeOf` turns it into the one setting of the scheme
  (`nativeTheme.themeSource`): Pastel is light, Pastel dark is dark.
- The page marks a Pastel theme with `applyPalette` (`lib/theme.ts`): before its first
  paint (`main.tsx`) and on every change (`AppContext`), through the CSSOM. Anything
  that cannot read CSS asks `useResolvedTheme()`, which is only ever light or dark.
- The window draws its ground and its buttons' strip in the page's canvas and ink
  (`window.ts`), following the learner's settings as well as the system's
  (`look.onChange`): a Pastel color changes nothing the operating system sees.

## URLs and origins

- Never use `new URL(x).origin` for `adle://` URLs in main-process code: Node reports `"null"` for
  custom schemes. Use `adleOriginOf()` from `@adle/event-protocol`.
- The Content Security Policies live in `electron/main/protocol.ts` and are asserted in
  `security-boundaries.test.ts`. Do not add `unsafe-inline` or `unsafe-eval` to the app policy.
- **"No network" includes what is not a request** (ADR-029): no name lookups
  (`refuseNameLookups`), a proxy that is nowhere, and no non-proxied UDP. (A `webrtc`
  directive in the policy is not known to this Chromium and only logs an error.) `e2e/security.spec.ts` tries a peer connection and a preconnect against
  listeners on this computer, from the page and from a player frame. Keep all of it.
- Inline `style` props are fine (React sets them through the CSSOM); HTML strings with `style`
  attributes are not.

## The scene player

- The rest of the app uses `ScenePlayer` (React) or `WanimPlayerAdapter`. Nothing else may touch
  the iframe or import Wanim.
- A change to messages between host and frame is a change to `packages/event-protocol`: update
  both validators, both sides, and the tests in one commit.
- A slide or a figure Adle wrote says, as each step ends, whether any of its words lie over
  others or under a line, or anything lies past the edge of the screen (the scene event
  `layout`, ADR-055, ADR-056), and gives each such word a soft shadow in the stage's color
  as it does (ADR-069), naming what is in whose way by its elements' keys. A hidden trial
  (`runTrial`) hands what a slide said back with its verdict (`layout`, each once, eight
  at most), and the core may draw a crowded slide again (ADR-073); an open lesson looks
  again while one is (`mending`), and a part on the screen keeps the picture it began
  with. `slide-player.spec.ts` and the figures in `scene-player.spec.ts` fail on it, but
  for the slides of `fixtures/slides/crowded/`, which must say it, each such word with its
  shadow and its names.
- A frame may send `MESSAGE_BUDGET_PER_SECOND` messages a second and no more; past that the
  adapter ends the scene like one that hangs. A scene that needs to say something on every
  frame is saying too much: report a change, not a state.
- Any behaviour of Wanim you rely on must be written into
  `skills/wanim-scene-authoring/reference.md` as Verified, with a test.
- **A picture is tried before it is shown** (ADR-038). `SceneTrials` (mounted with the
  writing context) asks the core for trials while a lesson is written and runs each with
  `runTrial` in a frame nobody sees (`hidden: true`): a load with `rehearsal: true`, which
  the frame runs through fast (`frame-clock.ts` rushes, `time-warp.ts` speeds its clock).
  Never rehearse a scene a learner is looking at, and never show a frame that rehearses.
- **The adapter chooses the size a scene is drawn at** from the width of its frame
  (`qualityForWidth`, ADR-032). Do not pass `quality` to make a picture "sharper": drawn
  more than twice as wide as it is shown, a picture loses its thinnest strokes when the
  browser shrinks it. The frame's canvas fills the frame at any drawing size.

## Build and run

- `scripts/build.mjs` bundles main and preload with esbuild (CommonJS, `electron` external) and
  builds the renderer and player with Vite. Output goes to `dist/` (not committed).
- There is no dev server (ADR-003). `npm run dev` rebuilds and restarts Electron.
- `ADLE_USER_DATA_DIR=<dir>` runs against an isolated profile. Tests always set it.
- `assets/brand/` holds the logo artwork and its vector form; `assets/icons/` is rendered from
  it by `npm run icons` and committed. The window reads its icon from `assets/icons/` at run
  time (`paths.windowIcon`), so the package script ships that folder inside the archive.

## The packaged app

- `scripts/package.mjs` puts `package.json`, `dist/`, and the icons into `app.asar`, and a
  private Python with the core into `resources/core` (ADR-019). The Python's `venv` and
  `ensurepip` stay in it, and on Windows `python.exe` stays beside `adle-core.exe`: a
  natural voice's environment is made from it (ADR-042), and `package:check` makes one. Nothing else ships: if the app
  comes to need a file at run time, it must be in `dist/` or added to the script, and the
  packaged end-to-end run is what tells you that you forgot.
- Anything the main process needs from npm must be bundled by esbuild. There is no
  `node_modules` in the package, so an `external` other than `electron` breaks it.
- `resolveLaunchSpec` decides how the core is started. Packaged, it is the private Python
  with `-I` first. Do not pass it anything through `PYTHON*` variables: they are ignored.
- The release build cannot be driven by a test tool, on purpose. Test the build from
  `npm run package:test` with `npm run e2e:packaged`; check the release build from outside
  with `npm run package:check`. A new fuse goes into both `package.mjs` and the check.
- **Installers** (ADR-034) are made by `scripts/installer.mjs` from the release folder as it
  is, with the system's own tool: Inno Setup (`installer/windows.iss`), `hdiutil`,
  `dpkg-deb` (`installer/linux.desktop`). No tool is added to the project for this. With
  `--check` the script installs what it made, starts it with
  `smoke-packaged.mjs --at=<installed executable>`, and removes it: that is how an installer
  is tested, on GitHub's machines, for every push.
- **The private Python must be one uv manages.** `package.mjs` refuses any other: an
  environment made from a computer's own Python would have the computer copied into the
  app. The workflows set `UV_PYTHON_PREFERENCE=only-managed`.
- **macOS:** after the fuses and the notices have changed the bundle it is signed "ad hoc",
  or a Mac with Apple's processor will not start it. That is not a developer's signature.
  Anything added to the bundle goes in before that step.
- **Linux:** the `.deb` installs Chromium's sandbox helper as root's, marked to run as
  root. Never give a launcher `--no-sandbox`, and never make a kind of package that can
  only run that way.
- The identifier in `installer/windows.iss` (`AppId`) is how Windows knows a newer Adle
  from a second program. It never changes.

## Tests

- Unit tests sit next to the code as `*.test.ts(x)`. Main-process tests mock `electron`.
- `e2e/` drives the built app. Use the `adle` or `profileDir` fixture from `e2e/support/app.ts`;
  never launch against the default profile. `mountRawPlayer` tests the frame at the protocol level.
- Set a theme with `launchApp(dir, { theme })`, not media emulation: it exercises the real path.
  Pastel and Pastel dark take `pastelHue` too (ADR-074).
- `getByRole(role, { name })` matches substrings. Add `exact: true` for short names such as
  navigation items; a card on the same screen may contain the same word.
- A course is in two places: its card in the library and its entry in the rail. Ask for the
  card with `courseCard(page, name)`.
- A lesson and a round of questions have no rail (`AppShell focus`). A journey that needs
  Settings or the library from there goes back to the course first.
- `expectNoAccessibilityViolations` and `screenshot` wait for motion to finish (`settled`).
  Do the same before measuring a colour or comparing two pictures yourself.
- Never drive a native dialog. Replace `dialog.showOpenDialog` in the main process with
  `app.evaluate` (`chooseInFileDialog` in `e2e/support/courses.ts`, which also has the shared
  steps for creating a course, importing, running axe, and saving a screenshot).
- `getByLabel` also matches `aria-label`s that contain the text ("Objective 1" matches "Remove
  objective 1"). Ask for the role: `getByRole('textbox', { name: 'Objective 1' })`.
- Never call `show()` on the app window from a test (ADR-008).
- **The window's pixels and a picture of the page are not the same.** A page under test is
  laid out at one pixel to the point; the window is shown at the display's own scale, and
  `capturePage` reads that. A journey whose answer depends on how many pixels there are
  fixes the scale: `launchApp(dir, { displayScale: 1 })`.

## Lessons

- `renderer/src/lesson/` is plain TypeScript with unit tests and no React: `LessonController`
  (what is on screen), `Narrator` engines, `SceneCues` (narration to scene), `answers`.
  `screens/lesson/` only draws what they say.
- **The narrator is the clock.** Do not add timers to the controller or the screen; a new way of
  reading a lesson is a new `Narrator`. A break's clock is the app's (`app/BreakContext.tsx`)
  and is never part of a lesson.
- A question the learner asks about a part (`AskDialog`, `lib/asks.ts`) is a job like any
  other. In a part that teaches with a picture (`canRedraw`), the learner can ask for the
  picture to be drawn again instead ("Change the picture", ADR-067); what comes back is
  offered in the answer and the note ("Use this picture"), and only that press puts it
  in the lesson: `lessons.use_ask_picture` returns the lesson, which the screen takes
  (`useLessonUpdates().adopt`) and the controller swaps into the part
  (`LessonController.replace`, the one way a part already there changes; a learner in it
  starts it again). "Put the original back" is `lessons.put_back_picture`. The lesson holds the job, so the dialog can be closed while it is answered, and
  opened again to watch it or stop it; a lesson that is opened again picks up a question
  still on its way. A failure is said where the learner is: in the dialog if it is open, as
  a toast if not. Show the learner's own words as plain text and the answer with `MathText`.
- A narrator calls `onWord` only if it really knows the position. Never fake word highlighting.
- **A slide is paced by its cues** (ADR-049). Every narrator delivers a line's `cues` through
  `onCue`, once each, in order, all before `onEnd` (`CueKeeper`); one that does not know
  where it is delivers them at the time the line would reach them (`CueClock`), which is
  not a claim to a word. The controller passes each to `advanceScene`; `SceneCues` counts
  them and gives the slide one each time it says it holds after a step (`setHolding` with
  the step's number). A slide is loaded with `steps` (`pacing: 'cued'`); never send it
  `next` before its step event, which would cut the step short.
- The renderer has no answer keys. Anything that needs one (what was right, why) comes back from
  `lessons.answer`. Do not add a field to the player view to "save a round trip".
- Lesson text is shown with `MathText`, never `dangerouslySetInnerHTML`.
- A segment with a scene must render something useful in five cases: the scene runs, the scene
  fails in the player (`ScenePlayer` shows the fallback), the core withheld the scene
  (no artifact for the reference), the scene is still being drawn, and the scene arrived
  after the part had begun (ADR-031).
- A lesson can be open before all its pictures are drawn (ADR-031), and before all its
  parts are written (ADR-048). `useLessonUpdates` finds out when a picture or a part has
  arrived; it is not a clock of the lesson and decides nothing about what is said or when.
  The words of a part already there stay as they were when it was opened, and a new part
  only ever comes after the last (`LessonController.extend`). A learner who reaches the
  end of what is written waits there (`held`) and goes on into the next part when it
  comes; the last part so far is not the last while `more` is true, so it never says
  "Finish lesson". A picture takes its place by itself only in a part that has not begun
  (`status === 'ready'`); otherwise it is offered. Ask the picture, not the part, whether
  there is anything to operate (`scene.interactive`): the two can disagree in a lesson
  opened early.
- **A lesson is watched on a screen** (`StageFrame`, ADR-035): dark in either theme, with
  the words being said along its foot. Whatever a part shows goes on it (`ScenePlayer
  onStage`, or the board), except a question, which is a card of the page. On the screen
  use the `--ad-color-stage*` tokens and `IconButton variant="stage"`; the page's own
  tokens there are dark on dark in the light theme. The transcript's lines are all in the
  page whether one is shown or all: hide the others from the eye, never from the tree.
- **The bar under a lesson is one row** (ADR-054): the lesson's own controls, then what the
  learner may need to know just now (`.controlNotes`, which wraps in its own room), then
  what to do about the part. The much-used controls keep their words; Read aloud,
  Transcript and This didn't help are `IconButton` toggles with `aria-pressed`, named by
  the words they had. A new note goes in the middle, never into a group of buttons.
- **Full screen** is the player element itself (`useFullscreen`), by the browser's own
  means; the main process grants it to the app's own page and to nothing else. In a
  journey, give the screen back with the button that took it: a test's Escape does not
  reach the browser. What is not on the lesson's screen needs a surface of the page's
  under it there. The filled player says `app-region: no-drag`, because it covers the
  strip the window is moved by.
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
- The session summary (`SessionSummary`, from `overview.session`) sits under the suggested
  step on the Learn tab; that step is its "Continue". It shows right answers as counts and
  never as a share of the answers given, and it does not list wrong ones.
- Practice reuses `CheckpointPanel` and `lessons.answer`. A practice question is answered at the
  lesson it belongs to (`lesson_id` comes with it).
- Opening a route again must be able to start afresh: `useRouter().visit` goes up with every
  navigation; key a screen on it when "the same place again" means "a new run"
  (`PracticeScreen`).
- Words for progress are states and counts. No percentage, no bar that reads as a score.
- "This did not help" can be taken back (ADR-054): its toggle in the bar is pressed while
  the report stands (`unhelpful_parts`), its dialog offers "Undo" once the report is saved,
  and pressing the toggle again takes it back with nothing to choose.
- "This did not help" is recorded first and never argued with. What it offers must not include
  the same content again.
- A course with concepts opens on the Learn tab. End-to-end journeys that are about the
  curriculum call `openCourseTab(page, 'Curriculum')`.

## Generation and narration

- Work the AI provider does is a **job**. Start it and follow it with `useGeneration`
  (`lib/use-generation.ts`), which also picks up work that was already under way. Show it with
  `GenerationStatus`, which has every state: waiting, running with a way to cancel, refused
  before it started, failed with what to do next, cancelled. Give it `usualSeconds` from the
  core's plan: it says how long the wait usually is and offers a break of that length,
  and `kind` (`lesson` or `suggestions`): while words are written it says what is
  happening in the learner's terms and lists the titles written so far
  (`lib/writing-progress.ts` reads `Job.progress_detail`, ADR-037). Never show more of an
  answer than its titles while it is written.
- Long work is watched app-wide by `WritingProvider` (the rail's "Now", the toast and the
  notification when it is ready). Something that arrived is said once, unless the screen in
  front of the learner shows it (`showsOutcome`); something that failed is always said. A
  screen that starts such work calls `refresh()` (`useGeneration` does). Do not add a second
  announcement.
- A notification is `getBridge().app.notify(kind)`. In end-to-end tests none is shown:
  read what would have been with `adle.notices()`, and set the focus with
  `adle.setFocused(false)` first (one is only asked for while Adle is in the background).
- Read a job's `result` only through `lib/generation.ts`. It is free-form in the contract and is
  checked there.
- **A lesson job has a lesson before it has ended** (ADR-031, ADR-048): `readLessonOutcome`
  reads it from a running job, as soon as its first part is written. `hasLessonToStart`
  says there is one; `isWritingTheRest` that its later parts are still being written (it
  is still seen taking shape, part by part), and `isDrawingPictures` that only pictures are
  left (the core reports the `drawing` stage before that). `useGeneration`'s third argument
  (`onUsable`) fires when there is one. Show such a job with
  `GenerationStatus lessonReady`. A tab of the course says "Lesson ready" with
  `useLessonNotices`; everywhere else `WritingProvider` does, and it keeps the one record
  of who was told (`wasTold`, `markTold`), so a lesson is announced once however the
  learner moves about. Removing a lesson forgets its job on the screen; the core stops it.
- What will be sent, and where, is one press away from every control that sends it:
  put `<WhatIsSent what to wait />` beside the button (ADR-036), with the phrase from
  `lib/generation.ts` and the destination the core plans (`destination(status, work)`),
  never a hard-coded name. Do not write the sentence beside the button again, and do not
  add a control that sends without the note. A journey reads it with `openWhatIsSent`.
- **A file's pages that are pictures are read at the learner's word** (ADR-060):
  `ReadPictures` in each row of Materials, with `WhatIsSent` beside "Read them" and where
  it goes from `routes.read`. When nobody chosen can read pictures, or has no key, there is
  nothing to press and `noReader` says what would let them be read. A reading under way
  is followed when the tab is opened again (`jobs.list_active`, kind `read_pictures`).
- **A course from files is made with its files** (ADR-053): `NewCourseDialog` creates the
  course, then `importWithPicker`; nothing chosen, and the course is removed again. Its
  "Set it up for me" asks for the suggestions with `setup`; `readSetUp` reads what that
  added, and the curriculum then reloads, selects the first concept and follows its lesson.
  The Materials tab follows an import begun elsewhere (`jobs.list_active`). A journey
  makes a course with `createCourse(page, name, { files, app })` or `{ topic }`; "Set it
  up for me" is left off unless it passes `setUp`.
- Speech uses **local voices only** (`loadLocalVoices`). Do not list or use a voice whose
  `localService` is false.
- **A natural voice is played from what the core recorded** (ADR-042): `RecordedNarrator`
  plays a line's clip and marks each word at the time the core measured, and
  `useRecordedNarration` hands it the clips as they are recorded. A line not recorded yet
  is waited for (ADR-051): the narrator holds it (`state.waiting`, said in the bar with a
  way to read on in the other voice) and plays it when its clip comes; the other voice
  reads it only when the learner chooses it for the rest of the lesson (`useFallback`) or
  no recording will come (`expect(false)`). The voice never changes by itself in the
  middle of a lesson. A lesson job that says `voicing` has a lesson that is not ready yet
  (`hasLessonToStart`, `lessonNotice`). Settings → Learning →
  Voice (`VoiceChoices`) sets a voice up, follows the setup, and removes a voice, saying
  first how much is downloaded and from where, and says when one set up here is slower
  than speech (`speedNote`, ADR-052). Each speaker can be heard before it is chosen, and
  the Expressive voice is put together from parts, from a voice to start from, or
  written in the learner's own words, and heard before it is saved (`useVoiceSample`,
  ADR-057, ADR-062): the parts and their names are the core's (`design_choices`), and
  so is the description they make (`voice.describe`), never written in the page;
  a voice is saved and heard by its parts when it has any (`voiceRequest`); while lessons are recorded in
  a voice just chosen, the card in use says which (`recordingNote`). A journey uses a stand-in engine
  (`e2e/voice.spec.ts`), never a real download.
- **The teacher** a lesson and an answer are written as (ADR-071) is chosen in Settings →
  Learning → Teacher (`TeacherSettings`), the way the Expressive voice is: its parts, the
  teachers to start from and the sentence they make are the core's (`learner.character`,
  `learner.describe_character`), never written in the page; the switch to teach as the
  Expressive voice's person is offered only while that voice reads the lessons.
- End-to-end journeys that are not about speech call `showNarrationAsText(page)` first.
- No end-to-end test reaches a real provider: start `startFakeProvider()` and pass its
  address in `ADLE_PROVIDER_BASE_URL` (one endpoint in place of the choice), or start two and
  pass both in `ADLE_PROVIDER_ENDPOINTS` (the two providers, moved; `e2e/providers.spec.ts`).
  The app keeps the providers' real limits (ADR-068): five requests a minute at AIHubMix,
  one at a time, so a journey that needs a sixth will see the app wait (test that, or stay
  under it); forty a minute at NVIDIA, up to six at once, so a film's chapters sent to its
  stand-in can arrive together, and a queue answers them in the order they arrive. A file's
  pages arrive in order: each is drawn, one at a time, before it is sent. `{ slowly: true, thinkMs, pieceMs }`
  answers like a model that thinks first and writes a title at a time.
- A toast that reports a failure is an `alert`; one that reports a success is a `status`.
- **Words** (ADR-028, ADR-044): American English, short, plain, about the learner's task.
  `renderer/src/wording.test.ts` fails on a British spelling in any string. "Couldn't save your goal",
  "Loading library…", "Cancel" and the action by its name. Typographic quotation marks and
  apostrophes. Nothing about the app's own workings unless the learner must act on it.
- The rail says nothing about the app's own service while it runs. The page writes the state
  on `<html data-core>`; a journey waits for it with `expectReadyOnPage(page)`.
- A break knows where leaving it leads (`rest.returnVia`): back, or somewhere said, such as
  the course after a lesson that has just been finished.
- **How a course's lessons are formed** (ADR-061) is the core's to say: read it with
  `useLessonRules` (`lessons.rules`, `lib/lesson-rules.ts`) and show it with
  `LessonRulesDialog`, opened from the course's header ("Taught as …"), where the learner
  may choose the subject or hand the choice back to Adle. The teaching styles offered for
  a lesson are those that suit the course's subject (`waysFor`). Never write a rule, or a
  subject's name, into the renderer.

## Renderer conventions

- Logic that can be pure lives beside its screen in a `*-model.ts` file with unit tests
  (`screens/course/curriculum-model.ts`). Components stay thin.
- A mutation that returns the whole resource updates it with `setData`; do not refetch.
- A dialog that contains a form is mounted only while open, so its fields start from the current
  data, and it marks its first field with `data-autofocus`.
- A control whose selection *records* something (a self-rating) is a set of buttons with
  `aria-pressed`, never a radio group or select: those change as the arrow keys pass over them.
