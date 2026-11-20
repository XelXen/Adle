# Project state

The single place to find out where Adle stands and what to do next. Update it at the end of every
work session (see `AGENTS.md` → "Keeping the next agent oriented").

- **Last updated:** 2026-11-20
- **Branch:** `dev` (all work; `main` holds only the original plan commit until the owner merges)
- **Last commit:** see `git log -1`
- **Active milestone:** M8 — release hardening, done as far as this machine can take it:
  failure handling (ADR-018), packaging (ADR-019), the licence inventory, the audits, the
  performance report, and the release checklist. Since then: a second AI provider, NVIDIA
  NIM, beside AIHubMix (ADR-021), through which **a real model has written lessons for the
  first time**; and, at the owner's request on 2026-11-20: a new look (ADR-022) in Geist
  (ADR-025), both providers used together (ADR-023), questions asked during a lesson
  (ADR-024), and a break while a lesson is written (ADR-026). What is left needs the owner;
  see "Next actions"
- **Commits:** every commit is GPG-signed and waits for the owner's passphrase prompt. If
  `git log` is behind the working tree, a `pinentry` window is waiting on the desktop.

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
- **Library:** courses listed most recently used first; create a course from a topic or from
  materials; delete a course (with its files) after confirmation.
- **Course → Materials:** import PDF, Word, Markdown, and text files with the file dialog or by
  dropping them; progress while importing; per-file outcome (imported, already imported,
  rejected with a reason); extraction warnings; remove a source; search with file and page or
  section for every hit.
- **Course → Learn** (the tab a course with concepts opens on): one suggested next step with
  the reason for it, the alternatives ("Or instead"), a note that stopping is fine when things
  are going badly, and each concept in learning order with its state in words, what is still
  missing, when it is next reviewed, and what Adle has noticed about it.
- **Hypotheses:** two answers pointing the same way show as "Seen more than once" with a
  sentence; one answer shows as "Suspected, not established". "That was a slip" sets one aside.
  A slip of sign shows as a slip and is counted as partly right.
- **Practice and review:** a few questions on one concept, with why these questions, answered
  and explained as in a lesson, then a summary and what to do next. Nothing answered in the
  last twelve hours is asked again; if nothing can be asked, the screen says when it can.
- **Reviews:** scheduled by the core after answers; due ones are suggested first among routine
  steps and marked on the concept. Doing one moves the next further away.
- **The session summary** (Learn tab, under the suggested step): "This session" while the
  learner may still be in it, "Last time, yesterday" and the like afterwards. Lessons finished
  and questions answered; for each concept worked on, how many answers were right (with any
  that were lighter evidence named, and one sentence saying what that means), what is still
  needed in the concept's own words, and when its review comes. No score, and wrong answers
  are not listed.
- **"This did not help"** in a lesson: skip to the next question, have the concept explained
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
  "Your answer" / "The right answer".
- **Resume and review:** a lesson reopens at the part where it was left; a finished one reopens
  from the start with every part open and no question blocking. A finished lesson ends with
  what to do next.
- **When a scene cannot run:** if it fails in the player, or the core withholds it, the part
  shows its description in words and the lesson goes on.
- **Suggested concepts:** "Suggest concepts with AI" on the curriculum says what will be sent,
  runs as a job with progress and Cancel, and ends in a review dialog where the learner picks
  what to add. Suggestions that finish while the learner is elsewhere wait to be reviewed or
  discarded. Nothing is added without the learner choosing it.
