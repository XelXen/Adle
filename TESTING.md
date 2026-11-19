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
| Curriculum screen logic | `apps/desktop/renderer/src/screens/course/curriculum-model.test.ts` | Path order; which neighbour swaps prerequisites allow and the reason given; dependents; map layout (rows, wrapping, no overlap, links); grouped warnings |
| Lesson playback | `apps/desktop/renderer/src/lesson/controller.test.ts` | Nothing plays unasked; beats in turn; pause and resume through the narrator; late callbacks ignored; a question blocks once and only once; jumping only to reached parts; resume and review; finishing; the silent narrator's clock |
| Scene cues | `apps/desktop/renderer/src/lesson/scene-cues.test.ts` | A cue is kept until its segment's scene is holding, delivered once, never to another segment, and not kept for a later visit |
| Answers | `apps/desktop/renderer/src/lesson/answers.test.ts` | Reading a typed number (decimal comma, fractions, typographic minus) without guessing; the request built for each question form; what is still missing |
| Mathematics | `apps/desktop/renderer/src/components/MathText.test.tsx` | Splitting text and `$…$`; KaTeX output with MathML; text that does not parse is shown as written |
| Main: core | `apps/desktop/electron/main/core/core.test.ts` | Supervisor against a fake child (ready, fatal, timeout, crash, stubborn, token delivery); HTTP client mapping |

jsdom has no modal `<dialog>` or `matchMedia`; `vitest.setup.ts` supplies minimal stand-ins. The
real behaviours are tested in Electron.

### 2. Python (pytest)

Strict mode: warnings are errors.

| File | Covers |
|---|---|
| `tests/unit/test_api_boundary.py` | Token required everywhere, host check, error contract, no CORS/docs, no echo of input |
| `tests/unit/test_provider_credentials.py` | Key never returned or written; internal-route marking; log redaction |
| `tests/unit/test_scene_policy.py` | Every shipped scene passes; every hostile/broken fixture is rejected for the right reason; scoping tricks; escape attributes; imports; conventions; degenerate input |
| `tests/unit/test_database.py` | Fresh and repeated migration; schema equals the models; **backup before upgrade**; a failed migration rolls back; a newer or foreign database is refused; backup pruning; the FTS index follows inserts, updates, and cascading deletes |
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
| `tests/integration/test_process_lifecycle.py` | Real child process: handshake, loopback, shutdown on stdin EOF, bad handshakes, token not in argv or stderr |
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
| `scene-player.spec.ts` | Plain scene; interactive scene driven by host and by pointer; events; pause/resume frame-identical; hold on first frame; theme; four broken scenes fail safely; stuck scene isolated; every skill example in both themes; the in-app runtime check operated by keyboard |
| `security.spec.ts` | Renderer globals and exact bridge surface; no network/popups/navigation; inline script refused; internal operations refused; hostile scene contained; player has no bridge |
| `course-materials.spec.ts` | Create a course; import by file dialog and by drop; extraction status, warnings, and rejections; search with file and page or section; persistence across a restart; remove a source; delete a course; duplicates; keyboard-only creation; a course that no longer exists |
| `curriculum.spec.ts` | Draft from the headings of imported materials; edit objectives; add a concept; prerequisites with a reason; a loop cannot be made; reorder with an explanation when a prerequisite forbids it; self-rating shown as a claim; link and unlink a passage; list and map views; restart in the other theme; remove a concept; a topic course built with the keyboard alone; axe on each view |
| `lesson.spec.ts` | Add the sample course; a whole lesson: start, pause, resume, a narrated scene and its description in words, an interaction driven from the keyboard, wrong, hinted, and skipped answers, typeset mathematics, a part that ends by itself, the finish panel, the record in the course, review with every part open; resume at the saved part with the scene held until Start; **a scene that breaks while playing and a scene the core withholds** both fall back to words while the lesson goes on; axe on each state |
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

No test calls the real AI provider. The fake provider server arrives with the client (M5).

`e2e/lesson.spec.ts` edits the profile's database between two launches (with Node's built-in
`node:sqlite`) to put a broken scene into a stored lesson. That is the honest way to reach the
state "a stored scene no longer works": there is deliberately no test hook in the app for it.

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
