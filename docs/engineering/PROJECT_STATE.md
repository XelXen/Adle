# Project state

The single place to find out where Adle stands and what to do next. Update it at the end of every
work session (see `AGENTS.md` → "Keeping the next agent oriented").

- **Last updated:** 2026-11-19
- **Branch:** `dev` (all work; `main` holds only the original plan commit until the owner merges)
- **Last commit:** see `git log -1`
- **Active milestone:** M5 — provider client, generation, narration
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
| M5 — Generation, audio, timeline | Not started | — |
| M6 — Assessment and adaptation | Not started | — |
| M7 — Complete UX and sample course | Not started | — |
| M8 — Release hardening | Not started | — |

## What works in the running app

- First launch → welcome with the local-first disclosure → library. Remembered across restarts.
- Navigation rail (collapses under 960 px), light/dark/system theme applied before first paint.
- **Library:** courses listed most recently used first; create a course from a topic or from
  materials; delete a course (with its files) after confirmation.
- **Course → Materials:** import PDF, Word, Markdown, and text files with the file dialog or by
  dropping them; progress while importing; per-file outcome (imported, already imported,
  rejected with a reason); extraction warnings; remove a source; search with file and page or
  section for every hit.
- **Course → Curriculum** (the tab a course opens on once it has materials or a topic): the
  concepts as a list in teaching order or as a map; add, edit, reorder, and remove concepts;
  learning objectives; what each concept needs first and why, with loops refused and explained;
  "Start from your materials" offers the headings of imported files as concepts; link a concept
  to passages in the materials; say how well you already know a concept and read back the record
  of everything noted about it.
- **Library → sample course:** "Try the sample course" adds "Introduction to neural networks"
  (eight concepts with objectives and reasons for every prerequisite) without a key.
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
  from the start with every part open and no question blocking.
- **When a scene cannot run:** if it fails in the player, or the core withholds it, the part
  shows its description in words and the lesson goes on.
- Settings → AI provider: save / replace / remove the key (OS-encrypted); provider facts from the core.
- Settings → Learning: pace, explanation depth, narration, captions, goal (stored by the core).
- Settings → Privacy & data: what is stored, what is sent.
- Settings → About & diagnostics: core status and restart; live scene runtime check with a mirrored,
  keyboard-operable slider.
- Python core starts as a supervised child, authenticates with a per-launch token, migrates its
  database (with a backup first), and exits with the app.

Not present yet (do not assume): spoken narration (captions only), provider calls (so no
generated lessons and no AI-proposed curriculum), lessons for the other seven sample concepts,
misconception handling, a chosen next step, review sessions, a progress screen, export and
restore in the interface, packaging.

Built and tested but not yet reachable from the interface: `restore_database`
(`infrastructure/migrate.py`). The restore screen arrives with export in M7.

## Test results

Windows 11, Node 24.3.0, Python 3.12.11, Electron 45.4.1. One run of
`node scripts/check.mjs --e2e` on the tree that became the M4 commit.

| Gate | Status | Detail |
|---|---|---|
| Contracts up to date (API and Lesson IR schema) | PASS | `npm run contracts:check` |
| Scene name allowlist up to date | PASS | `npm run wanim-names:check` |
| Prettier | PASS | |
| ESLint (type-aware, a11y, hooks) | PASS | 0 warnings |
| TypeScript (`tsc`, 6 projects) | PASS | |
| Vitest | PASS | 304 tests, 15 files |
| ruff (lint + format) | PASS | |
| mypy (strict) | PASS | 70 source files |
| pytest | PASS | 665 tests |
| Playwright + Electron (E2E) | PASS | 45 tests, none flaky |
| `npm audit` (all dependencies) | NOT RUN | Last run before KaTeX was added; run again before release |
| GitHub Actions CI | NOT RUN | Workflow exists; repository has no remote |
| Packaged build | BLOCKED | No packager chosen yet (M8) |
| macOS / Linux | NOT RUN | Developed on Windows only |
| Real AI provider | NOT RUN | No request has been sent yet; tests never will |

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
- An animation-only scene starts blank and is over in a few seconds, while its narration takes
  half a minute. Scenes follow the narration only at segment level today (start, pause, and a
  cue to leave a live page). Finer synchronisation needs Wanim's slides mode
  (`self.next_slide()`), which is documented upstream and not yet tested here.

## Next actions (M5), in order

1. **Provider client and quota** (started, not yet wired in): `generation/quota.py` (pure rules,
   tested) and `generation/provider.py` (one streamed chat completion, tested against a mock
   transport). Still to do: a `model_usage` table and migration, a gateway that applies the
   quota, waits or refuses, records usage, and retries once after a 429; `provider.usage`.
2. **Generation as jobs:** a forgiving draft format the model writes, compiled deterministically
   into the Lesson IR (ids, objective links, citations only from passages that were supplied);
   one request for the lesson, one per scene (at most one retry when the static policy rejects
   a file, and a segment that loses its scene becomes an explanation); a curriculum proposal the
   learner reviews before anything is added.
3. **Fake provider** for unit tests (mock transport) and for E2E (a local HTTP server, reached
   through `ADLE_PROVIDER_BASE_URL`). No test calls the real provider.
4. **Interface:** propose a curriculum; create a lesson with progress and cancel; usage estimate
   in Settings; clear states for no key, rate limited, quota used up, and failure.
5. **Narration aloud** through the operating system's voices (Web Speech API, local voices only)
   behind the existing `Narrator` interface, with word highlighting only where the engine
   reports word boundaries, a voice and volume setting, and the silent captions as fallback.
6. **A few real requests** (owner's key, read from outside the repository, never typed into the
   app by an agent) to check the prompts against the real model. Record usage here.

Then M6 (misconceptions, next-step policy with reasons, review queue, progress screen,
rubric-bounded grading), M7 (the rest of the sample course, export / restore / delete, polish),
M8 (packaging, hardening).

## Known gaps (tracked, not forgotten)

| Gap | Planned |
|---|---|
| The main process does not handle a renderer crash (`render-process-gone`); the learner would see an empty window | M8 (start-up and shutdown failure matrix) |
| The parser worker has no OS-level sandbox | M8, with packaging (SECURITY.md) |
| Restore and export exist in code or are planned but have no screen | M7 |
| Only one of the eight sample concepts has a lesson | M7 |
| A lesson returns to the first concept of the course, not the one it taught, and nothing suggests what to do next | M6 (next-step policy) |
| Narration and animation are synchronised per segment, not per sentence | M7, after testing Wanim's slides mode |
| The interaction event log and working memory from the plan are not stored; attempts and observations are | M6 |
| Extraction quality on complex PDFs (columns, tables, equations) is whatever `pypdf` gives | When retrieval quality is evaluated |

## Open questions for the owner

- **Licence.** The repository is marked `UNLICENSED`. Choose a licence before publishing.
- **Commit signing.** Git is configured to GPG-sign commits. Signing needs the key's passphrase in
  the desktop session; agents cannot provide it. A commit made while the passphrase prompt is
  unanswered simply waits.
- **Vector search.** Not built: FTS5 covers the current need, and `sqlite-vec` plus a local
  embedding model adds packaging risk. Revisit with packaging in M8 unless retrieval quality
  proves insufficient earlier.
