# Testing

How Adle is tested, how to run each layer, and what is not covered yet.

Statuses used here and in `docs/engineering/PROJECT_STATE.md`:
**PASS** (ran and passed), **FAIL** (ran and failed), **NOT RUN**, **BLOCKED** (could not run; says why).
A result is never reported from reading code.

## Quick reference

| Command | Runs | Time |
|---|---|---|
| `npm run check` | Contract and allowlist drift, Prettier, ESLint, `tsc`, Vitest, ruff, mypy, pytest | ~1 min |
| `node scripts/check.mjs --e2e` | All of the above, then builds and runs the Electron suite | ~5 min |
| `npm test` | Vitest (TypeScript unit and component tests) | ~3 s |
| `npm run core:test` | pytest (Python unit and integration tests) | ~30 s |
| `npm run e2e` | Build, then Playwright against the real Electron app | ~4 min |

Single targets:

```bash
npx vitest run packages/event-protocol
```

```bash
uv run --directory services/core pytest tests/unit/test_scene_policy.py -k hostile
```

```bash
npm run e2e -- security.spec.ts
```

## Layers

### 1. Unit and component (Vitest)

`vitest.config.ts` defines two projects: `node` (main process, pure logic) and `dom` (jsdom, React).
Tests sit beside the code as `*.test.ts(x)`.

