# Testing

How Adle is tested, how to run each layer, and what is not covered yet.

Statuses used here and in `docs/engineering/PROJECT_STATE.md`:
**PASS** (ran and passed), **FAIL** (ran and failed), **NOT RUN**, **BLOCKED** (could not run; says why).
A result is never reported from reading code.

## Quick reference

| Command | Runs | Time |
|---|---|---|
| `npm run check` | Contract and allowlist drift, third-party licences, Prettier, ESLint, `tsc`, Vitest, ruff, mypy, pytest | ~2.5 min |
| `node scripts/check.mjs --e2e` | All of the above, then builds and runs the Electron suite | ~14 min |
| `npm test` | Vitest (TypeScript unit and component tests) | ~6 s |
| `npm run core:test` | pytest (Python unit and integration tests) | ~95 s |
| `npm run e2e` | Build, then Playwright against the real Electron app | ~11 min |
| `npm run package:test` then `npm run e2e:packaged` | The same suite against the packaged app | ~2 min, then ~11 min |
| `npm run package` then `npm run package:check` | The release build, started from outside on an empty profile | ~2 min, then ~15 s |

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
| Design tokens | `packages/design-system/src/tokens.test.ts` | WCAG contrast for 54 pairs × 2 themes; dark theme completeness; scene palette sync; no raw colours in stylesheets |
| Components | `packages/design-system/src/components/components.test.tsx` | Roles, names, keyboard patterns, loading/disabled/invalid states, toast timing; a dialog gives the focus back to what opened it, also when it is unmounted while open, and a press that began inside it does not close it |
| Frame clock | `apps/desktop/player/frame/src/frame-clock.test.ts` | Pause holds frames, resume releases, cancel, native clock |
| Control mirroring | `apps/desktop/player/frame/src/controls.test.ts` | Reading `adle_controls`, clamping, type checks, cap |
| Player adapter | `apps/desktop/player/host/WanimPlayerAdapter.test.ts` | Status machine, origin/window/run filtering, timeouts, watchdog, fresh origin after failure; **the size a scene is drawn at for a frame of each width** (small for a small frame, never shrunk by more than two or stretched by more than a tenth, the middle size while the frame has no size, a size that is named is used) |
| Main: boundaries | `apps/desktop/electron/main/security-boundaries.test.ts` | Path traversal, host routing, CSP contents, request/navigation filters, trusted sender, invoke validation, window preferences, the window's own title bar and its colours |
| Main: the session | `apps/desktop/electron/main/session-hardening.test.ts` | Each lock is put on (ADR-029): **no name is looked up; every request but the app's own refused; what is not a request goes to a proxy that is nowhere, this computer included; no UDP outside a proxy; nothing saved to a file; no permission of any kind**; no window opened; the window's document stays in the app and a frame is a scene player or nothing |
| Preload: dropped files | `apps/desktop/electron/preload/dropped.test.ts` | **No method of what the page hands over is ever called**; only a real `File` gets a path, and the path is the browser's; a path merely written down is not taken; a bound on how many are looked at |
| Main: local state | `apps/desktop/electron/main/local-state.test.ts` | Key validation; the encrypted store, with **a key kept by provider and address and returned for no other pair**, the choice of provider, the single key of earlier versions, and a tampered record; the list of providers read from the core; Linux fallback refusal; UI state; launch spec |
| Main: what a started core is handed | `apps/desktop/electron/main/providers.test.ts` | **The choice first, then each provider its own key; a choice that was not applied means no key at all** (ADR-029); no key for an address it was not stored for; a choice the core does not offer is kept and not replaced; nothing when the core cannot say which providers there are |
| Main: notifications | `apps/desktop/electron/main/notices.test.ts` | Only the kinds Adle has words for; fixed words with nothing of the learner in them; only while Adle is in the background and the learner has not turned them off; the same thing is not said twice in a row |
| Provider settings | `apps/desktop/renderer/src/screens/settings/provider-model.test.ts` | The sentence about a provider's models and their order; where a key is obtained; that "the provider's limit" is said only where the provider publishes one |
| Main: imports | `apps/desktop/electron/main/imports.test.ts` | Course id shape; import paths must be absolute, bounded, NUL-free; no echo of submitted paths |
| Main: when the app fails | `apps/desktop/electron/main/recovery.test.ts` | A crashed page is reloaded or the app quit, as the learner chooses, and a clean exit says nothing; a hung page is left alone by default; an uncaught error restarts or quits and **never restarts into a failure at start-up**; a stray rejection is only noted; one question at a time; every message says the work is safe and contains no jargon; a core that died is started again at most twice in five minutes. The local log: one JSON line per event, long values cut, starts afresh at its limit, never throws |
| Main: the data as a whole | `apps/desktop/electron/main/data-copy.test.ts`, `data.test.ts` | Where a copy may be saved (never inside the data folder; the ending added but never over another file); what may be restored; which folder may be deleted. The handlers with Electron replaced: each dialog's answer, only a file name returned, the core's refusal passed on, **the folder deleted while the core is held stopped and before anything may start it**, a core that does not come back, one action at a time |
| Data actions in the interface | `apps/desktop/renderer/src/lib/data-actions.test.ts` | Backing out says nothing; what is said after saving, restoring, and deleting; a failure is titled for what did not happen and keeps its reason |
| Curriculum screen logic | `apps/desktop/renderer/src/screens/course/curriculum-model.test.ts` | Path order; which neighbour swaps prerequisites allow and the reason given; dependents; map layout (rows, wrapping, no overlap, links); grouped warnings |
| Lesson playback | `apps/desktop/renderer/src/lesson/controller.test.ts` | Nothing plays unasked; beats in turn; pause and resume through the narrator; late callbacks ignored; a question blocks once and only once; jumping only to reached parts; skipping to the next question without passing an unanswered one; resume and review; finishing; the silent narrator's clock; **a lesson still being written** (ADR-048): parts added after the last and none changed, the learner held at the end of what is written and taken into the next part when it comes, or to the end when none will |
| Scene cues | `apps/desktop/renderer/src/lesson/scene-cues.test.ts` | A cue is kept until its segment's scene is holding, delivered once, never to another segment, and not kept for a later visit |
| Answers | `apps/desktop/renderer/src/lesson/answers.test.ts` | Reading a typed number (decimal comma, fractions, typographic minus) without guessing; the request built for each question form; what is still missing |
| Speech | `apps/desktop/renderer/src/lesson/speech.test.ts` | Only local voices; waiting for the voice list; the voice for the lesson's language over the system default; the voice as the clock; word positions only from the engine; pause, resume, cancel; a stand-in when the voice fails |
| What a learner reads | `apps/desktop/renderer/src/wording.test.ts` | **Every string and every piece of text in the interface, the main process and the design system is in American English** (ADR-044), read by TypeScript's own parser so that comments and names in code do not count; the API's names are let be; the check itself catches a British word in a string and in JSX text and nothing in a comment |
| A natural voice, played | `apps/desktop/renderer/src/lesson/recorded.test.ts` | A recorded line plays its clip at the learner's pace and volume and marks each word at the time it was recorded; pause and resume hold the mark; a line not recorded, or a clip that will not play, is read by the computer's voice |
| The voices in Settings | `apps/desktop/renderer/src/screens/settings/voice-model.test.ts`, `VoiceChoices.test.tsx` | Sizes as a person says them, and where a setup downloads from; which voice is in use, set up, being set up, waiting, offered, or out of reach and why; the best for this computer until one is set up; **a setup followed to its end** (one at a time, its progress, "ready" said once), stopped, and failed with the reason in its own card; a speaker chosen; back to the computer's voice; removal only after saying what it frees; nothing to set up or remove for a voice set up by hand |
| Generation results | `apps/desktop/renderer/src/lib/generation.test.ts` | Reading a proposal or a lesson outcome from a job's free-form result; **a lesson that can be started while its pictures are still being drawn** (read from a job that is still running, and from no job that failed or was stopped); what is said when a lesson can be started and when its work ends, and that it is not said twice; the wait said beside the button; progress; which remedy each failure gets |
| A lesson's pictures and later parts, as they arrive | `apps/desktop/renderer/src/lib/use-lesson-updates.test.tsx` | A lesson with nothing to wait for is never asked about again; one that is waiting for a picture or a part is looked at every few seconds until nothing is, and takes each as it comes; its parts only ever grow; a look that fails changes nothing and is tried again; no look once the learner has left |
| Where a request goes | `apps/desktop/renderer/src/lib/provider.test.ts` | The destination is the core's plan word for word, and no provider is named while it is not known; a wait is never said more exactly than it can be known; reading the outcome of a key check |
| Questions during a lesson | `apps/desktop/renderer/src/lib/asks.test.ts` | The ready-made questions, none of which asks for the answer to an open question; the bounds on a question; everything a question sends is named; who answered; the questions of one part in order |
| Breaks | `apps/desktop/renderer/src/lib/breaks.test.ts` | A break as long as the wait, within bounds; the clock for the eye and for the ear; longer and shorter by whole minutes; ideas that count nothing and never scold |
| What is being written, app-wide | `apps/desktop/renderer/src/app/WritingContext.test.ts` | Which screen already shows what has arrived (so it is not announced there), and which screen is where it is; **when there is something to say** (a lesson as soon as it can be started, suggestions only when they are all there, a failure always, nothing for work the learner stopped); the words for it; which screens say it themselves |
| Next step and progress | `apps/desktop/renderer/src/lib/learning.test.ts` | The session summary in words ("This session", or "Last time" with its day; counts of what was done; right answers with any lighter evidence named and never as a share). Where each kind of suggested step leads (a lesson, questions, the settings when a key is missing, nowhere); waits and reviews in everyday words; counts of concepts that are never a score; how a hypothesis is labelled; how a set of questions is summed up |
| Mathematics | `apps/desktop/renderer/src/components/MathText.test.tsx` | Splitting text and `$…$`; KaTeX output with MathML; text that does not parse is shown as written |
| Sample course content | `apps/desktop/renderer/src/components/sample-content-math.test.ts` | Every formula in every sample lesson typesets with the player's own options; no formula is left unclosed; narration, which is read aloud, contains no notation; there are eight lessons |
| Main: core | `apps/desktop/electron/main/core/core.test.ts` | Supervisor against a fake child (ready, fatal, timeout, crash, stubborn, token delivery); **what is done after the core is ready and before anyone is told** (it runs first, and its failure is a failed start with no core left behind); a value for a path is refused unless it is a plain id; a start that restores a copy first (the file named over stdin only, the core's report read, a report that makes no sense not taken for success, a longer wait); work that needs the core stopped, during which nothing can start it; a core that stopped without being asked says so, and one that was asked does not; HTTP client mapping |

jsdom has no modal `<dialog>` or `matchMedia`; `vitest.setup.ts` supplies minimal stand-ins. The
real behaviours are tested in Electron.

### 2. Python (pytest)

Strict mode: warnings are errors.

| File | Covers |
|---|---|
| `tests/unit/test_api_boundary.py` | Token required everywhere, **and checked before any of the body is read**; a body over the limit refused, with or without a stated length; host check; error contract; no CORS/docs; no echo of input |
| `tests/unit/test_prompt_quoting.py` | **Nothing in quoted text can pass for the end of its block**, in any spelling of the tag; ordinary mathematics left alone; a file's name and a heading are quoted with the excerpt and cut short; every prompt that carries excerpts does so |
| `tests/unit/test_provider_routing.py` | **Both providers together (ADR-023).** One provider chosen is the whole plan whatever has happened to it; with "automatic", what is waited for goes to the quick one and long work to the roomy one; only providers with a key are ever planned; the next is asked when one cannot answer, and it is said; an account that refuses is left alone until its key changes; one request at a time at each provider; what to expect is measured; a key check goes to that provider alone; the reason given is about the provider that is away; what an old key found out is not held against a new one |
| `tests/unit/test_asks.py` | **A question during a lesson (ADR-024).** Kept beside its part; the part and the question sent as quoted material that cannot close its block; **the answer to a question the lesson is asking is never sent**, nor which choice is right; one more try for an unusable answer and then none; bounds; no key, nothing asked; does not wait behind a lesson being written; can be stopped; **the answer that follows counts as an aided one, also after the note was removed**; a skipped question has shown its explanation |
| `tests/unit/test_provider_choice.py` | **A choice of providers (ADR-021).** The catalogue and a developer's moved endpoints; the exact body each NVIDIA model is sent; a key only ever at its own provider's address, and never another's in its place; what counts as a model being away (404, 410, 5xx, an error mid-answer, silence, the time limit) and what does not (a refused key, a rate limit, no connection); the next model asked and said, a refused request passed over too, the ten-minute rest, every model resting; a provider with one model unchanged; each provider counted alone against its own limits; thinking counted and not kept; "stop" and the time limit while a model only thinks; what a model is doing reported to the job; the API (choose, refused while writing, keys per provider, the internal flag); a lesson through NVIDIA with the first model away |
| `tests/unit/test_provider_credentials.py` | Key never returned or written; internal-route marking; log redaction, **including inside a traceback**; the log records an error's kind and where it happened, never its text |
| `tests/unit/test_scene_policy.py` | Every shipped scene passes, the skill examples and the sample course alike; every hostile/broken fixture is rejected for the right reason; scoping tricks; escape attributes; imports; conventions; calls known to go wrong in the pinned runtime (`Dot` given its position as an argument; `set_fill` and `set_color` given anything by name), with a reason that says how to write them; degenerate input |
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
| `tests/unit/test_lesson_ir.py` | Every segment and question form; unknown fields, links, markup, paths, and control characters refused; bounds; references inside a lesson; a text alternative for every scene; the player view contains no answer key (checked field by field and by searching the output); stable shuffling; **an ordering question is shown under names that are not its ids and do not sort into its answer**, the same names every time on one installation |
| `tests/unit/test_lessons_api.py` | The sample course installs complete, once, or not at all; a lesson served for the player; progress and sticky completion; every reference must belong to the course, including citations; an outdated lesson is reported, listed, and removable; **stored scenes are described again from their source and withheld if they may not run**; cascading deletes |
| `tests/unit/test_scoring.py` | Each question form, tolerance and floating-point noise, sign slips, normalised short answers, partial credit for ordering (answered by the names the page was shown; a real id is not accepted), self-assessed explanations, malformed responses |
| `tests/unit/test_answers_api.py` | Outcome, feedback, explanation, and what changed for right, wrong, hinted, unsure, repeated, and skipped answers; the attempt and the evidence are stored together; no blame and no score in any text |
| `tests/unit/test_misconceptions.py`, `test_misconception_wording.py` | One answer is a suspicion; an independent second supports it; the same wrong option again is not new evidence; a question that could have shown it rejects or resolves it; help and doubt clear nothing; the learner can set one aside and it can come back; slips never block; what a question can reveal; wording that is tentative and never blames; any record folds to coherent hypotheses (property) |
| `tests/unit/test_practice_and_next_step.py` | Which questions are asked first and why; recent ones kept back; variety; the choice does not depend on input order (and properties). The next step for every situation, with its exact reason: resume, a newer explanation first, trouble, reviews by how overdue, suspicions, practice only for what practice can supply, the next concept, nothing due; never the same lesson after a run of misses; a bound on explanations; a step that needs a key never placed first; no reason contains a score; any course gets one coherent suggestion (property) |
| `tests/unit/test_tracing_slips_and_dismissals.py` | A slip counts as partly right and says so; a repeat is described as one; a standing misunderstanding blocks "demonstrated" until cleared; setting one aside is an observation with its own sentence; replay reproduces all of it |
| `tests/unit/test_sitting.py` | Where a sitting begins and ends (a pause longer than the gap; exactly the gap; activity dated in the future); what it showed as counts of right answers and how many count in full; **a sitting never makes a concept demonstrated**; what is missing in the concept's own words; reviews soonest first; lines in learning order; a property test over arbitrary records |
| `tests/unit/test_session_summary_api.py` | Through the service and the API: nothing before anything is done; shown, still needed, and planned review match the concept's own row; only unaided answers count in full; skips are activity but not answers; "last time" after the gap; a new sitting replaces the old; **no score, rate, or percentage in the payload** |
| `tests/unit/test_learning_api.py` | The whole of it through the API: the first suggestion and its reason; learning order; hypotheses from suspicion to supported to resolved, and dismissed; **each kind of answer recorded as what it is** (right, hinted, unsure, slipped, wrong, skipped) and moving the estimate differently; practice without answer keys; nothing asked twice in a day; a repeat counting only after a gap; **a review coming due, being suggested, and moving on**; "this did not help"; no score in any response |
| `tests/unit/test_practice_questions_and_strategies.py` | Questions kept for practice in the lesson format and out of the player view; extra questions in a draft kept or dropped, never fatal; the way of teaching asked for is the one recorded; another explanation uses a way not tried yet; at most four lessons per concept |
| `tests/unit/test_quota.py` | Allowed, wait, or used up; the minute window across midnight; the token allowance counts the request about to be sent; waiting as long as asked always opens the window (property) |
| `tests/unit/test_provider_notice.py` | **An answer the provider wrote itself**, in the two shapes the real provider sent on 2026-11-20 (streamed, and not): raised as `provider_notice` with the provider's words quoted; an answer with text and no tokens used is one too; an ordinary answer, or a stream that reports no usage, is not; the words reach the learner and not the log; hostile words are made one plain line of limited length; a lesson job and a curriculum job each end after one request with nothing saved. Each sign was removed in turn and a test seen to fail |
| `tests/unit/test_provider_client.py` | One request to the configured address with the key in one header and nowhere else; no sampling parameters; streamed and unstreamed answers; every refusal as a readable error that quotes nothing; redirects not followed; size and time bounds, **on one line, on the whole answer, and on an answer that only drips**; asked for uncompressed; cancel between chunks, and the connection closed; endpoint configuration |
| `tests/unit/test_model_gateway.py` | Usage written before sending; a full minute waited out; a used-up day refused before sending; one retry after a 429 and never two; nothing else retried; cancel while waiting; one request in flight |
| `tests/unit/test_drafts.py` | A model's answer found however it was wrapped; **TeX written with one backslash or two is read whole** (the draft a real model sent, the escapes that are valid JSON for something else, real line breaks left alone; a property test that a properly escaped answer is read exactly as before); ids and links assigned here, never read from the model; citations only of passages that were supplied; at most two scenes; scene loss; a proposal cannot contain a loop; **TeX escaped twice is shown as it was meant**, and TeX written once is left alone |
| `tests/unit/test_figures.py` | **Figures (ADR-045).** Every example is a scene the policy accepts, and is the file the player runs (`npm run figures`); a formula is read as arithmetic and comparisons and nothing else, and tried for a value and a jump; text reaches the scene only as a literal; a figure that does not hold together says why; pacing; **what a real model wrote is taken as it was meant**: a blank field, curves counted from 0, a curve in pieces, an area that follows the slider, a slider named x, words and a formula in one cell |
| `tests/unit/test_lesson_figures.py` | A lesson with figures is one request, every figure in it and paced to its words; a figure that cannot be drawn costs its picture, not the lesson; one with no description is not drawn; an interaction with nothing to move is watched; figures and a model's scene together |
| `tests/unit/test_scene_trials.py` | **A picture tried in the player before it is kept (ADR-038)**, with the app played by a thread: the app is there while it asks; a trial offered, answered and withdrawn; one nobody answers is untried; a failure told to the model in one short line; a picture that fails its trial written again, told why, and said in words if it fails twice; without the app, pictures kept untried; **a lesson's figures offered for their trials all at once** (ADR-045) |
| `tests/unit/test_speech.py` | **Notation in narration said in words** (ADR-047): the lines a real model wrote; fractions, roots, powers, sums, limits, cases, accents; mathematics in its own symbols (σ, ≤, ∫); words joined by a hyphen kept; a line with a link or markup left to be refused; nothing of TeX left in what is said; a long line ends at a sentence |
| `tests/unit/test_stream.py` | **An answer read as it arrives** (ADR-048): what comes before the parts, then each part once its closing brace has come, the same however the answer is cut into pieces (a property); a brace or a quotation mark inside a sentence is not structure; TeX read as the whole answer would read it; parts written before the title give no header; an answer cut off gives only its whole parts; another model's answer starts afresh; what follows the answer is not read |
| `tests/unit/test_lesson_part_by_part.py` | **A lesson begun at its first part** (ADR-048), against an answer held partway: stored, listed as still being written, opened and its place kept while the rest is written, and said to be written by whom; every later part added after the last, the first as it was; one request for the words; the same lesson as one taken whole; a later part that is not whole left out, and the lesson not written again; a first part that is not whole begins nothing, and the whole answer decides; a stop, or a provider that fails, keeps the parts there are and says it ends early; removing the lesson while it is written ends the work; one left being written when the app closed ends at the next start; a model that fails before its first part is passed over as before |
| `tests/unit/test_pdf_headings.py` | **A PDF's whole syllabus (ADR-046)**: sections from its outline, else its numbered headings, cut page by page; a table of contents and a heading never joined to the text around them; a course plan offered every heading, or how each page begins when there are none; the owner's own chapter where it is (`testchap.pdf`, never committed) |
| `tests/unit/test_narration.py` | With a stand-in engine: what each voice needs and what this computer runs; the card read from its driver's own tool; a number found as it is said; no voice means lessons are read as before; the richest voice here reads lessons, any can be chosen; **each line recorded once with where its words are**, again in another voice and never played in the old one; clips named by the core, never by a path; a lesson or a course that goes takes its recordings; a line the voice cannot say fails plainly; **a lesson recorded as soon as it is stored when a voice reads them**, and not without one; **a setup runs in the background** and the voice then reads the lessons; one at a time, stoppable; refused where the computer cannot run it, or for a voice set up by hand; a failure says why; removal takes that voice's recordings and leaves the others'; the Expressive voice designed from the lesson's own description |
| `tests/unit/test_wording.py` | **Every string the core can say, every text of the sample course and its pictures' labels are in American English** (ADR-044), read by Python's own parser (comments and docstrings do not count; the schema's names are let be); the writing rules and the request for a picture ask the model for American spelling |
| `tests/unit/test_voice_install.py` | Nothing downloaded: a file is whole only if it is exactly the one pinned; each file fetched from its pinned revision, a redirect followed, then the voice tried; **a changed, a longer and a shorter file are each refused**; a download that cannot be had is said plainly; a stopped one leaves nothing half written; a file another voice has is copied; no room means nothing fetched; **the programs installed exactly as locked**, in an environment the core's own Python makes (`venv`, for real), with every hash required and none of this computer's pip settings; a failed install leaves no environment; programs from another version are installed again; every lock pinned with its hashes and without what is left out; removal keeps what another voice still needs |
| `tests/unit/test_generation_api.py` | Proposal and lesson jobs end to end against the scripted provider: request counts for every path, prompts carry what they should and nothing secret, a hostile document cannot close its quotation, cancel, quota, provider failures, a proposal found again or set aside; **a first draft kept when only its notation or a practice question needed mending** |
| `tests/unit/test_lesson_before_pictures.py` | **A lesson can be taken as soon as its text is written** (ADR-031), against a provider whose pictures are held back: it is listed, opened, answered and its place kept while the job still runs; each picture is added when it is drawn; one that cannot be drawn, or that the lesson cannot take, is said in words; stopping keeps the lesson, and before there is one saves nothing; **removing the lesson, or its course, ends the work without waiting for the picture asked for** (each seen to fail with the stopping taken out); who wrote it is kept with the lesson; the gate takes a picture that is included or still to come and nothing else; **the voice is told of a lesson while its pictures are still to come**; a lesson left waiting when the app closed is settled at the next start |
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
| `providers.spec.ts` | **Two providers, as two servers on this computer.** Both are shown with their addresses and models in order; choosing NVIDIA and giving it its own key; a request with the first model away: only NVIDIA's server is asked, only with NVIDIA's key, each model with only its documented fields; the stand-in is said while it happens and in the review; the provider cannot be changed while it is writing; the choice, both keys and the count survive a restart. A key is not handed over when the provider has moved, and is there again when it is back. The page cannot name an address or an unknown provider |
| `ask.spec.ts` | **A question asked during a lesson.** What will be sent is said first and nothing is sent before "Ask"; the answer is typeset and says who wrote it; it is kept beside its part, can be removed, belongs to that part, and is there after a restart; a ready-made question; a question the lesson is asking: the dialog says asking counts as help, the request has the choices and nothing that settles it, and the answer that follows is recorded as aided (read from the database); a slow answer: carry on with the lesson, be told by the app and (recorded, never shown) by the computer; stopping one; a provider that fails; no key |
| `break.spec.ts` | **Waiting for something to be written.** The wait is said in minutes with a break offered; the break's clock, made longer and shorter, left running in the rail; the lesson can be started while the learner is in Settings and in another window, its pictures still held back: a toast, and a notification with fixed words, once; the break has it waiting, says its pictures are on their way and does not list it a second time as work under way; nothing more is said when the pictures arrive; opening it ends the break; a break ends by itself (the page's clock moved forward), says so once, and more rest is as welcome as going back; notifications turned off; the page cannot ask for words of its own |
| `provider-key.spec.ts` | Save key → not in DOM, bridge responses, or any profile file (including the core log after exit); survives restart; remove with confirmation; invalid key; dialog focus trap and Escape |
| `scene-player.spec.ts` | Plain scene; interactive scene driven by host and by pointer; events; pause/resume frame-identical; hold on first frame; theme; four broken scenes fail safely; stuck scene isolated; **a curve shown by its stroke is a line and one shown with `set_opacity` is filled in**, and **a fill given in order is drawn, given by name it is lost, and without its colour the scene stops** (the window's own pixels, read by the main process); every skill example and **every scene of the sample course** run to completion in both themes, with a screenshot of each; the in-app runtime check operated by keyboard; **a picture shown at the size of a lesson, on a display with one pixel to the point, keeps every one of 26 small minus signs when it is drawn at the size the adapter asks for** (drawn at the old size two were not there at all); a scene drawn at each of the three sizes fills its frame at each; the pointer lands where it points on a picture shown smaller than it is drawn (a slider dragged at the size of a lesson) |
| `security.spec.ts` | Renderer globals and exact bridge surface; no network/popups/navigation; **nothing arrives at listeners on this computer from a peer connection or a connection opened ahead of time, from the page or from a player frame**; a forged list of dropped files names nothing; inline script refused; internal operations refused; **the page cannot say where a copy goes, which file is restored, or that the learner is sure**; hostile scene contained; player has no bridge |
| `recovery.spec.ts` | **The page's process is killed for real**: the learner is asked in plain words, chooses Reload, and the window comes back on the library with the course still there and the core untouched; one line in `app.log` with the event and nothing of the learner's. "Show log files" in Settings opens the log folder and says the log stays on this computer |
| `data.spec.ts` | Save a copy, delete the course, restore it with its materials still searchable, be shown the safety copy, and undo the restore with it; backing out of each dialog, a place inside the data folder, a name without its ending, a file that only looks like a copy, a document; **delete everything**: the confirmation's wording and default, no phrase of an imported file left in Adle's folders, the saved copy untouched, the key still stored and handed to the new core, and a course created afterwards; axe on each outcome |
| `course-materials.spec.ts` | Create a course; import by file dialog and by drop; extraction status, warnings, and rejections; search with file and page or section; persistence across a restart; remove a source; delete a course; duplicates; keyboard-only creation; a course that no longer exists |
| `curriculum.spec.ts` | Draft from the headings of imported materials; edit objectives; add a concept; prerequisites with a reason; a loop cannot be made; reorder with an explanation when a prerequisite forbids it; self-rating shown as a claim; link and unlink a passage; list and map views; restart in the other theme; remove a concept; a topic course built with the keyboard alone; axe on each view |
| `lesson.spec.ts` | Add the sample course; **each of the other seven lessons gone through part by part**: every picture loads and has its description in words, every question can be skipped, the two interactions have a control, the lesson ends with a suggested next step; a whole lesson in detail: start, pause, resume, a narrated scene and its description in words, an interaction driven from the keyboard, wrong, hinted, and skipped answers, typeset mathematics, a part that ends by itself, the finish panel, the record in the course, review with every part open; resume at the saved part with the scene held until Start; **a scene that breaks while playing and a scene the core withholds** both fall back to words while the lesson goes on; axe on each state; a lesson's picture is drawn at the size that suits its frame (854 wide in a window of the usual size); a scene not yet started is still, and moves once started: told from its own canvas, not from a picture of the page, and both pictures are kept with the report if they differ |
| `generation.spec.ts` | **A notice from the provider in the model's place**: shown in the provider's own words with no link in them, after one request, with the settings offered and "Try again" not. Against the local fake provider: what will be sent is said first; suggestions reviewed, some kept, a dropped dependency explained; a lesson written with progress and then played; **a lesson started while its pictures are held back** (said once; listed with "Pictures on their way"; no break and no second lesson offered; a part whose picture is not there yet is in words; the first picture takes its place in a part that has not begun, the second is offered in a part that has; who wrote it is under the title); **the pictures stopped, which keeps the lesson, and a lesson removed while they are drawn, which ends the work with nothing called cancelled and no further request**; usage counted in Settings; no key; a provider failure and one retry; the fifth request in a minute waits and can be cancelled; suggestions that arrive while the learner is elsewhere |
| `learning.spec.ts` | **The session summary**: after a lesson and a check ("This session", counts, right answers, the planned review), as "Last time, 2 days ago" on returning, and replaced by a new sitting in which one answer is lighter evidence and that is explained. A course opens on its suggested step and the reason; a lesson in which two answers point the same way; the lesson ends with a check, the check asks the question that would show it; the hypothesis shown and set aside with "That was a slip"; **the database is moved two days into the past between launches** and a review is due, suggested, done, and rescheduled further away. "This did not help": skip to the next question, the suggestion changes and says why, no key means an honest pointer to the settings. With the fake provider: another explanation in a chosen way of teaching is written, followed on the Learn tab, and suggested ahead of the old lesson. axe on each state, both themes |
| `narration.spec.ts` | With a voice on the machine: voice and volume settings, a sample, speech as the lesson's clock, pause and resume of the voice itself, transcript on and off, switching reading aloud off and on, no voice left talking after leaving. Without a voice: the lesson says so and reads as text. With voices that are listed and cannot be held (a build machine with nowhere to play sound): the journey asks the machine, and follows the app where it stands in for the voice line by line; the report says which way it went |
| `voice.spec.ts` | With a stand-in engine pointed at by the developer settings: the sample lesson recorded in the background, then played with **each word marked in turn, looked at on every frame of the page**, and never the computer's voice speaking; pause holds the word. Settings lists the voices from the lightest to the richest, the one in use, a speaker chosen and kept, and back to the computer's voice; axe |
| `learning-preferences.spec.ts` | Pace, explanation depth, narration, captions, and goal: changed by mouse and keyboard, remembered across a restart |
| `appearance-a11y.spec.ts` | Theme through the real mechanism and persisted; **axe (WCAG 2.2 AA) on every screen in both themes**; minimum window size; 200% text; reduced motion; **the window's own title bar**: the strip the window is moved by, nothing that can be pressed underneath it on any screen, and the system's buttons in the theme's colours |

Screenshots of every screen and scene are written to `apps/desktop/test-results/screens/` for
review. They are not compared against baselines (see Gaps).

No notification of the operating system is ever shown by a test run. The launch helper
replaces the last step (`Notification.prototype.show`) with a recorder, so the app's own
decision runs as it does for a learner: read what it would have shown with `adle.notices()`.
One is only asked for while the window does not have the focus, which on a developer's
screen is a matter of luck, so a journey sets it: `adle.setFocused(false)`.

A journey that needs minutes to pass moves the page's clock (`page.clock.install()`,
`fastForward`, then `resume`); it never waits them out.

Test launches add Chromium switches that keep the window painting when it is covered by another
window; they affect scheduling only. Before a test starts, the launch helper waits for the window
to be visible, gives it keyboard focus, and checks that the page is producing frames, so a launch
that does not paint fails at once with a clear message (ADR-008). Tests never call `show()` on
the window themselves.

### 4. The packaged app

Two builds come out of `scripts/package.mjs` (ADR-019), and each is tested in the only way
it can be.

| What | How | Covers |
|---|---|---|
| The build for tests (`out/test`) | `npm run e2e:packaged`: the whole suite of section 3, unchanged, with `ADLE_E2E_EXECUTABLE` pointing at the packaged executable | Everything the suite covers, in the form a learner would run: the app loaded from its archive, the core running in its private Python. In particular scene isolation, the bridge surface, and the network block |
| The release build (`out/release`) | `npm run package:check`, from outside, because its debugger switches are off | Fuses as intended; will not run as plain Node; starts on an empty profile with a bare `PATH` and a hostile `PYTHONHOME` and `PYTHONPATH`; the core comes up; nothing in the log of failures; the core does not stay behind when the app is ended. On Windows also what starting it cannot show: none of its programs asks for a part of the Visual C++ runtime that the package does not bring (read from their import tables; a computer that builds software has that runtime, a new one may not) |
| The core as packaged | A step of `package.mjs` itself | The private Python imports the service and everything it needs, finds its migrations and the sample course as package data, and has no telemetry exporter in it |

A first start straight after packaging is slow while the operating system looks at the new
files, so `e2e:packaged` runs the start-up check first as a warm-up.

### 5. Installers, and what GitHub runs

An installer is tested by using it. `node scripts/installer.mjs --check` makes the
installer of the system it runs on, installs it, starts the installed app from outside with
`scripts/smoke-packaged.mjs --at=<the installed executable>` (the same check as for the
release folder), and removes it again. It changes the computer it runs on, so outside CI it
asks to be told `--on-this-computer`.

The machine that built an installer has everything the app was built from, so an app that
leaned on any of it would still start there. Each installer is therefore tried a second
time, with `node scripts/installer.mjs --check --made`, on a machine of the same system
that has Node, the `scripts` folder and nothing else of the project: no Python of Adle's,
no uv, no Electron, nothing built. What starts there starts on what the installer brought.
One thing is left out there, and said: reading the binary's fuses needs a tool that machine
does not have, so they are read where the app is built.

| Workflow | When | What it runs |
|---|---|---|
| `ci.yml` | every push to `main`, every pull request | `node scripts/check.mjs` and both audits, on Linux. Then, side by side: the end-to-end suite on Windows and on Linux; and `build.yml`. For a release commit (`release: <version>`, ADR-043) it first checks that the version can be published, and when everything has passed, publishes the installers `build.yml` made, with checksums |
| `build.yml` | called by `ci.yml` | On Windows, macOS (Apple and Intel processors) and Linux: the release build, its installer, the installer tried out as above, and the start-up check of the release folder, which also has the core's Python make an environment with pip in it, as a natural voice is set up in (ADR-042). Then, on a second machine of each kind: the installer tried out where it was not built |

What each system's try-out covers that the others do not:

- **Windows:** a silent install into a folder of its own, the Start menu shortcut, and an
  uninstall that leaves neither behind.
- **macOS:** the app copied out of the disk image still has the signature it was built
  with, file for file (`codesign --verify --deep --strict`).
- **Linux:** the package holds the sandbox helper as root's and marked to run as root; the
  app starts once installed, on a system as Ubuntu ships it; removing the package removes
  the app. The tarball is unpacked, and started where the system lets an unpacked app
  build a sandbox.

A build machine is not a learner's computer, and has to be given a few things:

- **A keyring, on Linux.** Adle keeps a provider's key only where the system can keep a
  secret, and a build machine has no keyring. The Linux journeys run in a session with a
  message bus and an unlocked GNOME keyring made for that run (`ci.yml`), which is asked to
  keep something and give it back before any journey starts.
- **The test tool's idea of where secrets go, undone.** Playwright starts every Chromium it
  drives with `--password-store=basic`: on Linux, "keep secrets as plain text". Adle
  refuses that however good the keyring is, so `e2e/support/keep-secrets.cjs` is loaded
  into the app after the tool's own loader and takes the switch away, on every system. A
  packaged app loads neither, and never has the switch.
- **A display, on Linux**: a virtual one (`xvfb-run`). The start-up check starts the app
  with almost nothing in its environment, and hands on where the display is and the right
  to draw on it.
- **Namespaces, on Linux, for an app run from its folder.** Installed from the `.deb`, the
  app builds its sandbox with the helper the package installs, on the system as it ships.
  Run from the build folder (the journeys, and the check of the release folder), the helper
  is nobody's, so the build machine is told to let programs make namespaces. The sandbox
  itself is on in every case.
- **Nothing, for sound.** GitHub's Windows machine lists voices and has nowhere to play
  them. The journey that reads aloud asks the machine what it can do and follows.
- **Somebody to notify.** The Linux machine's session has no notification service, and the
  app, asked whether a notification could be shown, rightly hears no and shows none. The
  launch helper already stands in for the showing; it answers that question too, with yes.
- **Time for its first frames.** Drawing without a graphics card on a busy machine, a
  window was seen to take more than five seconds over its first two frames. The launch
  helper asks up to six times before it calls a launch one that does not paint.

A profile on Linux also holds links that lead nowhere (Chromium writes who holds the
profile into the name a link points at), so the helper that searches a profile for a key
reads a link as what it is and does not follow it.

When the app does not come up, the start-up check says what the app wrote to its error
output and how its two logs end, and stops as soon as the app has closed instead of waiting
for a core that is not coming.

### 6. Fixtures

| Location | Contents |
|---|---|
| `skills/wanim-scene-authoring/examples/` | Known-good scenes; run by E2E and checked by the scene policy tests |
| `apps/desktop/e2e/fixtures/scenes/` | Broken and hostile scenes (labelled; see its README) |
| `apps/desktop/e2e/fixtures/figures/` | One scene of every kind of figure, as the core writes them (`npm run figures`); each run to completion in both themes by `e2e/scene-player.spec.ts` |
| `services/core/adle_core/sample_course/` | The sample course itself: outline, lesson templates, scenes. Product content, validated by `test_lessons_api` and played by `e2e/lesson` |
| `apps/desktop/electron/main/core/__fixtures__/fake-core.mjs` | Stand-in for the core's launch protocol |
| `fixtures/sample-documents/` | Real PDF (printed by Chromium), Word, Markdown, and text files, plus encrypted, scanned, damaged, mislabelled, and empty ones; a chapter with an outline and one with numbered headings (ADR-046). Its README says how each is built. |
| `testchap.pdf` (repository root, ignored by git) | The owner's own lecture notes, used by `test_pdf_headings.py` where the file is, and by `scripts/dev/real_provider_check.py document:<file>` by hand. Never committed |

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
| **The release build** is checked from outside only; the journeys run against a twin of it with the debugger reachable | By design (ADR-019). The two differ in one fuse. |
| **A learner's own computer** | The nearest thing that runs by itself is a build machine that did not build the installer it is given (section 5). It still has more on it than a new computer: GitHub's machines come with many libraries and tools. A person installing a release on their own computer: NOT RUN. |
| **What the `.deb` says it needs** | Tried only on machines that had all of it already. A bare system would show a missing name; none is run. |
| **macOS**: the end-to-end suite does not run there | The release build and its installer are built and started on macOS by every push; the journeys run on Windows and Linux only. Nobody has looked at Adle on a Mac. |
| **Installers** cannot be tried on the computer Adle is developed on | By decision (ADR-034): they are made and tried on GitHub's machines, which have the tools and can be thrown away. |
| **Visual regression** is manual (screenshots captured, not diffed) | Left open. Baselines differ between machines and fonts; a person looks at `test-results/screens`. |
| **Screen reader** behaviour is inferred from roles and axe, not tested with a real reader | NOT RUN. Needs a person. |
| **Performance** is measured on one machine | `docs/engineering/PERFORMANCE.md`, by `scripts/measure.mjs`. Large courses, large documents, and memory are not measured. |
| **AIHubMix's free model** has never answered | BLOCKED at the provider (a relay error for one account; the other must be topped up). Every path is tested against a stand-in. |
| **NVIDIA NIM** was tried by hand, not by a test | By design: no test may call a real provider. What was sent, what came back and how long it took on 2026-11-20 is in ADR-021 and `PROJECT_STATE.md`. |
| Complex PDFs (multi-column, tables, equations) are not among the fixtures | Add them when extraction quality is worked on. |
| Vector retrieval | Not built; search is FTS5 only (ADR-007). |
