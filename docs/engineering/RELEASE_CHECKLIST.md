# Release checklist

Three parts: how a version is published, how a build is made by hand, and where Adle
stands against the acceptance list in `PLAN.md` section 17. A status is one of `PASS`, `FAIL`,
`NOT RUN`, or `BLOCKED`, and each has the evidence beside it. Nothing is inferred.

- **Last filled in:** 2026-11-21, on Windows 11, for the tree described in `PROJECT_STATE.md`.

## Publishing a version

GitHub does it, from a release commit on `main` (ADR-043; the steps for a person are in
`CONTRIBUTING.md` → Releasing). Nothing is built, tagged or uploaded by hand.

| Step | Where | What it proves |
|---|---|---|
| 1. The version and its section in the changelog | `npm run release:notes` | The notes exist |
| 2. A commit `release: <version>`, pushed to `main` on its own | `git push origin main` | What is released is a commit anyone can read |
| 3. CI for that commit | `.github/workflows/ci.yml` | The subject names an alpha or a stable version that `package.json` and the changelog have, not released from another commit; every journey passed on Windows and on Linux; every installer was built and tried out on its own system, where it was built and where it was not; then those installers are published with their checksums, tagged at that commit (as a pre-release for an alpha) |
| 4. Download one and open it | The release page | A person has looked at what people will get |

## Making a build by hand

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
| 10. The installer | `npm run installer` | The folder wrapped the way this system installs things (Windows needs Inno Setup) |
| 11. Try it by hand | Open `apps/desktop/out/release/…/Adle`, add the sample course, take a lesson | A person has looked at it |

The outputs are the folder `apps/desktop/out/release/Adle-<platform>-<arch>/`, which runs
where it is put, and its installer in `apps/desktop/out/installers/`. Close Adle first if
it is open from that folder: the folder cannot be rebuilt under it.

## Before giving it to people who are not developers

| Needed | Status | Why, and what there is |
|---|---|---|
| A licence for the project | PASS | GNU GPL, version 3 (ADR-033); the text travels with every build |
| An installer for each system | PASS | Made, installed, started and removed on GitHub's machines (`a812d34`): `…-windows-x64-setup.exe`, 133 MB; `…-macos-arm64.dmg`, 151 MB, and `…-macos-x64.dmg`, 156 MB; `…-linux-x64.deb`, 126 MB, and `…-linux-x64.tar.gz`, 171 MB. Not on this computer, which has no Inno Setup. On Ubuntu the tarball is unpacked and not started, because Ubuntu keeps an unpacked app from building its sandbox; the folder it holds is started there by the check of the release build |
| A build and a test run on macOS and on Linux | PASS (machines); NOT RUN (a person) | Linux: every journey passes on GitHub's Ubuntu machine, and the `.deb` installs and starts on Ubuntu as it ships. macOS: built, signed ad hoc, installed from its disk image and started, on Apple's and on Intel's processors; no journey runs there. Nobody has looked at Adle on either. The window's own title bar (ADR-030) has been seen on Windows 11 only |
| A run on a computer that has never had the project on it | PASS | On GitHub's machines, `a812d34`: each installer was handed to a second machine of its system that has Node, the scripts that do the trying and nothing else of the project, and was installed, started (the core up within 1.7 to 3.0 s) and removed there. Such a machine still carries more than a new computer does, so on Windows the package's 73 programs and libraries were also read for a runtime library they ask for and do not bring (none). A person installing a release on their own computer: NOT RUN |
| A code-signing certificate, and signing in the build | NOT RUN | Not done, by the owner's decision (ADR-034). Windows warns about an unsigned program and macOS asks before opening one; the release says what to choose |
| A generated lesson sat by a person, from start to finish, in the app | NOT RUN | A real model has written lessons (Kimi K3.1 Pro through NVIDIA NIM, 2026-11-20), and one was gone through in the app from its first part to "Lesson complete" by a script, in both themes (2026-11-21), which found a picture that did not run and led to a rule that now catches it. A second was written the same day with the lesson opening as soon as its text was ready (ADR-031) and gone through the same way; its interactive picture ran, and it showed a formula without its minus sign at the size a lesson shows pictures, which is mended (ADR-032). Nobody has yet learnt from one. The owner's key has to be typed in by the owner |

## The acceptance list (PLAN.md section 17)

