# Release checklist

Two parts: what to do each time a build is made for someone else, and where Adle stands
against the acceptance list in `PLAN.md` section 17. A status is one of `PASS`, `FAIL`,
`NOT RUN`, or `BLOCKED`, and each has the evidence beside it. Nothing is inferred.

- **Last filled in:** 2026-11-20, on Windows 11, for the tree described in `PROJECT_STATE.md`.

## Making a build

Run from the repository root, on the operating system the build is for.

| Step | Command | What it proves |
|---|---|---|
| 1. A clean tree at the commit to release | `git status` | Nothing unrecorded goes into the build |
| 2. Exactly the locked dependencies | `npm run setup` | The build is reproducible from `package-lock.json` and `uv.lock` |
| 3. Every gate | `node scripts/check.mjs --e2e` | Formatting, lint, types, licences, unit tests, core tests, and all journeys |
| 4. Known vulnerabilities | `npm audit` and `uv tool run pip-audit -r <exported requirements>` | Nothing known in what is installed |
| 5. The build for tests | `npm run package:test` | The packaged app exists in a form a test tool can drive |
| 6. Every journey against the package | `npm run e2e:packaged` | What a learner would run passes the same tests |
| 7. The release build | `npm run package` | The same build, with the debugger switches off |
| 8. The release build starts | `npm run package:check` | Fuses set; will not run as Node; starts on an empty profile with nothing borrowed from the computer; no orphaned service |
| 9. Timings, if anything on the paths changed | `node scripts/measure.mjs --packaged` | The figures in `PERFORMANCE.md` still hold |
| 10. Try it by hand | Open `apps/desktop/out/release/…/Adle`, add the sample course, take a lesson | A person has looked at it |

The output is the folder `apps/desktop/out/release/Adle-<platform>-<arch>/`. It runs where
it is put. Zip the folder to hand it over.

## Before giving it to people who are not developers

None of these is done. Each needs something only the owner has.

| Needed | Why |
|---|---|
| A code-signing certificate, and signing in the build | Windows warns about an unsigned program; macOS refuses to open one |
| An installer (NSIS or MSI; DMG; AppImage) | A folder is not how most people install software |
| A licence for the project | The repository is marked `UNLICENSED` |
| A build and a test run on macOS and on Linux | The script has the paths for both and has run on neither |
| A run on a computer that has never had the project on it | Step 8 strips the environment, which is not the same thing |
| A lesson written by the real model, read by a person | The model has not answered yet: one key gets HTTP 500 from the provider's relay; the other account must be topped up first |

## The acceptance list (PLAN.md section 17)

| Item | Status | Evidence |
|---|---|---|
| First launch is understandable without reading technical documentation | PASS | `e2e/first-run` (welcome, what stays local, keyboard only); not tested with learners |
| Works without an AI provider, on sample and local content | PASS | `e2e/first-run`, `e2e/lesson` (all eight sample lessons), `e2e/learning`; the session blocks all network requests |
| Topic or syllabus import and source provenance work locally | PASS | `e2e/course-materials`; `test_ingestion`, `test_courses_and_sources` |
| Curriculum graph is reviewable and editable | PASS | `e2e/curriculum`; `test_curriculum_graph`, `test_curriculum_api` |
| Lesson IR is versioned and validated | PASS | `test_lesson_ir`, `test_lessons_api`; schema generated into `packages/contracts` and checked for drift |
| Complete Wanim scene files are generated and executed only in the isolated player | PASS for execution; BLOCKED for generation by the real model | Isolation: `e2e/security`, `e2e/scene-player`, in development and **in the packaged build**. Generation: `e2e/generation` and `test_generation_api` against the fake provider; the real provider has returned only errors |
| Audio and transcript controls work, with honest alignment fallback | PASS | `e2e/narration`; `speech.test.ts` (words are highlighted only when the engine says where it is) |
| Learner interactions produce persistent events | PASS | `test_answers_api`, `test_learning_api`; `e2e/learning` across a restart |
| Mastery is evidence-based and explainable | PASS | `test_knowledge_tracing` (property tests), `test_learner_api`; no score in any payload |
| Misconceptions are treated as hypotheses until supported | PASS | `test_misconceptions`, `e2e/learning` |
| Next-step adaptation is bounded, understandable, and user-controllable | PASS | `test_practice_and_next_step` (every reason checked), `e2e/learning` |
| Retrieval practice exists and persists | PASS | `test_review_schedule`, `e2e/learning` (two days pass; the review is due, done, and rescheduled further away) |
| Quota exhaustion, network loss, TTS failure, Wanim failure, and malformed model output are recoverable | PASS | `e2e/generation` (no key, rate limit, used-up day, provider failure, cancel), `test_model_gateway`, `test_drafts`; `e2e/narration` (no voice); `e2e/lesson` and `e2e/scene-player` (scenes that break or are withheld) |
| Data export, deletion, backup, and restore are tested | PASS | `e2e/data`, `test_data_copy`, `test_database`, `test_process_lifecycle`. "Export" is a copy of everything; one course alone cannot be exported (ADR-016) |
| Light and dark themes, accessibility, and reduced motion are tested | PASS, with a gap | `e2e/appearance-a11y` (both themes, axe on every screen, reduced motion in the shell); axe on each state in the other specs. Not tested with a screen reader by a person |
| CI, unit, integration, E2E, security, and packaging checks pass | PASS locally; CI NOT RUN | The gates above on this machine. The workflow in `.github/` has never run: the repository has no remote |
| `AGENTS.md`, `PROJECT_STATE.md`, ADRs, README, and developer docs are current | PASS | Updated with each commit; ADR-001 to ADR-019 |
| Git history is coherent, atomic, and honest | PASS | One Conventional Commit per slice on `dev`, each with its gate results, all signed; nothing pushed |

## Known limitations

- **No lesson from the real model has been seen.** Every path is tested against a stand-in
  that answers as the documentation says the provider does. The prompts are unchecked. Two
  keys were tried: the provider's relay answers the first with HTTP 500, and the second
  belongs to an account that must be topped up before the provider passes anything to the
  model (it says so in a notice, which Adle now shows; ADR-020).
- **Narration and animation are synchronised per part of a lesson**, not per sentence.
- **PDFs are read with `pypdf`.** Columns, tables, and equations come out as that library
  gives them. Scanned pages are flagged, not read.
- **Search is by words** (SQLite FTS5), not by meaning.
- **One course cannot be exported alone**, and a saved copy is not encrypted.
- **Open answers are marked by the learner** against a list of points, and count as lighter
  evidence. The model does not grade.
- **No installer, no signature, no automatic update.**
- **Windows only, so far.** Nothing has been run on macOS or Linux.
- **Failures are not reported to anyone.** If something breaks on a learner's computer, the
  only record is the log on that computer.
