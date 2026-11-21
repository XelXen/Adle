# Project state

The single place to find out where Adle stands and what to do next. Update it at the end of every
work session (see `AGENTS.md` → "Keeping the next agent oriented").

- **Last updated:** 2026-11-21
- **Branch:** `dev` (all work; `main` holds only the original plan commit until the owner merges)
- **Last commit:** see `git log -1`
- **Active milestone:** M8 — release hardening, done as far as this machine can take it:
  failure handling (ADR-018), packaging (ADR-019), the licence inventory, the audits, the
  performance report, and the release checklist. Since then: a second AI provider, NVIDIA
  NIM, beside AIHubMix (ADR-021), through which **a real model has written lessons for the
  first time**; and, at the owner's request on 2026-11-20: a new look (ADR-022) in Geist
  (ADR-025), both providers used together (ADR-023), questions asked during a lesson
  (ADR-024), and a break while a lesson is written (ADR-026). Then, after the owner looked
  at the app and asked for a review of it: neutral colours with a near-black dark theme
  (ADR-027), every sentence rewritten short and plain (ADR-028), the findings of two reviews
  fixed (ADR-029), and a title bar of the app's own (ADR-030). And then the largest thing
  that was left from the plan: **a lesson opens as soon as its words are written**, and its
  pictures arrive while the learner studies (ADR-031). What is left needs the owner; see
  "Next actions"
- **Commits:** a commit is GPG-signed if the owner answers the passphrase prompt (a
  `pinentry` window on the desktop) within a few minutes. If not, it is made unsigned, as
  the owner asked on 2026-11-21. `git log --format='%h %G? %s'` shows which is which.
  Nothing is ever pushed.

## Milestone status