| Item | Status | Evidence |
|---|---|---|
| First launch is understandable without reading technical documentation | PASS | `e2e/first-run` (welcome, what stays local, keyboard only); not tested with learners |
| Works without an AI provider, on sample and local content | PASS | `e2e/first-run`, `e2e/lesson` (all eight sample lessons), `e2e/learning`; the session blocks all network requests |
| Topic or syllabus import and source provenance work locally | PASS | `e2e/course-materials`; `test_ingestion`, `test_courses_and_sources` |
| Curriculum graph is reviewable and editable | PASS | `e2e/curriculum`; `test_curriculum_graph`, `test_curriculum_api` |
| Lesson IR is versioned and validated | PASS | `test_lesson_ir`, `test_lessons_api`; schema generated into `packages/contracts` and checked for drift |
| Complete Wanim scene files are generated and executed only in the isolated player | PASS | Isolation: `e2e/security`, `e2e/scene-player`, in development and **in the packaged build**. Generation: `e2e/generation`, `e2e/providers` and `test_generation_api` against stand-ins; and **by a real model** on 2026-11-20 (Kimi K3.1 Pro through NVIDIA NIM, ADR-021): two lessons through Adle's own generation service, three scenes between them, each of which passed the static policy on the first try and ran in the isolated player in both themes. Those runs were by hand: no test may call a real provider |
| Audio and transcript controls work, with honest alignment fallback | PASS | `e2e/narration`; `speech.test.ts` (words are highlighted only when the engine says where it is) |
| Learner interactions produce persistent events | PASS | `test_answers_api`, `test_learning_api`; `e2e/learning` across a restart |
| Mastery is evidence-based and explainable | PASS | `test_knowledge_tracing` (property tests), `test_learner_api`; no score in any payload |
| Misconceptions are treated as hypotheses until supported | PASS | `test_misconceptions`, `e2e/learning` |
| Next-step adaptation is bounded, understandable, and user-controllable | PASS | `test_practice_and_next_step` (every reason checked), `e2e/learning` |
| Retrieval practice exists and persists | PASS | `test_review_schedule`, `e2e/learning` (two days pass; the review is due, done, and rescheduled further away) |
| Quota exhaustion, network loss, TTS failure, Wanim failure, and malformed model output are recoverable | PASS | `e2e/generation` (no key, rate limit, used-up day, provider failure, cancel), `test_model_gateway`, `test_drafts`; `e2e/narration` (no voice); `e2e/lesson` and `e2e/scene-player` (scenes that break or are withheld) |
| Data export, deletion, backup, and restore are tested | PASS | `e2e/data`, `test_data_copy`, `test_database`, `test_process_lifecycle`. "Export" is a copy of everything; one course alone cannot be exported (ADR-016) |
| Light and dark themes, accessibility, and reduced motion are tested | PASS, with a gap | `e2e/appearance-a11y` (both themes, axe on every screen, reduced motion in the shell, the window's own title bar); axe on each state in the other specs, and with it that nothing pressable lies where the window is moved. Not tested with a screen reader by a person |
| CI, unit, integration, E2E, security, and packaging checks pass | PASS | The gates above on this machine, and on GitHub's: Run on `a812d34`, 2026-11-21, eleven jobs: the gates and unit tests on Linux; every journey on Linux (107 of 107 in 14 minutes) and on Windows (107 in 17 minutes, one of them at its second try: a window that did not paint, which the launch helper is there to catch); and the four installers, each built, installed, started and removed on the machine that built it and again on a machine that did not |
| `AGENTS.md`, `PROJECT_STATE.md`, ADRs, README, and developer docs are current | PASS | Updated with each commit; ADR-001 to ADR-034 |
| Git history is coherent, atomic, and honest | PASS | One Conventional Commit per slice on `dev`, each with its gate results, signed where the owner answered the prompt (`git log --format='%h %G? %s'`); on GitHub since 2026-11-21, with no key and nothing of the learner's or the owner's in any commit (the whole history was searched before the first push) |

## Known limitations

- **AIHubMix's free model has never answered.** Two keys were tried: the provider's relay
  answers the first with HTTP 500, and the second belongs to an account that must be topped
  up before the provider passes anything to the model (it says so in a notice, which Adle
  shows; ADR-020). Generation was checked against a real model through NVIDIA NIM instead
  (ADR-021).
- **Generation through NVIDIA is slow.** Its models think before they write: about six
  minutes for a lesson's text and two to three for each picture with Kimi K3.1 Pro, on
  2026-11-20. Adle says what the model is doing and stays usable meanwhile, and the lesson
  can be started as soon as its text is written (ADR-031): after 298 seconds in a run on
  2026-11-21, with its picture arriving at 541.
- **What a provider documents and what its endpoint does differ**, in both directions
  (ADR-021), and can change. When it does, a model stops finishing or refuses its request;
  Adle then asks the provider's next model and says so. The settings that work are written
  beside each model in `services/core/adle_core/generation/provider.py`, with the date.
- **No person has sat a generated lesson yet.** Lessons were generated and inspected, and one
  was gone through in the app by a script; see `PROJECT_STATE.md`.
- **Narration and animation are synchronised per part of a lesson**, not per sentence.
- **PDFs are read with `pypdf`.** Columns, tables, and equations come out as that library
  gives them. Scanned pages are flagged, not read.
- **Search is by words** (SQLite FTS5), not by meaning.
- **One course cannot be exported alone**, and a saved copy is not encrypted.
- **Open answers are marked by the learner** against a list of points, and count as lighter
  evidence. The model does not grade.
- **No signature and no automatic update.** Windows and macOS ask before opening a build,
  and the release says what to choose. To update, install the newer version over the old.
- **Seen by a person on Windows only.** On Linux every journey passes on GitHub's machine;
  on macOS the app is built, installed and started there and no journey runs. The window's
  own title bar (ADR-030) in particular has only been seen on Windows 11; Linux keeps its
  usual frame.
- **On Linux a provider's key needs the desktop's keyring** (GNOME Keyring or KWallet).
  Where there is none Adle says so and does not keep the key.
- **Failures are not reported to anyone.** If something breaks on a learner's computer, the
  only record is the log on that computer.
