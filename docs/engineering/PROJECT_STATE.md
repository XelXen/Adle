# Project state

The single place to find out where Adle stands and what to do next. Update it at the end of every
work session (see `AGENTS.md` → "Keeping the next agent oriented").

- **Last updated:** 2026-11-20
- **Branch:** `dev` (all work; `main` holds only the original plan commit until the owner merges)
- **Last commit:** see `git log -1`
- **Active milestone:** M8 — release hardening, done as far as this machine can take it:
  failure handling (ADR-018), packaging (ADR-019), the licence inventory, the audits, the
  performance report, and the release checklist. What is left needs the owner or the
  provider; see "Next actions"
- **Commits:** every commit is GPG-signed and waits for the owner's passphrase prompt. If
  `git log` is behind the working tree, a `pinentry` window is waiting on the desktop.

## Milestone status

| Milestone | Status | Evidence / what is missing |
|---|---|---|
| M0 — Foundation | **Done** | Workspace, pinned toolchain, lint/type/test gates, docs, ADR process, CI workflow written. CI itself is NOT RUN (no remote yet). |
| M1 — Desktop shell and Sprout | **Done** | App launches without a key; welcome, library, settings; key add/remove without exposure; themes; a11y gates. |
| M2 — Persistence and ingestion | **Done** | Database with safe migrations, backup and restore; import of PDF, DOCX, Markdown, text with provenance; duplicate detection; FTS5 search; course and materials screens. Vector search deliberately not built (ADR-007). |
| M3 — Curriculum and learner model | **Done** | Concept graph validated on every write (loops, references, order, layers); curriculum screen (list and map; add, edit, reorder, remove; objectives; prerequisites with reasons; links to materials; outline from headings); learner preferences; knowledge as an append-only record folded through BKT into four states with reasons; review scheduling; retrieval with provenance (ADR-009). **Deferred to the lesson work:** working memory and the interaction event log. Answer evidence is exercised through the service in tests; in the app only self-rating can create evidence until questions exist. |
| M4 — Wanim and Lesson IR | **Done** | Player frame, adapter, static scene policy, skill, threat model (ADR-004). Lesson IR 1.0 with a generated JSON Schema; one validating gateway; scenes re-checked on every read; answer keys kept in the core with deterministic scoring; the lesson player; the first lesson of the sample course (ADR-010). The packaged-build check is BLOCKED on M8 packaging. |
| M5 — Generation, audio, timeline | **Done** (real provider BLOCKED) | Provider client, quota, and gateway; curriculum proposals and lessons as cancellable jobs compiled into the Lesson IR (ADR-012); the interface for both with every failure state; narration aloud through the computer's own voices (ADR-013). Every path is tested against a fake provider. **The real model has not produced a lesson yet:** the provider failed every request upstream on 2026-11-19, so the prompts are unchecked. |
| M6 — Assessment and adaptation | **Done** | Hypotheses about mistakes computed from the record (tentative, supported, rejected, resolved), checked with questions that would show them, and dismissible by the learner; slips counted as partly right; repeats counted in full only after a gap; questions kept for practice in the Lesson IR; a next-step policy with a reason for every step; the Learn tab, practice and review, "what next" after a lesson, "This did not help"; teaching strategy chosen or rotated (ADR-014). Not built by decision: model grading of open answers and model-proposed hypotheses. |
| M7 — Complete UX and sample course | **Done** (two items left as known gaps) | Done: every one of the eight sample concepts has a lesson with scenes, questions tagged with the mistakes their wrong options point at, and practice questions; every lesson is played from start to finish and every scene is run in both themes by the E2E suite. Also done: Settings → Privacy & data can save a copy of everything as one file, restore from one (checked and upgraded before anything is replaced; what is replaced is kept; undoable), and delete everything (ADR-016). Also done: the session summary (ADR-017). Polish done: every outcome of the new screens checked with axe, focus kept after "That was a slip". Left as known gaps, by decision: narration and animation are synchronised per segment (Wanim's slides mode was not tried), and screenshots are saved for review rather than compared against baselines. |
| M8 — Release hardening | **In progress** | Done: a crashed or hung page, an uncaught error in the main process, and a core that dies are each handled, with a local log and no reporting (ADR-018). Packaging (ADR-019): a folder that runs by itself, with a private Python for the core, fuses set; the whole end-to-end suite passes against the packaged app, and the release build passes a start-up check from outside. Licence inventory generated and checked in every gate; `npm audit` and `pip-audit` clean; `PERFORMANCE.md` and `RELEASE_CHECKLIST.md` written. **Not done, and not doable here:** an installer and code signing (the owner's certificates), macOS and Linux (no machine), a clean computer, a lesson from the real model (provider). |

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
  have their own words and their own way forward.
- **Narration aloud:** the lesson is read by a voice installed on the computer (never an online
  one), with "Read aloud" and "Transcript" switches in the lesson. Without a voice, or if the
  voice fails, the narration is shown as text at the learner's reading pace.
- Settings → AI provider: save / replace / remove the key (OS-encrypted); provider facts from the
  core; how much of today's request and token allowance is used and when it resets.
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

Not present yet (do not assume): a lesson written by the real model (see "The real provider"),
exporting a single course to share (not planned; ADR-016), an installer, a signed build.

## Test results

Windows 11, Node 24.3.0, Python 3.12.11, Electron 45.4.1. One run of
`node scripts/check.mjs --e2e` on the tree that became the commit for ADR-019, on 2026-11-20.

| Gate | Status | Detail |
|---|---|---|
| Contracts up to date (API and Lesson IR schema) | PASS | `npm run contracts:check` |
| Scene name allowlist up to date | PASS | `npm run wanim-names:check` |
| Packaged scene guide up to date | PASS | `npm run scene-guide:check` |
| Prettier | PASS | |
| ESLint (type-aware, a11y, hooks) | PASS | 0 warnings |
| TypeScript (`tsc`, 6 projects) | PASS | |
| Vitest | PASS | 497 tests, 23 files |
| ruff (lint + format) | PASS | |
| mypy (strict) | PASS | 88 source files |
| pytest | PASS | 1035 tests |
| Playwright + Electron (E2E) | PASS | 83 tests in 12 minutes, none flaky. 22 of them run the sample course's scenes in both themes |
| Third-party licences (`npm run licenses:check`) | PASS | Part of the gate; 411 npm and 41 Python packages, none refused, none unstated |
| `npm audit` (all dependencies) | PASS | 0 vulnerabilities, 2026-11-20 |
| `pip-audit` (everything in `uv.lock`) | PASS | No known vulnerabilities, 2026-11-20 (pip-audit 2.10.1) |
| GitHub Actions CI | NOT RUN | Workflow exists; repository has no remote |
| Packaged build: every journey (`npm run e2e:packaged`) | PASS | 83 tests against the packaged app, none flaky |
| Packaged build: release start-up check (`npm run package:check`) | PASS | Fuses, will not run as Node, starts on an empty profile with a stripped environment, no orphaned core |
| Packaged build on a computer that never had the project | NOT RUN | Needs another machine |
| Installer, code signing | BLOCKED | Need the owner's certificates |
| macOS / Linux | NOT RUN | Developed on Windows only |
| Real AI provider | BLOCKED | The provider fails every request upstream (HTTP 500 `do_request_failed`); see "The real provider" |

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

## The real provider

**BLOCKED at the provider.** On 2026-11-19 the owner's key was valid (`GET /v1/models` lists
exactly `coding-kimi-k3-free`) but all nine completion requests failed with HTTP 500
`do_request_failed` (`Post "https://***/coding/v1/messages": Bad Request`): on both the
OpenAI-compatible and Anthropic-compatible endpoints, with the smallest possible body. That is
AIHubMix's call to its upstream failing, not the request. The prompts
(`generation/prompts.py`) are therefore unchecked against the real model. To retry, from the
repository root:

```bash
uv run --directory services/core python <scratch>/tools/real_smoke.py <key file> <output dir> probe
```

(The script lives outside the repository on purpose; it is described in ADR-012. Nine of the
day's 80 budgeted requests were used on 2026-11-19.) When it answers: run it with `curriculum`
and `lesson`, read what the model actually writes, and adjust the prompts and the leniency of
`generation/drafts.py` to it. Do not loosen the Lesson IR or the scene policy to fit the model.

**Retried on 2026-11-20: still BLOCKED, and it is not the request.** Two requests were sent.
Adle's own client got the same HTTP 500. Then the request shown on the model's own page
(`https://aihubmix.com/model/coding-kimi-k3-free`: one user message, `max_tokens` 1024, not
streamed, to `/v1/chat/completions`) was sent as it stands, and got the same answer:
`do_request_failed`, `Post "https://***/coding/v1/messages": Bad Request`. The provider's
documentation names no required header, no restriction to particular clients, and no outage
for this model. So the relay between AIHubMix and the model is refusing, for this key or for
everyone; nothing in Adle can be changed to fix it, and Adle was not made to pretend to be
another program to find out. For the owner: ask AIHubMix about that error with this model,
or try the key in their own playground. In the app this state is handled: the job ends with
"The AI provider reported a problem on its side. Nothing was changed; try again in a little
while", nothing is saved, and no request is repeated.

## Next actions

Everything that could be done on this machine without the owner is done. What remains, in
the order it matters:

1. **Retry the real provider** (see "The real provider") and, when it answers, read what the
   model actually writes and adjust the prompts and the leniency of `generation/drafts.py`.
   This is the one part of the product no test has exercised for real.
2. **Push the branch** so that CI runs for the first time, on Windows and Linux. Expect
   surprises on Linux: nothing has run there.
3. **Choose a licence, get signing certificates, and add an installer** (ADR-019 says what
   and why). `docs/engineering/RELEASE_CHECKLIST.md` is the list.
4. **Try the packaged folder on a computer that never had the project**, and on macOS.
5. Smaller, by choice: Wanim's slides mode for narration in step with animation; exporting a
   single course; a screen-reader pass by a person.

## Known gaps (tracked, not forgotten)

| Gap | Planned |
|---|---|
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