| Area | File | Covers |
|---|---|---|
| Player protocol | `packages/event-protocol/src/index.test.ts` | Every message shape; rejection of unknown fields, types, sizes, event names; origin helpers |
| Design tokens | `packages/design-system/src/tokens.test.ts` | WCAG contrast for 30 pairs × 2 themes; dark theme completeness; scene palette sync; no raw colours in stylesheets |
| Components | `packages/design-system/src/components/components.test.tsx` | Roles, names, keyboard patterns, loading/disabled/invalid states, toast timing |
| Frame clock | `apps/desktop/player/frame/src/frame-clock.test.ts` | Pause holds frames, resume releases, cancel, native clock |
| Control mirroring | `apps/desktop/player/frame/src/controls.test.ts` | Reading `adle_controls`, clamping, type checks, cap |
| Player adapter | `apps/desktop/player/host/WanimPlayerAdapter.test.ts` | Status machine, origin/window/run filtering, timeouts, watchdog, fresh origin after failure |
| Main: boundaries | `apps/desktop/electron/main/security-boundaries.test.ts` | Path traversal, host routing, CSP contents, request/navigation filters, trusted sender, invoke validation, window preferences |
| Main: local state | `apps/desktop/electron/main/local-state.test.ts` | Key validation, encrypted store, Linux fallback refusal, UI state, launch spec |
| Main: imports | `apps/desktop/electron/main/imports.test.ts` | Course id shape; import paths must be absolute, bounded, NUL-free; no echo of submitted paths |
| Main: when the app fails | `apps/desktop/electron/main/recovery.test.ts` | A crashed page is reloaded or the app quit, as the learner chooses, and a clean exit says nothing; a hung page is left alone by default; an uncaught error restarts or quits and **never restarts into a failure at start-up**; a stray rejection is only noted; one question at a time; every message says the work is safe and contains no jargon; a core that died is started again at most twice in five minutes. The local log: one JSON line per event, long values cut, starts afresh at its limit, never throws |
| Main: the data as a whole | `apps/desktop/electron/main/data-copy.test.ts`, `data.test.ts` | Where a copy may be saved (never inside the data folder; the ending added but never over another file); what may be restored; which folder may be deleted. The handlers with Electron replaced: each dialog's answer, only a file name returned, the core's refusal passed on, **the folder deleted while the core is held stopped and before anything may start it**, a core that does not come back, one action at a time |
| Data actions in the interface | `apps/desktop/renderer/src/lib/data-actions.test.ts` | Backing out says nothing; what is said after saving, restoring, and deleting; a failure is titled for what did not happen and keeps its reason |
| Curriculum screen logic | `apps/desktop/renderer/src/screens/course/curriculum-model.test.ts` | Path order; which neighbour swaps prerequisites allow and the reason given; dependents; map layout (rows, wrapping, no overlap, links); grouped warnings |
| Lesson playback | `apps/desktop/renderer/src/lesson/controller.test.ts` | Nothing plays unasked; beats in turn; pause and resume through the narrator; late callbacks ignored; a question blocks once and only once; jumping only to reached parts; skipping to the next question without passing an unanswered one; resume and review; finishing; the silent narrator's clock |
| Scene cues | `apps/desktop/renderer/src/lesson/scene-cues.test.ts` | A cue is kept until its segment's scene is holding, delivered once, never to another segment, and not kept for a later visit |
| Answers | `apps/desktop/renderer/src/lesson/answers.test.ts` | Reading a typed number (decimal comma, fractions, typographic minus) without guessing; the request built for each question form; what is still missing |
| Speech | `apps/desktop/renderer/src/lesson/speech.test.ts` | Only local voices; waiting for the voice list; the voice for the lesson's language over the system default; the voice as the clock; word positions only from the engine; pause, resume, cancel; a stand-in when the voice fails |
| Generation results | `apps/desktop/renderer/src/lib/generation.test.ts` | Reading a proposal or a lesson outcome from a job's free-form result; progress; which remedy each failure gets |
| Next step and progress | `apps/desktop/renderer/src/lib/learning.test.ts` | The session summary in words ("This session", or "Last time" with its day; counts of what was done; right answers with any lighter evidence named and never as a share). Where each kind of suggested step leads (a lesson, questions, the settings when a key is missing, nowhere); waits and reviews in everyday words; counts of concepts that are never a score; how a hypothesis is labelled; how a set of questions is summed up |
| Mathematics | `apps/desktop/renderer/src/components/MathText.test.tsx` | Splitting text and `$…$`; KaTeX output with MathML; text that does not parse is shown as written |
| Sample course content | `apps/desktop/renderer/src/components/sample-content-math.test.ts` | Every formula in every sample lesson typesets with the player's own options; no formula is left unclosed; narration, which is read aloud, contains no notation; there are eight lessons |
| Main: core | `apps/desktop/electron/main/core/core.test.ts` | Supervisor against a fake child (ready, fatal, timeout, crash, stubborn, token delivery); a start that restores a copy first (the file named over stdin only, the core's report read, a report that makes no sense not taken for success, a longer wait); work that needs the core stopped, during which nothing can start it; a core that stopped without being asked says so, and one that was asked does not; HTTP client mapping |

jsdom has no modal `<dialog>` or `matchMedia`; `vitest.setup.ts` supplies minimal stand-ins. The
real behaviours are tested in Electron.

### 2. Python (pytest)

Strict mode: warnings are errors.

| File | Covers |
|---|---|
| `tests/unit/test_api_boundary.py` | Token required everywhere, host check, error contract, no CORS/docs, no echo of input |
| `tests/unit/test_provider_credentials.py` | Key never returned or written; internal-route marking; log redaction |
| `tests/unit/test_scene_policy.py` | Every shipped scene passes, the skill examples and the sample course alike; every hostile/broken fixture is rejected for the right reason; scoping tricks; escape attributes; imports; conventions; a call known to render wrongly in the pinned runtime (`Dot` given its position as an argument); degenerate input |
| `tests/unit/test_database.py` | Fresh and repeated migration; schema equals the models; **backup before upgrade**; a failed migration rolls back; a newer or foreign database is refused; backup pruning; **a backup is one file and reading it creates nothing beside it**; restoring keeps what it replaces, refuses what is not a backup, and leaves no trace when it fails; what prepares a restore runs on a working copy and can stop it; the FTS index follows inserts, updates, and cascading deletes; **learner evidence survives the table rebuild in revision 0005** |
| `tests/unit/test_data_copy.py` | Saving a copy through the API: one self-contained file with everything in it and **without the provider key**; an older copy replaced only by a complete one; refused inside the data folder, with another ending, as a relative path; **every operation that takes a path is internal**. Restoring: what the copy held comes back and what it replaced is kept; a safety copy can itself be restored; **an older copy is upgraded in a working file first, and one that cannot be upgraded replaces nothing**; another program's database is refused; originals nothing refers to are removed, and a source without its original still works. Each guarantee was confirmed by removing it and watching a test fail |
| `tests/unit/test_database_sessions.py` | **A unit of work that reads and then writes survives another writer arriving in between** (the interleaving that once failed with "database is locked"); a reader neither waits for a writer nor sees its unfinished work; a read-only unit cannot write; a writing unit inside another is refused at once; an error changes nothing |
| `tests/unit/test_ingestion.py` | Every format against real fixture files; heading paths; PDF reflow; encodings; each rejection and its message; limits; the worker protocol and malformed replies; chunking properties (Hypothesis) |
| `tests/unit/test_courses_and_sources.py` | Course lifecycle and validation; import of every format with provenance; duplicates; a bad file does not stop an import; cleanup on delete; scoped search, highlights, and query-injection attempts |
| `tests/unit/test_jobs.py` | Progress, expected and unexpected failure, one job at a time, cancel (queued, running, too late), interrupted on restart |
| `tests/unit/test_curriculum_graph.py` | Loops (reported once, shortest first), broken links, learning order, layers, closures, what is ready to learn; **properties** over random graphs (Hypothesis), including that a link closes a loop exactly when the check says so |
| `tests/unit/test_curriculum_outline.py` | Numbering removed from headings without damaging real titles; document title versus topics; administrative headings; repeats; bounds |
| `tests/unit/test_knowledge_tracing.py` | BKT against the textbook formula; estimate stays a probability; help and doubt weaken evidence; **one answer is never mastery**; criteria; self-reports; explanations never contain a score; replaying the record reproduces the state (property) |
| `tests/unit/test_review_schedule.py` | First review, growth, help, thin evidence, misses, pauses, cramming, late recall, wording; a schedule is always coherent (property) |
| `tests/unit/test_learner_preferences.py` | Defaults, round trip, tolerant loading |
| `tests/unit/test_curriculum_api.py` | Concepts, objectives with stable ids, order, prerequisites with reasons, loop and cross-course refusal, deletion, outline from headings, links to materials, related passages, retrieval queries and spreading across sources |
| `tests/unit/test_learner_api.py` | Preferences kept across a restart; self-rating as a claim; states with reasons; **no score in any response**; the derived state rebuilt from the record |
| `tests/unit/test_lesson_ir.py` | Every segment and question form; unknown fields, links, markup, paths, and control characters refused; bounds; references inside a lesson; a text alternative for every scene; the player view contains no answer key (checked field by field and by searching the output); stable shuffling |
| `tests/unit/test_lessons_api.py` | The sample course installs complete, once, or not at all; a lesson served for the player; progress and sticky completion; every reference must belong to the course, including citations; an outdated lesson is reported, listed, and removable; **stored scenes are described again from their source and withheld if they may not run**; cascading deletes |
| `tests/unit/test_scoring.py` | Each question form, tolerance and floating-point noise, sign slips, normalised short answers, partial credit for ordering, self-assessed explanations, malformed responses |
| `tests/unit/test_answers_api.py` | Outcome, feedback, explanation, and what changed for right, wrong, hinted, unsure, repeated, and skipped answers; the attempt and the evidence are stored together; no blame and no score in any text |
| `tests/unit/test_misconceptions.py`, `test_misconception_wording.py` | One answer is a suspicion; an independent second supports it; the same wrong option again is not new evidence; a question that could have shown it rejects or resolves it; help and doubt clear nothing; the learner can set one aside and it can come back; slips never block; what a question can reveal; wording that is tentative and never blames; any record folds to coherent hypotheses (property) |
| `tests/unit/test_practice_and_next_step.py` | Which questions are asked first and why; recent ones kept back; variety; the choice does not depend on input order (and properties). The next step for every situation, with its exact reason: resume, a newer explanation first, trouble, reviews by how overdue, suspicions, practice only for what practice can supply, the next concept, nothing due; never the same lesson after a run of misses; a bound on explanations; a step that needs a key never placed first; no reason contains a score; any course gets one coherent suggestion (property) |
| `tests/unit/test_tracing_slips_and_dismissals.py` | A slip counts as partly right and says so; a repeat is described as one; a standing misunderstanding blocks "demonstrated" until cleared; setting one aside is an observation with its own sentence; replay reproduces all of it |
| `tests/unit/test_sitting.py` | Where a sitting begins and ends (a pause longer than the gap; exactly the gap; activity dated in the future); what it showed as counts of right answers and how many count in full; **a sitting never makes a concept demonstrated**; what is missing in the concept's own words; reviews soonest first; lines in learning order; a property test over arbitrary records |
| `tests/unit/test_session_summary_api.py` | Through the service and the API: nothing before anything is done; shown, still needed, and planned review match the concept's own row; only unaided answers count in full; skips are activity but not answers; "last time" after the gap; a new sitting replaces the old; **no score, rate, or percentage in the payload** |
| `tests/unit/test_learning_api.py` | The whole of it through the API: the first suggestion and its reason; learning order; hypotheses from suspicion to supported to resolved, and dismissed; **each kind of answer recorded as what it is** (right, hinted, unsure, slipped, wrong, skipped) and moving the estimate differently; practice without answer keys; nothing asked twice in a day; a repeat counting only after a gap; **a review coming due, being suggested, and moving on**; "this did not help"; no score in any response |
| `tests/unit/test_practice_questions_and_strategies.py` | Questions kept for practice in the lesson format and out of the player view; extra questions in a draft kept or dropped, never fatal; the way of teaching asked for is the one recorded; another explanation uses a way not tried yet; at most four lessons per concept |
| `tests/unit/test_quota.py` | Allowed, wait, or used up; the minute window across midnight; the token allowance counts the request about to be sent; waiting as long as asked always opens the window (property) |
| `tests/unit/test_provider_client.py` | One request to the configured address with the key in one header and nowhere else; no sampling parameters; streamed and unstreamed answers; every refusal as a readable error that quotes nothing; redirects not followed; size and time bounds; cancel between chunks; endpoint configuration |
| `tests/unit/test_model_gateway.py` | Usage written before sending; a full minute waited out; a used-up day refused before sending; one retry after a 429 and never two; nothing else retried; cancel while waiting; one request in flight |
| `tests/unit/test_drafts.py` | A model's answer found however it was wrapped; ids and links assigned here, never read from the model; citations only of passages that were supplied; at most two scenes; scene loss; a proposal cannot contain a loop |
| `tests/unit/test_generation_api.py` | Proposal and lesson jobs end to end against the scripted provider: request counts for every path, prompts carry what they should and nothing secret, a hostile document cannot close its quotation, cancel, quota, provider failures, a proposal found again or set aside |
| `tests/integration/test_process_lifecycle.py` | Real child process: handshake, loopback, shutdown on stdin EOF, bad handshakes, token not in argv or stderr; **a restore asked for in the handshake** (done before the data is opened, reported in the `ready` line, the path not logged); a refused restore leaves the service running on the data as it was |
| `tests/integration/test_isolated_extraction.py` | Parsing in a real child process; a parse past its time limit is killed; **regression: an import inside the real service process** (ADR-007) |

Unit tests parse documents in-process for speed (`extract_in_process`). Only the integration
tests cross the process boundary, so a change to how children are started must be checked there.

### 3. End-to-end (Playwright + Electron)

Drives the **built** app: main, preload, renderer, player frame, and the real Python core.
`e2e/support/app.ts` gives each test a fresh profile directory (`ADLE_USER_DATA_DIR`).
`e2e/support/courses.ts` has the shared steps: create a course, import through the replaced file
dialog, run axe, save a screenshot.

| Spec | Journeys |
|---|---|
| `first-run.spec.ts` | First launch without a key; disclosure shown; library; persisted across restart; keyboard-only completion |
| `provider-key.spec.ts` | Save key → not in DOM, bridge responses, or any profile file (including the core log after exit); survives restart; remove with confirmation; invalid key; dialog focus trap and Escape |
| `scene-player.spec.ts` | Plain scene; interactive scene driven by host and by pointer; events; pause/resume frame-identical; hold on first frame; theme; four broken scenes fail safely; stuck scene isolated; every skill example and **every scene of the sample course** run to completion in both themes, with a screenshot of each; the in-app runtime check operated by keyboard |
| `security.spec.ts` | Renderer globals and exact bridge surface; no network/popups/navigation; inline script refused; internal operations refused; **the page cannot say where a copy goes, which file is restored, or that the learner is sure**; hostile scene contained; player has no bridge |
| `recovery.spec.ts` | **The page's process is killed for real**: the learner is asked in plain words, chooses Reload, and the window comes back on the library with the course still there and the core untouched; one line in `app.log` with the event and nothing of the learner's. "Show log files" in Settings opens the log folder and says the log stays on this computer |
| `data.spec.ts` | Save a copy, delete the course, restore it with its materials still searchable, be shown the safety copy, and undo the restore with it; backing out of each dialog, a place inside the data folder, a name without its ending, a file that only looks like a copy, a document; **delete everything**: the confirmation's wording and default, no phrase of an imported file left in Adle's folders, the saved copy untouched, the key still stored and handed to the new core, and a course created afterwards; axe on each outcome |
| `course-materials.spec.ts` | Create a course; import by file dialog and by drop; extraction status, warnings, and rejections; search with file and page or section; persistence across a restart; remove a source; delete a course; duplicates; keyboard-only creation; a course that no longer exists |
| `curriculum.spec.ts` | Draft from the headings of imported materials; edit objectives; add a concept; prerequisites with a reason; a loop cannot be made; reorder with an explanation when a prerequisite forbids it; self-rating shown as a claim; link and unlink a passage; list and map views; restart in the other theme; remove a concept; a topic course built with the keyboard alone; axe on each view |
| `lesson.spec.ts` | Add the sample course; **each of the other seven lessons gone through part by part**: every picture loads and has its description in words, every question can be skipped, the two interactions have a control, the lesson ends with a suggested next step; a whole lesson in detail: start, pause, resume, a narrated scene and its description in words, an interaction driven from the keyboard, wrong, hinted, and skipped answers, typeset mathematics, a part that ends by itself, the finish panel, the record in the course, review with every part open; resume at the saved part with the scene held until Start; **a scene that breaks while playing and a scene the core withholds** both fall back to words while the lesson goes on; axe on each state |
| `generation.spec.ts` | Against the local fake provider: what will be sent is said first; suggestions reviewed, some kept, a dropped dependency explained; a lesson written with progress and then played; usage counted in Settings; no key; a provider failure and one retry; the fifth request in a minute waits and can be cancelled; suggestions that arrive while the learner is elsewhere |
| `learning.spec.ts` | **The session summary**: after a lesson and a check ("This session", counts, right answers, the planned review), as "Last time, 2 days ago" on returning, and replaced by a new sitting in which one answer is lighter evidence and that is explained. A course opens on its suggested step and the reason; a lesson in which two answers point the same way; the lesson ends with a check, the check asks the question that would show it; the hypothesis shown and set aside with "That was a slip"; **the database is moved two days into the past between launches** and a review is due, suggested, done, and rescheduled further away. "This did not help": skip to the next question, the suggestion changes and says why, no key means an honest pointer to the settings. With the fake provider: another explanation in a chosen way of teaching is written, followed on the Learn tab, and suggested ahead of the old lesson. axe on each state, both themes |
| `narration.spec.ts` | With a voice on the machine: voice and volume settings, a sample, speech as the lesson's clock, pause and resume of the voice itself, transcript on and off, switching reading aloud off and on, no voice left talking after leaving. Without a voice: the lesson says so and reads as text |
| `learning-preferences.spec.ts` | Pace, explanation depth, narration, captions, and goal: changed by mouse and keyboard, remembered across a restart |
| `appearance-a11y.spec.ts` | Theme through the real mechanism and persisted; **axe (WCAG 2.2 AA) on every screen in both themes**; minimum window size; 200% text; reduced motion |

Screenshots of every screen and scene are written to `apps/desktop/test-results/screens/` for
review. They are not compared against baselines (see Gaps).

Test launches add Chromium switches that keep the window painting when it is covered by another
window; they affect scheduling only. Before a test starts, the launch helper waits for the window
to be visible, gives it keyboard focus, and checks that the page is producing frames, so a launch
that does not paint fails at once with a clear message (ADR-008). Tests never call `show()` on
the window themselves.

### 4. Fixtures

| Location | Contents |
|---|---|
| `skills/wanim-scene-authoring/examples/` | Known-good scenes; run by E2E and checked by the scene policy tests |
| `apps/desktop/e2e/fixtures/scenes/` | Broken and hostile scenes (labelled; see its README) |
| `services/core/adle_core/sample_course/` | The sample course itself: outline, lesson templates, scenes. Product content, validated by `test_lessons_api` and played by `e2e/lesson` |
| `apps/desktop/electron/main/core/__fixtures__/fake-core.mjs` | Stand-in for the core's launch protocol |
| `fixtures/sample-documents/` | Real PDF (printed by Chromium), Word, Markdown, and text files, plus encrypted, scanned, damaged, mislabelled, and empty ones. Its README says how each is built. |

No test calls the real AI provider. Python tests replace the transport in process
(`tests/support/model.py`); end-to-end tests point the app at a local server
(`e2e/support/fake-provider.ts`). Both answer from `fixtures/model-answers/`.

`e2e/lesson.spec.ts` edits the profile's database between two launches (with Node's built-in
`node:sqlite`) to put a broken scene into a stored lesson. That is the honest way to reach the
state "a stored scene no longer works": there is deliberately no test hook in the app for it.
`e2e/learning.spec.ts` does the same to let time pass: it moves every timestamp the learner
produced two days back. The app has no settable clock; the core's services take `now` as an
argument, and the Python tests use that.

## Current results

Recorded in `docs/engineering/PROJECT_STATE.md` with the date and commit they apply to.

## Gaps

| Gap | Plan |
|---|---|
| **Packaged build** is not tested (no packager yet) | M8. Until then "works in the packaged build" is BLOCKED. |
| **CI** workflow exists but has never run (no remote) | Run on first push; treat as NOT RUN until then. |
| **macOS and Linux** not exercised | CI matrix covers Linux; macOS in M8. |
| **Visual regression** is manual (screenshots captured, not diffed) | Add baselines once screens stabilise (M7). |
| **Screen reader** behaviour is inferred from roles and axe, not tested with a real reader | Manual pass in M7. |
| **Performance** numbers are informal single-machine observations | Measured report in M8. |
| Complex PDFs (multi-column, tables, equations) are not among the fixtures | Add them when extraction quality is worked on. |
| Vector retrieval | Not built; search is FTS5 only (ADR-007). |
| Answer evidence has no interface yet | The learner model is exercised with answers through the service in tests; only self-rating is reachable in the app until questions exist (M6). |
| Lessons, audio, adaptation | Not built yet (M4–M6); their tests arrive with them. |