- **Generated lessons:** "Create a lesson with AI" on a concept (and "Create the lesson" on
  the Learn tab) says what is sent and what it costs of the day's requests, shows progress and
  Cancel, and adds a lesson that plays like any other. For another lesson on the same concept
  the learner can choose how it should explain; left alone, Adle uses a way not used yet. A
  concept has at most four lessons. No key, a rate-limit wait, a used-up day, a provider failure, and a cancelled job each
  have their own words and their own way forward. While a model is at work the job says
  what it is doing ("Writing the lesson: Kimi K3.1 Pro is thinking it through", then "is
  writing"): the models that work today take minutes over one answer.
- **Which model wrote it:** if a provider's first model is not available, its next one is
  asked, and that is said while it happens ("Kimi K3.1 Pro is not available at the moment.
  Asking Mistral Large 4 instead") and afterwards: in the notice that a lesson is ready, and
  in the review of suggested concepts, which names its author ("Suggested by Mistral Large 4
  on NVIDIA NIM").
- **Narration aloud:** the lesson is read by a voice installed on the computer (never an online
  one), with "Read aloud" and "Transcript" switches in the lesson. Without a voice, or if the
  voice fails, the narration is shown as text at the learner's reading pace.
- Settings → AI provider: **"Which provider to use": Automatic, AIHubMix only, or NVIDIA
  NIM only.** Automatic uses every provider that has a key, each for what it is best at:
  what is waited for (a question, a list of concepts) goes to the quick one, long work (a
  lesson) to the roomy one once the quick one is half used for the day, and the other is
  asked when one cannot answer. "Where requests go now" shows the plan for each kind of
  request and the reason. The choice is changed only there, and not while something is
  being written. Below it, a card for each provider: its address, its models in the order
  they are asked, its key (save, replace, remove; OS-encrypted; kept for one provider at one
  address and never sent anywhere else), **"Check that it works"** (one word from that
  provider, nothing of the learner's sent), and how much of today's allowance is used
  there, with a sentence saying whether the limits are the provider's or Adle's own.
- **Asking a question during a lesson:** "Ask a question" in the lesson's bar pauses the
  lesson and opens a dialog: the learner's own words or a ready-made question, what will
  be sent and where, and "Ask". The answer is kept beside that part under "Your questions
  about this part", says who wrote it, and can be removed. The learner can carry on with
  the lesson while it is written. On a question the lesson is asking, Adle helps without
  giving the answer, and the answer that follows counts as an aided one.
- **Waiting:** where something is being written, the app says about how long it usually
  takes, that the learner need not watch, and offers **a break**: one clock sized to the
  wait, a small idea of what to do away from the screen, and what is being written
  meanwhile. The rail shows "Now": what is being written and a running break. When it is
  ready the app says so, and so does the operating system (fixed words, only while Adle is
  in the background; can be turned off in Settings → Appearance). A break is also offered
  at the end of a lesson. Nothing about breaks is counted or kept.
- "Cancel" and "Stop" take effect at once, however silent the provider is.
- **Library:** opens with "Pick up where you left off": the suggested next step of the
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
- Settings → About & diagnostics: core status and restart; live scene runtime check with a mirrored,
  keyboard-operable slider; "Show log files" opens the folder of local logs.
- **When the app itself fails** (ADR-018): a page that crashes or hangs, and an error nobody
  caught in the main process, each bring a plain message from the operating system with a way
  on (reload, wait, restart, quit); a core that dies is started again, at most twice in five
  minutes. Each is noted in `logs/app.log` on this computer. Nothing is reported anywhere.
- Python core starts as a supervised child, authenticates with a per-launch token, migrates its
  database (with a backup first), and exits with the app.
- **As a packaged app** (`npm run package`): a folder with `Adle.exe`, the app in an archive,
  and a private Python for the core that takes nothing from the computer it is on. Everything
  above works in it; the end-to-end suite says so.

Not present yet (do not assume): a generated lesson sat by a person in the app (see "The real
providers"), exporting a single course to share (not planned; ADR-016), an installer, a
signed build.

## Test results

Windows 11, Node 24.3.0, Python 3.12.11, Electron 45.4.1. One run of
`node scripts/check.mjs --e2e` on the tree that became the commits for ADR-021, on 2026-11-20.

| Gate | Status | Detail |
|---|---|---|
| Contracts up to date (API and Lesson IR schema) | PASS | `npm run contracts:check` |
| Scene name allowlist up to date | PASS | `npm run wanim-names:check` |
| Packaged scene guide up to date | PASS | `npm run scene-guide:check` |
| Prettier | PASS | |
| ESLint (type-aware, a11y, hooks) | PASS | 0 warnings |
| TypeScript (`tsc`, 6 projects) | PASS | |
| Vitest | PASS | 531 tests, 25 files |
| ruff (lint + format) | PASS | |
| mypy (strict) | PASS | 89 source files |
| pytest | PASS | 1130 tests |
| Playwright + Electron (E2E) | PASS | 88 tests in 12 minutes, none flaky. 22 of them run the sample course's scenes in both themes |
| Third-party licences (`npm run licenses:check`) | PASS | Part of the gate; 411 npm and 41 Python packages, none refused, none unstated |
| `npm audit` (all dependencies) | PASS | 0 vulnerabilities, 2026-11-20 |
| `pip-audit` (everything in `uv.lock`) | PASS | No known vulnerabilities, 2026-11-20 (pip-audit 2.10.1) |
| GitHub Actions CI | NOT RUN | Workflow exists; repository has no remote |
| Packaged build: every journey (`npm run e2e:packaged`) | PASS, one flaky | 88 tests against the rebuilt packaged app in 10 minutes. One, the pointer drag in `scene-player.spec.ts`, missed its first try and passed its retry, while a real-provider script was running on the same machine; run on its own afterwards it passed 8 times of 8 with no retries |
| Packaged build: release start-up check (`npm run package:check`) | PASS | Fuses, will not run as Node, starts on an empty profile with a stripped environment, no orphaned core |
| Packaged build on a computer that never had the project | NOT RUN | Needs another machine |
| Installer, code signing | BLOCKED | Need the owner's certificates |
| macOS / Linux | NOT RUN | Developed on Windows only |
| Real AI providers | AIHubMix: BLOCKED. NVIDIA NIM: tried by hand, works | No test may call a real provider. AIHubMix: a relay error for one key; the other account must be topped up. NVIDIA: two lessons with three scenes and two curricula were written through Adle's generation service on 2026-11-20, one of them by the stand-in model; see "The real providers" |

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
- Not done: nobody has sat one of these lessons in the app. The key has to be typed into
  Settings by the owner; automation does not enter credentials.

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

What remains needs the owner. In the order it matters:

1. **Replace the keys that were pasted into the chat** (two for AIHubMix, two for NVIDIA).
   They are in a transcript; treat them as used. Then type the new keys into Settings → AI
   provider yourself, press "Check that it works" on each, leave the choice on Automatic,
   and **sit a generated lesson from start to finish**, asking it a question on the way.
   Expect about twelve minutes for a lesson to be written by NVIDIA; the app will offer a
   break and tell you when it is ready.
2. **Top up the AIHubMix account** (its notice says ten tries without one), or remove its
   key: until then Automatic finds out once that it refuses and uses NVIDIA.
3. **Push the branch** so that CI runs for the first time, on Windows and Linux (it now runs
   for `dev` too). Expect surprises on Linux: nothing has run there.
4. **Choose a licence, get signing certificates, and add an installer** (ADR-019 says what
   and why). `docs/engineering/RELEASE_CHECKLIST.md` is the list.
5. **Try the packaged folder on a computer that never had the project**, and on macOS.
6. Decide whether GLM 5.3 Flash should stay NVIDIA's third model while it does not answer.
7. The largest thing still not built from the plan: **opening a lesson as soon as its words
   are ready**, with the pictures arriving while the learner studies (PROMPT.md 3, PLAN 12.1).
   The break makes the wait easier; this would shorten it from about twelve minutes to five.
8. Smaller, by choice: Wanim's slides mode for narration in step with animation; exporting a
   single course; a screen-reader pass by a person; showing on a lesson, not only on its
   job, which model wrote it.

## Known gaps (tracked, not forgotten)

| Gap | Planned |
|---|---|
| A request the learner stopped is given up at once, but its connection is only let go when the provider next says something (or its time runs out), so for a moment two may be open at one provider | By decision (ADR-023): closing a connection from another thread is not dependable across platforms |
| A lesson appears only when all of it is written, pictures included | Not built (ADR-026, "Next actions" 7) |
| A question asked during a lesson does not remember earlier questions | By decision (ADR-024): it is a note, not a chat |
| AIHubMix being "the quick one" is the owner's report, not a measurement | Its model has never answered Adle; one word in its definition if it turns out otherwise |
| Which model wrote a lesson is kept with the job that made it, not with the lesson | When someone wants to see it later than the notice |
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
  the desktop session; agents cannot provide it. A commit made while the passphrase prompt is
  unanswered simply waits.
- **Vector search.** Not built: FTS5 covers the current need, and `sqlite-vec` plus a local
  embedding model adds packaging risk. Revisit with packaging in M8 unless retrieval quality
  proves insufficient earlier.