| Milestone | Status | Evidence / what is missing |
|---|---|---|
| M0 — Foundation | **Done** | Workspace, pinned toolchain, lint/type/test gates, docs, ADR process, CI workflow written. CI itself is NOT RUN (no remote yet). |
| M1 — Desktop shell and Sprout | **Done** | App launches without a key; welcome, library, settings; key add/remove without exposure; themes; a11y gates. |
| M2 — Persistence and ingestion | **Done** | Database with safe migrations, backup and restore; import of PDF, DOCX, Markdown, text with provenance; duplicate detection; FTS5 search; course and materials screens. Vector search deliberately not built (ADR-007). |
| M3 — Curriculum and learner model | **Done** | Concept graph validated on every write (loops, references, order, layers); curriculum screen (list and map; add, edit, reorder, remove; objectives; prerequisites with reasons; links to materials; outline from headings); learner preferences; knowledge as an append-only record folded through BKT into four states with reasons; review scheduling; retrieval with provenance (ADR-009). **Deferred to the lesson work:** working memory and the interaction event log. Answer evidence is exercised through the service in tests; in the app only self-rating can create evidence until questions exist. |
| M4 — Wanim and Lesson IR | **Done** | Player frame, adapter, static scene policy, skill, threat model (ADR-004). Lesson IR 1.0 with a generated JSON Schema; one validating gateway; scenes re-checked on every read; answer keys kept in the core with deterministic scoring; the lesson player; the first lesson of the sample course (ADR-010). The same journeys pass against the packaged build. |
| M5 — Generation, audio, timeline | **Done** | Provider client, quota, and gateway; curriculum proposals and lessons as cancellable jobs compiled into the Lesson IR (ADR-012); the interface for both with every failure state; narration aloud through the computer's own voices (ADR-013). Two providers, chosen by the learner, each with its own key and count; a provider's next model stands in when its first is not available, and that is always said (ADR-021). Every path is tested against stand-ins. **A real model has written lessons** (Kimi K3.1 Pro and Mistral Large 4 through NVIDIA NIM, 2026-11-20); see "The real providers". |
| M6 — Assessment and adaptation | **Done** | Hypotheses about mistakes computed from the record (tentative, supported, rejected, resolved), checked with questions that would show them, and dismissible by the learner; slips counted as partly right; repeats counted in full only after a gap; questions kept for practice in the Lesson IR; a next-step policy with a reason for every step; the Learn tab, practice and review, "what next" after a lesson, "This did not help"; teaching strategy chosen or rotated (ADR-014). Not built by decision: model grading of open answers and model-proposed hypotheses. |
| M7 — Complete UX and sample course | **Done** (two items left as known gaps) | Done: every one of the eight sample concepts has a lesson with scenes, questions tagged with the mistakes their wrong options point at, and practice questions; every lesson is played from start to finish and every scene is run in both themes by the E2E suite. Also done: Settings → Privacy & data can save a copy of everything as one file, restore from one (checked and upgraded before anything is replaced; what is replaced is kept; undoable), and delete everything (ADR-016). Also done: the session summary (ADR-017). Polish done: every outcome of the new screens checked with axe, focus kept after "That was a slip". Left as known gaps, by decision: narration and animation are synchronised per segment (Wanim's slides mode was not tried), and screenshots are saved for review rather than compared against baselines. |
| M8 — Release hardening | **Done as far as this machine allows** | Done: a crashed or hung page, an uncaught error in the main process, and a core that dies are each handled, with a local log and no reporting (ADR-018). Packaging (ADR-019): a folder that runs by itself, with a private Python for the core, fuses set; the whole end-to-end suite passes against the packaged app, and the release build passes a start-up check from outside. Licence inventory generated and checked in every gate; `npm audit` and `pip-audit` clean; `PERFORMANCE.md` and `RELEASE_CHECKLIST.md` written. **Not done, and not doable here:** an installer and code signing (the owner's certificates), macOS and Linux (no machine), a clean computer, a generated lesson sat by a person (the owner's key is the owner's to type in). |

## What works in the running app

- First launch → welcome with the local-first disclosure → library. Remembered across restarts.
- Navigation rail (collapses under 960 px), light/dark/system theme applied before first paint.
- **The window has a title bar of its own** on Windows (and, untried, macOS): the app's
  canvas runs to the top edge, the system's buttons sit on it in the theme's colours, and the
  window is moved by the strip along its top. Linux keeps the frame it is given.
- **Library:** courses listed most recently used first; create a course from a topic or from
  materials; delete a course (with its files) after confirmation.
- **Course → Materials:** import PDF, Word, Markdown, and text files with the file dialog or by
  dropping them; progress while importing; per-file outcome (imported, already imported,
  rejected with a reason); extraction warnings; remove a source; search with file and page or
  section for every hit.
- **Course → Learn** (the tab a course with concepts opens on): one suggested next step with
  the reason for it, the alternatives ("Other options"), a note that stopping is fine when things
  are going badly, and each concept in learning order with its state in words, what is still
  missing, when it is next reviewed, and what Adle has noticed about it.
- **Hypotheses:** two answers pointing the same way show as "Seen more than once" with a
  sentence; one answer shows as "Suspected". "That was a slip" sets one aside.
  A slip of sign shows as a slip and is counted as partly right.
- **Practice and review:** a few questions on one concept, with why these questions, answered
  and explained as in a lesson, then a summary and what to do next. Nothing answered in the
  last twelve hours is asked again; if nothing can be asked, the screen says when it can.
- **Reviews:** scheduled by the core after answers; due ones are suggested first among routine
  steps and marked on the concept. Doing one moves the next further away.
- **The session summary** (Learn tab, under the suggested step): "This session" while the
  learner may still be in it, "Last time, yesterday" and the like afterwards. Lessons finished
  and questions answered; for each concept worked on, how many answers were right (with any
  that were given "with help" named, and one sentence saying what that means), what is still
  needed in the concept's own words, and when its review comes. No score, and wrong answers
  are not listed.
- **"This didn't help"** in a lesson: skip to the next question, have the concept explained
  another way (a chosen way of teaching; needs a key), or go to the course. The suggestion on
  the Learn tab changes accordingly and says why.
- **Course → Curriculum** (where a course without concepts opens, once it has a topic or materials): the
  concepts as a list in teaching order or as a map; add, edit, reorder, and remove concepts;
  learning objectives; what each concept needs first and why, with loops refused and explained;
  "Start from your materials" offers the headings of imported files as concepts; link a concept
  to passages in the materials; say how well you already know a concept and read back the record
  of everything noted about it.
- **Library → sample course:** "Try the sample course" adds "Introduction to neural networks"
  (eight concepts with objectives and reasons for every prerequisite) without a key. Every
  concept has a lesson of seven or eight parts: nine animated scenes and two things to try (the
  input of an activation function; the learning rate of gradient descent), questions in at
  least two forms with a question that asks to apply the idea somewhere new, and four or five
  further questions for practice and review. The whole loop can be walked without a key:
  lesson, evidence, the next concept, a prerequisite to revisit, practice, reviews.
- **Lessons:** a concept lists its lessons with how long they take and how far the learner has
  got. The lesson player shows parts one at a time with captions at the learner's reading pace,
  a board that fills in, a transcript, scenes that follow the narration (held until Start,
  paused with it), an interaction with keyboard-operable controls, and a description in words of
  every picture. Nothing plays until Start; Previous, Continue, and the numbered parts move
  around what has been reached.
- **Questions:** multiple choice, true or false, numeric, short answer, ordering, and
  self-assessed explanation. Hint, "I am not sure", and Skip. The core scores, explains, records
  the attempt and the evidence, and says in words what changed. After checking, options read
  "Your answer" / "Correct answer".
- **Resume and review:** a lesson reopens at the part where it was left; a finished one reopens
  from the start with every part open and no question blocking. A finished lesson ends with
  what to do next.
- **When a scene cannot run:** if it fails in the player, or the core withholds it, the part
  shows its description in words and the lesson goes on.
- **Suggested concepts:** "Suggest concepts with AI" on the curriculum says what will be sent,
  runs as a job with progress and Cancel, and ends in a review dialog where the learner picks
  what to add. Suggestions that finish while the learner is elsewhere wait to be reviewed or
  discarded. Nothing is added without the learner choosing it.
- **Generated lessons:** "Create a lesson with AI" on a concept (and "Create lesson" on
  the Learn tab) says what is sent, where, and about how long until the lesson can be
  started, shows progress and Cancel, and adds a lesson that plays like any other.
  **The lesson is there as soon as its text is written** (ADR-031): listed with "Pictures on
  their way", announced once, and ready to start while its pictures are drawn. A part whose
  picture has not arrived says so and gives the same idea in words; a picture that arrives
  takes its place in a part that has not begun, and is offered ("The picture is ready. Show
  picture") in one that has. "Stop" then stops the pictures and keeps the lesson; removing
  the lesson, or its course, stops the work. For another lesson on the same concept
  the learner can choose how it should explain; left alone, Adle uses a way not used yet. A
  concept has at most four lessons. No key, a rate-limit wait, a used-up day, a provider failure, and a cancelled job each
  have their own words and their own way forward. While a model is at work the job says
  what it is doing ("Writing the lesson: Kimi K3.1 Pro is thinking it through", then "is
  writing"): the models that work today take minutes over one answer.
- **Which model wrote it:** if a provider's first model is not available, its next one is
  asked, and that is said while it happens ("Kimi K3.1 Pro is not available at the moment.
  Asking Mistral Large 4 instead") and afterwards: in the notice that a lesson is ready, and
  in the review of suggested concepts, which names its author ("Suggested by Mistral Large 4
  on NVIDIA NIM"). A lesson a model wrote says so under its title, in one line ("Written by
  Kimi K3.1 Pro on NVIDIA NIM. AI can make mistakes."): who wrote it is kept with the
  lesson.
- **Narration aloud:** the lesson is read by a voice installed on the computer (never an online
  one), with "Read aloud" and "Transcript" switches in the lesson. Without a voice, or if the
  voice fails, the narration is shown as text at the learner's reading pace.
- Settings → AI provider: **"Provider": Automatic, AIHubMix only, or NVIDIA NIM only.**
  Automatic uses every provider that has a key, each for what it is best at: what is waited
  for (a question, a list of concepts) goes to the quick one, long work (a lesson) to the
  roomy one once the quick one is half used for the day, and the other is asked when one
  cannot answer. "Current routing" shows the plan for each kind of request and the reason.
  The choice is changed only there, and not while something is being written. Below it, a
  card for each provider: its address, its models in the order they are asked, its key
  (save, replace, remove; OS-encrypted; kept for one provider at one address and never sent
  anywhere else), **"Test key"** (one word from that provider, nothing of the learner's
  sent), and "Usage today", with a sentence saying whether the limits are the provider's
  or Adle's own.
- **Asking a question during a lesson:** "Ask a question" in the lesson's bar pauses the
  lesson and opens a dialog: the learner's own words or a ready-made question, what will
  be sent and where, and "Ask". The answer is kept beside that part under "Your questions
  about this part", says who wrote it, and can be removed. The learner can carry on with
  the lesson while it is written. On a question the lesson is asking, Adle helps without
  giving the answer, and the answer that follows counts as an aided one.
- **Waiting:** where something is being written, the app says about how long it usually
  takes, that the learner need not watch, and offers **a break**: one clock sized to the
  wait, a small idea of what to do away from the screen, and what is being written
  meanwhile. The rail shows "Now": what is being written (or "Drawing pictures") and a
  running break. When it is ready, which for a lesson is when it can be started, the app
  says so once, and so does the operating system (fixed words, only while Adle is in the
  background; can be turned off in Settings → Appearance). A break is also offered
  at the end of a lesson. Nothing about breaks is counted or kept.
- "Cancel" and "Stop" take effect at once, however silent the provider is.
- **Library:** opens with "Continue learning": the suggested next step of the
  course last opened, with its reason. A lesson a model wrote can be removed from its
  concept (after a confirmation that says what goes and what stays); a lesson that draws on
  the learner's materials names the passages under its title.
- Settings → Learning: pace, explanation depth, narration, voice, volume (with a sample),
  captions, goal (stored by the core).
- Settings → Privacy & data: what is stored and exactly what each kind of request sends.
  **Save a copy** writes everything to one `.adle` file wherever the learner chooses.
  **Restore from a copy** checks the file, brings it up to date, keeps what it replaces as a
  safety copy, and restarts the local service on it; a file that is not a copy, or cannot be
  used, changes nothing and says why. **Show safety copies** opens their folder; one of them
  can be restored the same way, which is how a restore is undone. **Delete everything** asks
  in the operating system's own window, then removes every course, material, answer, and
  safety copy; the key and the appearance settings stay. Each works when the local service
  has failed to start, except saving.
- Settings → About: whether Adle's background service is running, and "Restart"; an
  animation check with a mirrored, keyboard-operable slider; "Open log folder" opens the
  folder of local logs.
- **Words** (ADR-028): short and plain everywhere, with nothing about the app's own workings
  unless the learner must act on it. The rail says nothing about the background service
  while it runs. Progress is Not started, Learning, Nearly there, Understood.
- **When the app itself fails** (ADR-018): a page that crashes or hangs, and an error nobody
  caught in the main process, each bring a plain message from the operating system with a way
  on (reload, wait, restart, quit); a core that dies is started again, at most twice in five
  minutes. Each is noted in `logs/app.log` on this computer. Nothing is reported anywhere.
- Python core starts as a supervised child, authenticates with a per-launch token, migrates its
  database (with a backup first), and exits with the app.
- **As a packaged app** (`npm run package`): a folder with `Adle.exe`, the app in an archive,
  and a private Python for the core that takes nothing from the computer it is on. Everything
  above works in it; the end-to-end suite says so.

Not present yet (do not assume): a generated lesson sat by a person (one was gone through
by a script; see "The real providers"), exporting a single course to share (not planned;
ADR-016), an installer, a signed build.

## Test results

Windows 11, Node 24.3.0, Python 3.12.11, Electron 45.4.1. One run of
`node scripts/check.mjs --e2e` on the tree that became the commits for ADR-027 to ADR-030,
on 2026-11-21.

| Gate | Status | Detail |
|---|---|---|
| Contracts up to date (API and Lesson IR schema) | PASS | `npm run contracts:check` |
| Scene name allowlist up to date | PASS | `npm run wanim-names:check` |
| Packaged scene guide up to date | PASS | `npm run scene-guide:check` |
| Nothing secret about to be committed | PASS | `npm run secrets:check` |
| Prettier | PASS | |
| ESLint (type-aware, a11y, hooks) | PASS | 0 warnings |
| TypeScript (`tsc`, 6 projects) | PASS | |
| Vitest | PASS | 666 tests, 33 files |
| ruff (lint + format) | PASS | |
| mypy (strict) | PASS | 95 source files |
| pytest | PASS | 1280 tests |
| Playwright + Electron (E2E) | PASS | 103 tests in 15 minutes, in one run of the gate for ADR-031 with no retry (two comments and the documents were edited after it). 22 of them run the sample course's scenes in both themes. Wherever a journey checks a screen for accessibility it now also checks that nothing pressable lies where the window is moved |
| Third-party licences (`npm run licenses:check`) | PASS | Part of the gate; 412 npm and 41 Python packages, none refused, none unstated |
| `npm audit` (all dependencies) | PASS | 0 vulnerabilities, 2026-11-21 |
| `pip-audit` (everything in `uv.lock`) | PASS | No known vulnerabilities, 2026-11-21 |
| GitHub Actions CI | NOT RUN | Workflow exists; repository has no remote |
| Packaged build: every journey (`npm run e2e:packaged`) | NOT RUN | for this tree (ADR-031). On the tree of `f68bdc8`, 2026-11-21: 100 passed and 1 passed on its second try, the race described under Findings |
| Packaged build: release start-up check (`npm run package:check`) | NOT RUN | for this tree |
| Packaged build on a computer that never had the project | NOT RUN | Needs another machine |
| Installer, code signing | BLOCKED | Need the owner's certificates |
| macOS / Linux | NOT RUN | Developed on Windows only. The window's own title bar (ADR-030) has been seen on Windows 11 only |
| Real AI providers | AIHubMix: BLOCKED. NVIDIA NIM: tried by hand, works | No test may call a real provider. AIHubMix: a relay error for one key; the other account must be topped up. NVIDIA: lessons, curricula and answers were written through Adle's own services on 2026-11-20; tried again after the way an answer is read was changed (ADR-029): a key check in 26 seconds and an answer to a question in 88, two requests. See "The real providers" |
| A lesson a real model wrote, in the app | PASS | By a script, 2026-11-21: a lesson written by Kimi K3.1 Pro, opened from its profile with no key, gone through in both themes from its first part to "Lesson complete", no error in the console. Not a person |

## Launch reliability (ADR-008)

While the window was created hidden and shown on `ready-to-show`, about 1 to 3 in 100 launches
driven by Playwright never produced a first frame: no `paint` entry, no animation frame,
`capturePage` timed out, and the window never appeared. Hiding and showing, resizing,
`invalidate()`, and reloading did not recover it. Measured with a launch loop:

| What the driver did (window created hidden) | Stalled |
|---|---|
| Called `show()` after the heading rendered, with early viewport emulation | 2 of 110 |
| Called `show()` after the heading rendered, no emulation | 3 of 50 |
| Waited for the app's own show, then focus only | 0 of 50 |
| Nothing at all | 0 of 40 |
| Early viewport emulation only | 0 of 60 |
| Waited for the app's own show, then emulation and focus | 1 of 80 |
| No driver attached (plain `electron -r` observer) | 0 of 40 |

No single test-side action explains it. The window is now created visible (`show: true`); with
that build the loop showed **0 stalls in 150 launches** and the E2E suite passed twice with no
flaky test. The E2E helper waits for the window, requests focus, and fails fast with a clear
message if the page is not painting. `retries: 1` stays on; a test reported as *flaky* is to be
investigated, not ignored.

## Findings worth knowing (all recorded in ADRs, nested AGENTS files, or the Wanim skill)

- **A value handed over by the page can carry functions of its own** (ADR-029). The preload
  once called `.map` on "the dropped files", and a page could have answered with any path.
  The preload calls no method of anything from the page.
- **"No network" is more than requests.** A peer connection reached listeners on this
  computer by UDP and TCP with every request refused. What stops it is no name lookups, a
  proxy that is nowhere and no UDP outside a proxy. A `webrtc` directive in the content
  security policy is not known to this Chromium: it stops nothing and logs an error on
  every page.
- **Anything that can be pressed and may lie along the top of the window must say
  `app-region: no-drag`** (ADR-030). A tall dialog reached under the strip the window is
  moved by; a test's clicks do not pass through the window's frame, so only a check of where
  things lie finds this.
- **`scrollbar-width` or `scrollbar-color` anywhere switches off the `::-webkit-scrollbar`
  parts**, and with them the look of every scroll bar.
- **`getByRole(..., { name: 'Answer' })` also finds "Answering your question".** A journey
  read the dialog before its answer was there. Short names take `exact: true`.
- **When many journeys fail for one reason** (a change of wording), run the files one at a
  time: the list reporter prints what failed only when a run ends. And look for the words a
  journey expects in the sources before running it: two small scripts did that in seconds
  where a run takes minutes.
- **`set_fill` and `set_color` take their arguments in order, without names, in Wanim
  0.1.3.** `set_fill(opacity=0.3)` stops a scene with "ManimColor only accepts ...", and
  `set_fill(colour, opacity=0.3)` runs and leaves the shape with no fill. A lesson a real
  model wrote lost its interactive picture to the first. The scene policy now refuses both
  (`unreliable_call`), which gives the model one more try with the reason; the guide says
  how to write them; `e2e/scene-player.spec.ts` reads the pixels. Found by sitting that
  lesson in the app, not by any test: the policy cannot see what a call does when it runs.
- **A test that waits longer than its stand-in holds out proves nothing.** The tests for
  "removing a lesson stops its pictures" passed with the stopping taken out: the held
  answer lets go by itself after twenty seconds and the tests waited thirty. They wait five
  and ten now. Take the fix out and watch the test fail before believing it.
- **A journey that misses once in a hundred is a race in the app as often as in the test.**
  One pressed "anything that says lesson" before a concept's lessons had loaded, and so
  pressed "Create a lesson with AI". The button no longer shows until the list is known.
- **A screenshot of the page is not the window.** The system's buttons, and how a dimmed
  page looks around them, show only in a picture of the window itself (`PrintWindow`).
- **A shell string is no place for a backslash.** A regular expression or `\n` passed
  through `node -e` or a here-document arrived changed, more than once. Patches are files.

- **A provider's reference is not its endpoint** (ADR-021). Kimi K3.1 Pro's documented
  default for `reasoning_effort` is not what it does when the field is left out: without it
  the model thought for eight minutes over a lesson and wrote nothing. Mistral Large 4
  refuses the value its reference lists and needs one it does not list. What works, and
  the date it was seen to, is written beside each model in `generation/provider.py`. Try a
  new field against the real endpoint by hand before relying on it.
- **A model writes TeX in JSON with one backslash as often as with two.** `\sigma` is then
  not JSON, and `\frac` is: a form feed and "rac". `drafts.mend_backslashes` mends an
  answer before it is parsed; do not parse a model's JSON any other way.
- **`set_opacity` fills a plotted curve.** The first interactive scene a real model wrote
  showed a curve as a solid shape for that reason. The scene guide says to use
  `set_stroke(opacity=...)`, and `e2e/scene-player.spec.ts` reads the window's own pixels
  to check both.
- **Real models take minutes.** A lesson's text: about five minutes from Kimi, seven and a
  half from Mistral. A scene: two to four. "Stop" and the time limit are checked on every
  line a provider sends, because the first piece of an answer arrives minutes in.
- Wanim 0.1.3 evaluates scenes in a same-origin child frame: needs `unsafe-eval` and a real origin.
- A scene stuck in a loop blocks its process; a new frame on the same origin never starts. Hence a
  fresh `adle://<id>.player` origin per frame.
- `preload_fonts` is typed but not exported; use `preload_submodules('fonts')`.
- `new URL('adle://…').origin` is `"null"` in Node. Use `adleOriginOf()`.
- Playwright forces a light colour scheme unless `colorScheme: null` is passed to `electron.launch`.
- On Linux, `safeStorage` may silently use a plaintext-equivalent backend; Adle refuses it.
- TypeScript 7 and ESLint 10 are not usable yet with the lint plugins (ADR-001).
- **Python `multiprocessing` hangs under the service on Windows** (the service blocks a thread on
  stdin, which a `multiprocessing` child inherits). Children are started with `subprocess` and
  explicit pipes (ADR-007). Unit tests parse in-process and cannot see this class of bug; the
  integration test that runs the real service can.
- SQLAlchemy URLs are built with `URL.create`, and SQLite URIs are percent-encoded: a profile
  folder may contain `#`, `%`, or `?`.
- `getByRole(..., { name })` matches substrings, and two controls may share a name (the
  navigation rail and a course's back button are both "Library"). Use `exact: true` and scope
  to a region.
- A `BrowserWindow` created with `show: false` can fail to paint its first frame (ADR-008).
- Vite inlines assets under 4 KB as `data:` URIs. One KaTeX font is that small, and the CSP
  (rightly) refused it. Both builds set `assetsInlineLimit: 0`. Found by an E2E test that
  asserts an empty console.
- React's lint rules (`react-hooks/immutability`, `refs`) reject writing to a ref received as
  a prop and reading refs in a `useState` initialiser. Long-lived non-React state goes in a
  small class created once (`openSession`, `SceneCues`).
- **A copy of a SQLite database made with the backup API is still in write-ahead mode.**
  Merely opening it, even read-only, creates a `-shm` and a `-wal` file beside it and leaves
  them there. Every copy is therefore switched to single-file mode before it is closed
  (`backup_database`); a test looks at the folder afterwards.
- `PRAGMA trusted_schema = OFF` does not break the triggers that keep the search index in
  step: FTS5 is marked harmless by SQLite. Checked with a probe before it was switched on,
  and by the whole suite since.
- The first version of a test for a guarantee can pass without testing it. The seven
  guarantees of ADR-016 were each removed from the code in turn and a test was seen to fail
  (a throwaway script outside the repository does this in a minute).
- Several notices of what a lesson request sends had left out the learner's goal, pace, depth
  of explanation, and the few words about where they stand on the concept. All of them now
  come from one function (`lessonDisclosure`), which is to be kept in step with
  `lesson_request` in the core.
- A long shell heredoc that contains an apostrophe can fail to parse under Git Bash. Patch
  scripts are written to a file and run from there.
- **Playwright's handle on a page does not survive that page's process crashing**, even after
  the window has reloaded ("Target crashed"). `e2e/recovery.spec.ts` reads the reloaded
  window through the main process with `webContents.executeJavaScript`, which works under
  the app's Content Security Policy.
- A self-marked answer is recorded as "unsure". The session summary first left such right
  answers out of its count, which read as a miscount beside "3 of 3 answers right"; the
  end-to-end journey showed it. They are counted, and named as lighter evidence (ADR-017).
- Patch scripts written in Python on Windows turn LF into CRLF unless they write with
  `newline="\n"`. Git normalises on commit, but the working tree is left mixed. Node's
  `writeFileSync` does not do this.
- A course's sample lesson has three questions; without more, a review can only repeat them.
  Lessons now carry up to eight further questions (`Lesson.practice`) for practice and review.
- On a question that is hard to guess, a slip of sign moves the estimate more than a right
  answer after a hint that gave the method away. That is intended (ADR-014) and tested.
- **In Wanim 0.1.3 a `Dot` given its position as an argument (`Dot(point, color=...)`) loses
  its colour and is drawn white**, which is invisible on the light stage. The shipped example
  had this too. A dot is created with keywords and then placed
  (`Dot(color=..., radius=...).move_to(point)`); the scene policy refuses the other form
  (`unreliable_call`) so that a generated scene cannot have it either. Found by looking at the
  screenshots the E2E suite takes of every scene.
- Text inside a scene is drawn in `ink` or `muted` only. The accent colours are for shapes:
  as text on the stage they do not have enough contrast in one theme or the other.
- The sample lessons are written by hand as JSON. A mistyped formula would fail nowhere (the
  player shows what it cannot typeset as written), so a unit test typesets every formula of
  every sample lesson and checks that narration, which is read aloud, contains no notation.
- An animation-only scene starts blank and is over in a few seconds, while its narration takes
  half a minute. Scenes follow the narration only at segment level today (start, pause, and a
  cue to leave a live page). Finer synchronisation needs Wanim's slides mode
  (`self.next_slide()`), which is documented upstream and not yet tested here.

## The real providers

Two providers (ADR-021). No test calls either: what follows was done by hand, with scripts
kept outside the repository that drive the core's own services, and is described so that it
can be done again.

### NVIDIA NIM: it works

Tried on 2026-11-20 with the owner's key, against
`https://integrate.api.nvidia.com/v1/chat/completions`. Requests that day: about thirty,
most of them small.

| What was asked for | By | Requests | Time | Outcome |
|---|---|---|---|---|
| A lesson on activation functions (sample course) | Kimi K3.1 Pro | 4 | 17.5 min | Nine segments, three checkpoints, two scenes. The first draft was refused (TeX with one backslash; now read), the second accepted. Both scenes passed the static policy as first written |
| A curriculum for "Probability for data analysis" | Kimi K3.1 Pro | 1 | 2 min | Twelve concepts, three objectives each, prerequisites that form a valid order; added without an issue |
| A lesson on gradient descent, after the fixes | Kimi K3.1 Pro | 2 | 8.7 min | Nine segments, one interactive scene; draft and scene each accepted as first written |
| A curriculum, with a first model that does not exist | Mistral Large 4 | 2 | 5 min | NVIDIA's own HTTP 404 for the absent model; Adle said so, asked Mistral, and recorded "… was not available, so Mistral Large 4 wrote this in its place" |

- All three generated scenes were then run in the isolated player, in both themes, with a
  one-off Playwright spec that is not in the suite: each loads, draws, and either finishes or
  waits for the learner with its controls announced.
- What the runs changed in the product: `reasoning_effort` for both thinking models; the
  reader that mends TeX backslashes, and a line in the prompt; a rule in the scene guide
  about showing a curve; "stop" and the time limit on every line; a refused request moving
  on to the next model; the job saying what the model is doing.
- GLM 5.3 Flash, the third in line, has not answered once: no line in three minutes, in
  three attempts. If the first two are both away, a request waits three minutes and fails.
- **One of these lessons was sat in the app from start to finish on 2026-11-21, by a
  script**: the profile the lesson was written into was opened in the app (a copy of it,
  with no key, so nothing was asked of anyone) and gone through part by part in both
  themes: ten parts, two questions answered and one skipped, the lesson finished, the
  course's next step shown, no error in the console. Its first picture played. Its second,
  the one to try, did not run: see "Findings" for why, and what now catches it. A person
  has still not learnt from one: the key has to be typed into Settings by the owner.

To do it again, from the repository root (the scripts are in the session's scratch folder,
`tools/`; they are described here because that folder does not last):

```bash
uv run --directory services/core python <scratch>/tools/real_smoke_nim.py nvidia <key file> <output dir> probe "lesson:Loss" curriculum
uv run --directory services/core python <scratch>/tools/nvidia_stream_diag.py <key file> <model id> <saved prompt> <answer file> usage effort=low
```

The first builds the real services on an empty profile, chooses the provider, puts the key
in the in-memory vault, and saves every prompt and answer. The second sends one saved prompt
to one model and prints, every twenty seconds, how much thinking and how much answer has
arrived: it is how the `reasoning_effort` findings were made.

### AIHubMix: still blocked at the provider

On 2026-11-19 the owner's key was valid (`GET /v1/models` lists exactly
`coding-kimi-k3-free`) but all nine completion requests failed with HTTP 500
`do_request_failed` (`Post "https://***/coding/v1/messages": Bad Request`): on both the
OpenAI-compatible and Anthropic-compatible endpoints, with the smallest possible body.
Retried on 2026-11-20 with the request printed on the model's own page: the same answer. So
the relay between AIHubMix and the model is refusing, for this key or for everyone; nothing
in Adle can be changed to fix it, and Adle was not made to pretend to be another program to
find out.

A second key, the same day: HTTP 200, and the text was the provider's own: "Sorry, to
prevent abuse of free resources, accounts that have not been recharged can only try 10
times. You can increase the free quota after recharging; https://console.aihubmix.com/topup".
With that account the model is reachable in principle, and what stands in the way is topping
the account up, which is the owner's to do. Adle recognises such an answer (`provider_notice`,
ADR-020): one request, the provider's words shown, the settings offered.

Tried again on 2026-11-20 through the new "automatic" choice, with keys for both providers
(`scripts/dev/real_provider_check.py`, see "Trying the real providers again"): AIHubMix
answered a check of its key and a question with the same notice; NVIDIA's Kimi K3.1 Pro
answered the check in 14 seconds and then **the question, in AIHubMix's place, in 64
seconds**, and the answer's record says "AIHubMix could not answer, so NVIDIA NIM wrote
this." That run is also why an account that refuses is now left alone for six hours, not
ten minutes: each try at it can be one of the ten the account allows.

New installations start on "automatic", which with one key is simply that provider. The
owner's description of AIHubMix as the quick one is written into its definition (`quick`)
and has not been observed: its model has never answered Adle.

### Trying the real providers again

    uv run --directory services/core python ../../scripts/dev/real_provider_check.py \
        --out <a folder outside the repository> \
        --aihubmix <file holding that key> --nvidia <file holding that key> \
        --selection auto check ask curriculum lesson

Keys are read from files and never printed. Every prompt and answer is saved under
`--out`, with which provider and model each request went to and how long it took, and the
data it leaves can be opened in the app (`ADLE_USER_DATA_DIR=<out>/profile`). No test runs
this, and it spends real allowance.

## Next actions

First, and not needing the owner:

- **The packaged builds have not been made from this tree** (ADR-031). `npm run package:test`,
  `npm run e2e:packaged`, `npm run package`, `npm run package:check`, then
  `node scripts/measure.mjs --packaged` for `PERFORMANCE.md`. (On the tree of `f68bdc8` the
  packaged build measured 0.37 s to the first screen, 1.15 s to the service, 0.31 s to open
  a lesson and 0.84 s to a scene's first frame; `PERFORMANCE.md` still shows the older
  figures.)
- **A picture shown small loses thin strokes.** Found on 2026-11-21 in a lesson Kimi K3.1
  Pro wrote (usable after 298 s, its one picture after 541 s; sat by a script in both themes
  with no error): `MathTex(r"L(w)=(w-2)^2", font_size=32)` showed as "(w 2)". The runtime
  draws every scene 1280 pixels wide and the browser shrinks the canvas to the 565 a lesson
  shows; shrunk by more than two, a thin stroke is dropped, not thinned. The fix that was
  begun and not finished or tested: `WanimPlayerAdapter` asks for a size to suit the frame
  (`-ql` under 640 device pixels wide, `-qh` over 1408, else `-qm`), and the frame's canvas
  fills the frame at any of them (`width: min(100vw, calc(100vh * 16 / 9))` in
  `player.css`). It needs unit tests, a journey that reads the pixels of thin lines at 565
  pixels, and a look at the sample scenes.

What else remains needs the owner. In the order it matters:

1. **Replace the keys that were pasted into the chat** (two for AIHubMix, two for NVIDIA).
   They are in a transcript; treat them as used. Then type the new keys into Settings → AI
   provider yourself, press "Test key" on each, leave the choice on Automatic, and **sit a
   generated lesson from start to finish**, asking it a question on the way. Through NVIDIA,
   expect about six minutes until the lesson can be started; the app offers a break and
   tells you when. Its pictures follow over the next few minutes and appear in it as they
   are drawn.
2. **Top up the AIHubMix account** (its notice says ten tries without one), or remove its
   key: until then Automatic finds out once that it refuses and uses NVIDIA.
3. **Push the branch** so that CI runs for the first time, on Windows and Linux (it now runs
   for `dev` too). Expect surprises on Linux: nothing has run there.
4. **Choose a licence, get signing certificates, and add an installer** (ADR-019 says what
   and why). `docs/engineering/RELEASE_CHECKLIST.md` is the list.
5. **Try the packaged folder on a computer that never had the project**, and on macOS, where
   the window's own title bar (ADR-030) has never been seen.
6. Decide whether GLM 5.3 Flash should stay NVIDIA's third model while it does not answer.
7. Still not built from the plan's section 12.1: **writing a lesson part by part.** Its text
   is one request and arrives whole, about five minutes through NVIDIA (ADR-012, ADR-031).
   That would need the draft format and the request budget to change together.
8. Smaller, by choice: Wanim's slides mode for narration in step with animation; exporting a
   single course; a screen-reader pass by a person.
9. From the review of 2026-11-20, left by decision (ADR-029, "Not done, and why"): a release
   build can still be started with Chromium's remote debugging switch; the page can ask for
   the data dialogs again and again; `provider.usage` is a route the interface does not
   call (five tests read it).

## Known gaps (tracked, not forgotten)

| Gap | Planned |
|---|---|
| A request the learner stopped is given up at once and hung up as well as that can be done from another thread; where it cannot, its connection is let go when the provider next says something (or its time runs out), so for a moment two may be open at one provider | By decision (ADR-023, ADR-029): the provider's turn is not kept waiting for a request nobody wants |
| The window's own title bar has been seen on Windows 11 only | Needs a Mac (ADR-030); Linux keeps its usual frame |
| A lesson's text is one request and arrives whole; the wait before a learner can begin is that request | By decision (ADR-012, ADR-031); "Next actions" 7 |
| A picture that arrives while a lesson is open is found by looking every three seconds, not by being told | By decision (ADR-031): nothing new crosses the bridge for it |
| A question asked during a lesson does not remember earlier questions | By decision (ADR-024): it is a note, not a chat |
| AIHubMix being "the quick one" is the owner's report, not a measurement | Its model has never answered Adle; one word in its definition if it turns out otherwise |
| GLM 5.3 Flash, NVIDIA's third model, has never answered | The owner's choice of order (ADR-021) |
| The parser worker has no OS-level sandbox | Not built. It is a separate, short-lived, isolated process that returns only checked JSON (SECURITY.md) |
| No installer, no signature, no automatic update; Windows only | Needs the owner (ADR-019, `RELEASE_CHECKLIST.md`) |
| A single course cannot be exported to share with someone else; a copy holds everything | By decision (ADR-016) |
| A saved copy is not encrypted | By decision (ADR-016); the interface says so |
| Narration and animation are synchronised per segment, not per sentence | M7, after testing Wanim's slides mode |
| Working memory from the plan is not a stored thing: what a session needs is rebuilt from attempts, observations, and `learner_events` on every request | By decision (ADR-014) |
| Open answers are self-assessed against a rubric, not graded by the model | By decision (ADR-014); revisit if the provider's allowance grows |
| Extraction quality on complex PDFs (columns, tables, equations) is whatever `pypdf` gives | When retrieval quality is evaluated |

## Open questions for the owner

- **Licence.** The repository is marked `UNLICENSED`. Choose a licence before publishing.
- **Commit signing.** Git is configured to GPG-sign commits. Signing needs the key's passphrase in
  the desktop session; agents cannot provide it. Settled on 2026-11-21: wait a few minutes for
  the prompt to be answered, then commit unsigned.
- **Vector search.** Not built: FTS5 covers the current need, and `sqlite-vec` plus a local
  embedding model adds packaging risk. Revisit with packaging in M8 unless retrieval quality
  proves insufficient earlier.
