# services/core — the Python core

Read the root `AGENTS.md` first. This service owns all learner data and makes the only outbound
network calls. It is started by the Electron main process (ADR-002) and listens on loopback only.

## Commands

From the repository root (they run inside `services/core` via `uv run --directory`):

| Task | Command |
|---|---|
| Install / update the environment | `npm run core:sync` |
| Lint and format check | `npm run core:lint` |
| Auto-format and fix | `npm run core:format` |
| Type-check (mypy strict) | `npm run core:typecheck` |
| Tests | `npm run core:test` |
| One test | `uv run --directory services/core pytest tests/unit/test_scene_policy.py -k hostile` |
| Run by hand | `echo '{"token":"<32+ chars>"}' \| uv run --directory services/core python -m adle_core --data-dir ./var/dev` |

Add a dependency with `uv add <name>` (or `uv add --dev <name>`) inside `services/core`; commit
`pyproject.toml` and `uv.lock` together. Check the licence first: no GPL/AGPL.

## Layout and layering

```text
adle_core/
  errors.py       AdleError and friends (no framework imports; usable everywhere)
  api/            FastAPI app factory, auth, error contract, schemas, routes (no domain logic)
  application/    service container; courses (and a course as a file: course_file,
                  course_sharing), sources, jobs (four lanes), curriculum,
                  learner, retrieval, lessons, asks (questions put to Adle during a lesson),
                  generation and the model gateway, saving and restoring a copy of the data
  curriculum/     PURE rules: concept graph (loops, order, layers), outline from headings
  learner_model/  PURE rules: knowledge tracing, mastery states, review schedule, preferences,
                  hypotheses about mistakes, which questions to practise, the next step,
                  the latest sitting
  lessons/        PURE: the Lesson IR, the validating gateway (bundle.py), the player view
  evaluation/     PURE: deterministic scoring of answers
  sample_course/  package data: course outline, lesson templates, scene files
  domain/         pure models shared across areas (empty so far)
  infrastructure/ database, ORM models, migrate (with backup), asset store, ids
  migrations/     Alembic revisions (shipped inside the package)
  ingestion/      type detection, parsers, chunking, the parser worker process
  generation/     provider credentials and client, quota rules (pure), routing (pure: which
                  provider a request goes to), scene policy, drafts (what a model writes ->
                  Lesson IR, or an answer), prompts, data/ (generated files)
  voice/          a natural voice (ADR-042): what is downloaded, pinned (catalog), what
                  this computer can run (hardware), where it lives and the engine process
                  (runtime), setting it up (install), the locks of its programs (data/),
                  and engine.py, which runs in the voice's own environment and is never
                  imported by the core
  film/           a film of a whole course (ADR-065): the film maker pinned (catalog),
                  where it lives and running it (runtime), setting it up (install), what a
                  chapter may be (policy), what the engine says of a scene (report), the
                  files Adle writes around a chapter (script), a chapter's storyboard and
                  what is seen in it (storyboard, ADR-066), and data/ (the writer's guide
                  and example, the engine's names, the locks of its programs)
  orchestration/ audio/   empty: the computer's voice is the browser's (ADR-013), and jobs
                  are run by application/jobs.py
  tools/          developer entry points (contract export)
tests/unit/        fast, isolated
tests/integration/ real process, real database, fake provider
```

`curriculum`, `learner_model`, and `domain` are pure: no database, no framework, no clock except
one passed in. They import nothing from `application`, `infrastructure`, or `api`, and they are
where rules are decided and property-tested. `application` loads and stores; `api` may import
everything and decides nothing.

## Rules

- **Every route** has `operation_id="area.action"`, named Pydantic request/response models, and
  sits behind the launch-token dependency (applied app-wide). Then run `npm run contracts`.
- **Nothing of a request is read before `api/gate.py` has let it in**: the token first, then
  a bound on the body (ADR-029). The dependency stays as a second check. Do not add a
  middleware in front of the gate, or a route that needs a larger body.
- Routes only the main process may call get `openapi_extra={"x-adle-internal": True}`.
- **Errors:** raise an `AdleError` subclass with a stable `code` and a learner-readable message.
  Never return framework error shapes; never put submitted values or internals in a message.
- **Secrets:** the provider keys live in `CredentialVault` (memory), one per provider. Never
  write one anywhere, include it in a model's `repr`, or log it. Loggers carry
  `SecretRedactionFilter` as a backstop, for every key held.
- **A key goes to its own provider and nowhere else** (ADR-021). A `ChatClient` is bound to
  one provider and reads `vault.api_key(config.provider_id)`: never the "current" key. Do
  not add a client that can be pointed at another address after it is made.
- **Which providers may be used is the learner's choice**, held by the vault (one provider's
  name, or `"auto"`) and changed only through `GenerationService.select_provider` (refused
  while a job is writing). Never change it because something failed.
- **Where a request goes is decided in `generation/routing.py`**, a pure module, and applied
  only by `ModelGateway`. With one provider chosen the plan is that provider alone. With
  `"auto"` it is the providers that have a key, best first for the request's `purpose`
  (`ask`, `curriculum`, `check` are waited for; `lesson`, `scene` are long work). A new
  kind of request needs a purpose there. Never add a path that reaches a provider without a
  key of its own (ADR-023).
- **Logging:** log event types and identifiers, not document text, answers, or prompts. The
  text of an exception can hold any of those: log an error with `logs.where(error)` (its
  kind and where it happened), never with `logger.exception` or `exc_info`. The database
  keeps a statement's values out of its errors (`hide_parameters`).
- **Paths:** store only under `Settings.data_dir`, under generated names. Never use a
  user-supplied path as a destination. The one exception is `data.save_copy` (ADR-016): an
  internal route that writes a copy of the data where the learner chose in a save dialog.
  Do not add a second.
- **A course as a file** (ADR-063). What is in one, and reading one from anywhere, is
  `application/course_file.py`: a zip of JSON parts, each a closed Pydantic model
  (`extra="forbid"`), read by a member name this module made and never past a bound
  that does not trust the file's own sizes; nothing is ever extracted, and a member of
  any other name refuses the file. Saving and bringing in is
  `application/course_sharing.py` (`CourseFileService`). **Bringing in makes a new
  course and goes by the ordinary roads**: `CurriculumService` for concepts and what
  they need, `parse_bundle` then `LessonService.store` for a lesson (one that cannot
  be used is left out and counted), `SourceService.add_copied` for a document's
  sections and passages, `LearnerService.replay` for what the learner showed (each
  observation recorded as any other, so no state comes from a file). Identifiers in
  a file are only names for its own parts: everything gets a new one (`_renamed`). A
  course from a file is never `sample`, and half a course is deleted again. A new
  part of a course is a new model there, a line in `Holds` if the learner chooses
  it, and a test with a hostile one. **The core writes a course file only under
  `Settings.handover_dir`**, under a generated name it returns; the desktop shell
  moves it. Its three routes are internal, and the two that read take a path the
  learner chose in a dialog, like `sources.import_paths`.
- **The core's part of a settings file** (ADR-064, `application/settings_file.py`): the
  learner's preferences and the voice, saved as plain values and brought in one
  setting at a time, each only if it is a value it may have (`from_stored`). The file
  itself, and everything about keys, is the desktop shell's: these routes are internal,
  take no path, and never see a key. `plan` says what a file's voice would be on this
  computer (the one named, the nearest lighter one that fits, or none) and changes
  nothing; `bring_in` sets a voice up only when told the learner said so
  (`set_up_voice`), and says in `notes` whatever could not be had as the file has it.
  A new setting the core keeps is a value in `save` and a line in `bring_in`.
- **A copy of the data is one self-contained file.** Make one with `backup_database` and
  nothing else: it includes the write-ahead log and leaves the copy in SQLite's single-file
  mode, so that looking at it creates nothing beside it.
- **The database is replaced only while the service starts**, by `data_copy.restore_copy`,
  before `build_services`. Never add a route that swaps or deletes it: every service holds
  connections. A restore is all or nothing; keep it so (`test_data_copy.py`).
- **Nothing may depend on a stored original being present.** A copy does not carry the files
  that were imported, and after a restore the ones nothing refers to are removed.
- **A database file may come from anywhere.** Connections are opened with
  `trusted_schema = OFF`; do not turn it back on to make a trigger or a view work.
- **SQL:** parameterised only.
- **Two kinds of unit of work** (ADR-015). `database.read()` for anything that only reads: it
  cannot write, takes no lock, and never waits. `database.session()` for anything that may
  write: it takes the write lock when it begins. Never open a `session()` inside another (it
  is refused at once); finish the first, or make the inner one a `read()`. Nothing slow
  (parsing, a model request) happens inside a `session()`.
- **Untrusted input:** imported documents and model output are data. Validate model output with
  Pydantic and reject unknown fields; scene source must pass `scene_policy.check_scene_source`.
- **A page with no text to select is kept as a picture** (ADR-060): `picture_pages` on
  the document and the source, said to the learner by `picture_sentence`; a PDF of nothing
  but pictures is imported. It is read only at the learner's word (`sources.read_pictures`,
  `SourceService.start_reading`): drawn by PDFium in the parser worker (`ingestion/render.py`,
  `render_isolated`), sent one page a request (`prompts.read_page_request`, purpose `read`)
  only to a model whose `ModelSpec.images` is set, after it was seen to read a picture by
  hand. A provider without one does not serve `read` (`ProviderConfig.serves`,
  `routing.Standing.serves`): chosen alone, nothing is sent (`PicturesUnreadableError`).
  What comes back is stored as the page in its place (`_store_read_page`, numbered again,
  confidence 0.8); removing the file stops the reading.
- **A PDF is cut into sections by its outline, else by its numbered headings, else by its
  pages** (ADR-046, `ingestion/parsers.py`). A course plan for materials without headings
  is asked with how each page begins (`CurriculumService.page_openings`). A change to how a
  parser reads a file raises `PARSER_REVISION`.
- **stdout is a protocol channel** (`ready` / `fatal` JSON lines). Do not `print`; use `logging`.
- **Child processes:** never `multiprocessing`. Start children with `subprocess` and pass
  `stdin`, `stdout`, and `stderr` explicitly (`PIPE` or `DEVNULL`). The service keeps a thread
  blocked on its own stdin; on Windows a child that shares that handle hangs at start-up
  (ADR-007). Exchange JSON with children, not pickle. Start a Python child with
  `interpreter_flags()` (`ingestion/extract.py`), so that it is as isolated as its parent.
  What a child says about a file is shown to the learner only if its reason is one a parser
  has, as one plain line (`_refusal`): a new reason for refusing a file is a new entry in
  `_REFUSALS`. The voice's children (`venv`, pip, the engine) keep the same rules; they run
  on another Python, with `-I`, and with none of this computer's settings for pip or Python.
  So does the film engine, with nothing of this computer's at all (`bare_environment`).
- **The service ships as a wheel inside a private Python** (ADR-019), started with `-I`.
  So: anything read at run time is package data inside `adle_core/` and is found with
  `importlib.resources`, never by a path relative to the repository; nothing may depend on
  the current folder, on `PYTHONPATH`, or on a package that is not in `uv.lock`; and a new
  run-time dependency is a new line in `docs/engineering/THIRD_PARTY.md`
  (`npm run licenses`).
- **Schema changes** need an Alembic revision in `adle_core/migrations/versions/` and the matching
  model change in `infrastructure/orm.py`; `test_database.py` fails if they disagree. Author one
  with `ADLE_DATA_DIR=./var/dev uv run alembic revision --autogenerate -m "..."`, then review it
  by hand (virtual tables and triggers are always hand-written).
- A method named `list` on a class shadows the builtin in that class's later annotations (mypy
  rejects it). Use `list_all`, `list_for_course`, and so on.
- **The curriculum stays learnable.** Every write goes through `CurriculumService`, which asks
  `curriculum.graph` first. Do not insert concepts or edges any other way (ADR-009).
- **Learner knowledge** changes only through `LearnerService.record`. `learner_observations` is
  append-only and is the source of truth; `learner_concept_states` is derived and rebuildable.
  Never update a state row by hand.
- **A lesson is stored only through `lessons.bundle.parse_bundle`**, then
  `LessonService.store`. Never build a `LessonBundle` from input by hand, and never trust what
  input says about a scene: `inspect_scene` computes it. `LessonService.get` re-checks scenes
  on every read and withholds what fails (ADR-010).
- **Answer keys do not leave the core.** `lessons.get` returns `player_view(lesson)`. A new
  field on a question must be added to `lessons/player.py` deliberately; `test_lesson_ir.py`
  fails if a key leaks into the player view. An id can be a key too: the items of an
  ordering question are shown under names made by `ItemMask`, in the order of those names,
  and `AssessmentService` turns them back. Never show their own ids, and never shuffle with
  something the page could work out again.
- **An answer is recorded once, whole:** the attempt and its observation in one transaction
  (`AssessmentService.answer`). Scoring is deterministic; anything a model helps judge (M6) is
  bounded by a rubric and marked as such.
- **A hypothesis about a mistake is never stored.** It is folded from attempts and dismissals
  by `learner_model.misconceptions.fold` (read them with `application/evidence.py`). Do not add
  a table or a cache for it. What reaches the knowledge state is one flag on the observation.
- **What to do next, and which questions to ask, are decided in `learner_model/next_step.py`
  and `practice.py`.** `LearningService` gathers and translates; it must not grow an `if` that
  chooses. Every `Step` needs a reason a learner could disagree with, with no score in it
  (`test_practice_and_next_step.py` checks every reason).
- **Never suggest the same lesson again after it did not work**, and never suggest practice for
  something practice cannot supply. Both are tests; keep them passing rather than special-casing.
- **A session is a sitting, computed by `learner_model/sitting.py`** (ADR-017). Do not store
  one, and do not add a "session" row or a start or end event. It reports counts of right
  answers and the words `mastery.py` already produced; it must never contain a rate, and a
  sitting must never be what makes a concept "demonstrated".
- **Time is an argument.** Anything that depends on "now" (`AssessmentService.answer`,
  `LearningService`) takes `now`; routes do not pass it. Tests move the clock that way.
- **`learner_events` is append-only** and holds only events something reads. Adding a kind means
  a migration (the kinds are a CHECK constraint) and a reader.
- **"This did not help" can be taken back** (ADR-054): `lessons.withdraw_unhelpful` writes an
  `explanation_unhelpful_withdrawn` row after the report, which withdraws every report about
  that part of that lesson made before it. Read reports only through
  `evidence.standing_reports`, never by their kind alone. A lesson says which of its parts
  stand reported (`LessonForPlayer.unhelpful_parts`).
- **A question's `reveals` is stored with each attempt** (`evaluation.scoring.reveals`), as it
  was when answered. A right answer counts against a hypothesis only if the question could have
  shown it.
- **Sample content** is addressed by key in templates (`@concept:weighted_sum`) and installed
  through the ordinary services. Scene files there are excluded from ruff and mypy: they are
  Wanim scenes, not service code.
- **A model request goes through `ModelGateway.complete`**, from inside a job. Nothing else
  may call `ChatClient`. Do not add sampling parameters, retries, or a second request "to fix
  it": the number of requests per job is fixed in `application/generation.py` (ADR-012).
- **A lesson is stored as soon as its first part is written** (ADR-048): the answer is
  read as it arrives (`generation/stream.py`), and `_GrowingLesson` stores the lesson at
  its first whole part with `writing` set, then adds each later whole part after the last
  with `LessonService.extend`, which puts the whole lesson through `parse_bundle` again.
  A part already stored is never changed; a later part that cannot be used is left out
  and said; once begun the lesson is never written again (no retry, and no other model
  stood in: `_LessonBegunError` ends the answer instead), and whatever ends the answer
  keeps what there is and ends the writing (`close`, then `cut_short`). Until the first part is whole the whole answer
  decides, with its one retry, as it always did. Each figure is tried and settled as its
  part is stored; the job reports the `drawing` stage once every word is written. Who
  writes it is stored with its first part (`on_writer`).
- **A lesson's pictures follow its words** (ADR-031), with the pictures it is
  waiting for in `pending_scenes`. A picture reaches a stored lesson only through
  `LessonService.settle_scene`, which puts the whole lesson through `parse_bundle` again:
  with the picture, or with that part turned into words. Nothing may be left waiting once
  the work has ended, however it ended (`settle_unfinished`, also run when the core
  starts). A job says what can already be used with `JobContext.publish`; a lesson job's
  result therefore exists while it is still running.
- **Removing something stops the work for it** (`stop_for_lesson`, `stop_for_course`, called
  by the routes that delete). Nothing more is asked of a provider for what the learner has
  thrown away. A test of this must not wait longer than a stand-in for a slow answer
  takes to let go by itself, or it passes without the stopping.
- **Jobs run in four lanes** (`application/jobs.py`). Long work (an import, a lesson, a
  list of concepts) runs one at a time in the main lane. What the learner waits for (an ask,
  a check of a key) runs in the quick lane, so it never queues behind a lesson. A natural
  voice's work (setting one up, recording a lesson, a film's lines) runs in the voice lane,
  one at a time, so that a recording never runs while its programs are being replaced. A
  film, and setting up what makes it, run in the film lane: an hour of it holds nothing
  else up. As many requests are in flight at each provider as it takes (`at_once`: one at
  AIHubMix, six at NVIDIA, ADR-068), whichever lane asks; within a job, pieces asked for
  side by side go through `jobs.side_by_side` (a film's chapters, three at most; a file's
  pages, four at most), which stops the rest at the first failure or the learner's Stop.
- **A natural voice is set up only by `VoiceInstaller`, at the learner's word** (ADR-042).
  A model file is kept only if its size and hash are the catalogue's; a program only from
  the lock for this system, by its hash. A new file is a new pinned entry; a new version of
  a program is `scripts/dev/voice_locks.sh`, then each voice set up by hand. Only the
  voice's own folders are ever removed (`VoicePaths.environment`), never a Python a
  developer pointed Adle at (`borrowed`).
- **A film of a whole course** (ADR-065, `application/films.py`) is a chapter for each
  concept in learning order, each one complete ManimGX file a model writes
  (`prompts.film_chapter_request`, purpose `film`). **A chapter is code a model wrote,
  run outside the player's frame**, so: nothing of it runs before `film.policy`
  (`check_chapter_source`) passed it; it runs only as a module imported by Adle's own
  files (`film.script`: `take_source`, `film_source`, and `voice_source`, which takes
  the network away from the process and gives every scene Adle's voice instead of the
  engine's, an internet service); and only through `FilmEngine` (`film.runtime`), with
  `bare_environment`, in the film's folder, for a bounded time. The engine's home is
  kept between runs (`FilmPaths.home`, inside the film maker's folder): in a home never
  used, the engine's first run never ends, and every run after it, once it is ended, takes
  seconds. So `FilmEngine.prime` runs a small scene and ends it after `PRIME_SECONDS`
  before the setup's trial and before each film, and a chapter that runs out of time is
  looked at once more before it is blamed (`_looked_at`). The policy's names are
  the pinned engine's (`film/data/names.json`, from `scripts/dev/film_names.py`): never
  add a name to make a chapter work without reading what it reaches. An engine name used
  bare (`WHITE` for `m.WHITE`), or `np` or `math` not imported, is mended, not sent back
  (`policy.with_engine_names`), and so is a line given a run time of its own
  (`policy.with_timing_passed_on`: it goes to the line's animations) and a line with more
  bracketed spans than animations (`policy.with_spans_fitted`: the spans after the last
  animation lose their brackets, and what is said stays the same); the file is then
  checked as any other. A
  line with fewer spans than animations is sent back, never guessed. A chapter is asked
  for once and sent back `script.MAX_MENDS` times at most, told the policy's or the
  engine's findings (`report.findings`, by the chapter's own line); the version that ran
  with the least wrong is kept, and one that never ran is told in words
  (`script.plain_chapter`, which quotes the course's words only through
  `policy.text_problem`). A chapter sent back is shown back whole, up to the policy's
  `MAX_SOURCE_CHARS`: a chapter is 12,000 to 16,000 characters. What the engine said is
  told to the model and logged by count only. **A chapter's pictures are looked over once**
  (ADR-066): the storyboard `inspect` draws beside the take (`storyboard.sheets`, cleared
  before each run by `FilmEngine.inspect`, at most eight sheets, PNGs only) goes in one
  request (`prompts.storyboard_request`, purpose `storyboard`, so only to a model whose
  `ModelSpec.images` is set) with what is said while each animation plays
  (`storyboard.told`); the answer, a line a fault by picture, becomes what the writer is
  told by its own line (`storyboard.seen`), in the same mends (`_together`): when a version
  first runs clean while a mend is left, or before the last mend. Never a second look, and
  nothing waits on one: a look refused or failed, or no such model by the learner's choice
  (`FilmService._looks`), and the chapter is kept as it ran. The plan counts it
  (`checks_pictures`, `requests_at_most`). A film's lines are recorded by `NarrationService.record_film` into the film's
  folder; `script.engine_words` gives the engine a time for every run of the line. The
  film maker is set up only by `FilmInstaller`, at the learner's word, from the pinned
  Python and the lock for this system, and removing it takes only its own folder. A film
  stopped, failed, or left when the core stopped is `unfinished` (`settle`), and
  continuing begins at the first chapter not kept. Removing a film or its course stops it
  (`stop_for_course`, called before the course is deleted).
- **Looking for work that is under way and starting it are one step**
  (`GenerationService._starting`). Two requests arriving together must not both find
  nothing and both begin, and the provider must not be chosen under a job that has just
  started. A new way of starting model work takes the same lock around its look and its
  `submit`.
- **An ask is a note, not evidence** (`application/asks.py`, ADR-024). Only its existence is
  ever read by anything else: an answer to a checkpoint given after an ask about that part
  is an aided answer. Removing one takes its words and leaves the row (`REMOVED`), so that
  it still counts; a skip counts too, because it shows the explanation. Never send an answer key in `prompts.ask_request`: see
  `_part_brief` for what a part may show a model. **An ask can have its part's picture
  drawn again** (ADR-067, `redraw=True`): only for a part in `lessons.DRAWN_AGAIN` whose
  picture is not still coming; one request, two at most, purpose `lesson`
  (`prompts.redraw_request`, with the part's words marked where its steps play,
  `_marked_steps`); the answer read by `drafts.compile_redraw` (a slide, drawn and paced to
  the words, never one with a slider) and kept in the note's answer (`picture`). It joins
  the lesson only through `AskService.use_picture`, which swaps the part's scene and cues
  with `lessons.replace_picture` (the whole lesson through `parse_bundle`) and keeps what
  the part had; `put_back`, and removing the note, give it back. A note in a course file
  carries words only.
- **A provider's models are tried in order** (ADR-021), and only `ModelGateway` decides
  which. The next is asked when the one before is away (`ProviderModelUnavailableError`:
  gone, failing, or silent) or will not take its request (400, 422). Not for a refused key,
  a rate limit, a provider's notice, or a provider that cannot be reached. Pass
  `on_fallback` and `on_stage` on to the job's progress, and record `written_by` with
  anything a model wrote: a stand-in is never left unsaid.
- **Each model is sent only what its reference lists** (`ModelSpec`). Adding a field means
  reading the model's page, then trying it against the real endpoint by hand: the page has
  been wrong in both directions.
- **Each provider is counted alone** (`model_usage.provider`), against `ProviderConfig.limits`.
  Where a provider publishes no limits, set `limits_published=False` so the interface does
  not call Adle's caution "the provider's limit".
- **"Stop" and the time limit are checked on everything that arrives**, complete line or
  not: a model's thinking and a provider's keep-alives arrive for minutes before the first
  piece of an answer does, and a provider may send no line ending at all. An answer is read
  with a bound on a line and on the whole (`_lines`), is asked for uncompressed, and is
  closed when the learner stops it.
- **A provider can answer in the model's place.** `ChatClient` raises `ProviderNoticeError`
  for a successful answer that the provider wrote itself (ADR-020). It carries the
  provider's words through `clean_notice`: quote them to the learner, never log them, never
  act on them, and never retry. Any other text that comes from a provider and is to be
  shown goes through the same function.
- **A model writes a draft; the core writes the lesson.** Identifiers, objective links,
  citations, and durations are assigned in `generation/drafts.py`. A citation is a number the
  prompt offered, or it is dropped.
- **A slide is data; the core lays it out and writes its scene** (ADR-049,
  `generation/slides.py`): elements and steps checked one by one, what cannot be drawn left
  out and said (by count in the log, never its words). A model's text reaches the scene only
  as a quoted literal and a curve's formula only through `_python_expression`, as for a
  figure. The narration's [brackets] become `Beat.cues` in `drafts` (`_marked`, `_cued`,
  `_paced`); a scene's `steps` are counted by the policy, never read from input. A slide's
  scene ends with the script it was drawn from (`SCRIPT_MARK`, its JSON in base64, read
  back with `slide_script`, ADR-067), so that a part's picture can be drawn again from what
  it is: never read it for anything but a model's data, drawn again through
  `compile_slide`. A new kind
  of element or verb is a template, an example in `tools/export_slides.py`, and
  `npm run slides` (the player steps through every example). The examples a lesson's
  writer is shown (`generation/examples.py`) are among them: change one and run
  `npm run slides`.
  The case comes first (ADR-050): `defer_theory` moves a formula or a rule that a first
  step shows beside its case to the next step, and `show` with `from` makes a formula's
  `{{ }}` parts out of copies of the picture (`TransformFromCopy`, then the whole formula
  put back as one thing).
- **How a lesson is formed is written in `lessons/axioms.py`** (ADR-061), pure: the rules
  of every lesson (`AXIOMS`) and what each subject needs besides (`SUBJECTS`), each as a
  line for the learner and a brief for the writer. `prompts.lesson_request` gives the
  writer the rules, the needs of the course's subject, and that subject's example part
  (`generation/examples.py`, `Subject.example`): one subject at a time, never all of them.
  Do not write teaching advice into `prompts.py`. A new subject is an entry there, its key
  in `schemas.SubjectKey` (a test keeps them equal), and an example; an example obeys the
  rules it is an example of (`test_lesson_axioms.py`) and is a slide the player steps
  through. A course's subject (`courses.subject`, `subject_by_adle`) is placed by
  `courses.place` (a guess from its name, `axioms.guess`, which names nothing when two
  subjects are as likely), by the AI with its plan (`place_as`, in the plan's own request),
  or by the learner (`CourseService.update`), whose choice stands; a lesson of a course
  nobody has placed is formed by a guess from its concept (`generation.subject_of`).
  Nothing asks a model what subject something is in a request of its own, and the ways of
  teaching tried for another explanation are those that suit the subject (`next_strategy`).
- **A timeline, a vessel, a molecule and code are elements like the rest** (ADR-061,
  `generation/slides.py`). A vessel draws everything it will ever show where it goes
  (`vessel_seen` reads the steps as written) and keeps what has not happened off the stage
  (`_Scene.vessels`, `seen`); its shapes are worked out here, not in the scene
  (`_VESSEL_PROFILES`). A molecule's atoms are placed by the core (`_molecule_places`).
  Code is drawn a line at a time in the stage's own face (the player has one), each line
  where a block of them would have it (`make_code`). A link in anything an element says
  costs the picture that element (`names_a_link`), never the whole slide. Nodes stand as
  far apart as their names are wide (`_node_places`).
- **A picture keeps its words clear of each other and of the edge** (ADR-055,
  `generation/layout.py`, written into every slide and figure). A label is placed with
  `self.pin(label, anchor, side, buff)`, never with `next_to` alone, unless it is drawn
  again each frame (it follows something); `tidy` at the end of `build` moves a pinned
  label to the first clear side; a point's name keeps to a clear place (`self.sides`:
  side, distance, whether it was clear, and where its point was), and where none was clear
  looks again only once its point has moved 0.2: a search every frame stalls a slide.
  Each step, and each figure's page, ends with `self.audit()`, which says `layout` when
  words overlap, a line runs through a word (ADR-056: a `Line` of any kind, a
  `ParametricFunction`, or a `NumberLine`, which draws an axis itself, ADR-058, through
  the middle of its box), or something lies past the edge:
  the journeys fail on it for every example, so a template that puts words over words is
  found by `npm run e2e`. A drawing over a drawing is usually meant and is not looked at.
  The methods live on the scene: a name they take (`still_lines`, `lines_of`, `pin`, ...)
  must not be one a template already uses, or the template's is replaced. A slide's step is no longer
  than its words (`_fitted`, from `drafts._step_seconds`): never slower than written,
  never quicker than 0.45 of it.
- **A lesson's model does not think first** (ADR-049): what thinking used to catch is
  caught in `drafts` instead, deterministically (`_distinct_options`: a wrong option equal
  in value to the right one is left out; `_worked_to`: a numeric key its explanation
  does not reach is not used). Do not turn thinking back on to fix a kind of slip: catch
  the slip here, with a test from the answer that showed it.
- **A figure is data; the core writes its scene** (ADR-045, `generation/figures.py`): a kind
  from a fixed list, each a template filled with checked values. A model's text reaches the
  scene only as a quoted literal, and a formula only as Python written again from a tree of
  arithmetic and comparisons; the core runs a formula only through `_function`, on what
  `_python_expression` wrote, with no builtins. A new kind is a template, an example in
  `tools/export_figures.py`, and `npm run figures` (the player runs every example in both
  themes). A figure passes the policy, is tried in the player and is settled like a scene.
- **What can be mended in a lesson's answer is mended, not asked for again** (ADR-047):
  notation in narration is said in words (`generation/speech.py`, pure; a line with a link
  or markup is left as it is, to be refused), mathematics typed with the keyboard too
  (`_typed`: a factorial, "!=", "<=", "->", a list that goes on, ADR-057); a practice question that is not whole is left
  out (`LessonDraft`); a board line left open is left off; a figure that cannot be drawn is
  told in words, and a shade under a cumulative curve is drawn as its rise. Anything else
  that does not validate is still the one retry, told what was wrong.
- **A course left unnamed is named by Adle** (ADR-053, `courses.named_by_adle`): from its
  first file (`SourceService._store`), then from the suggestions' `course_title`; never
  once the learner names it (`CourseService.update` clears it). **A proposal with
  `setup`** adds everything suggested and begins the first lesson
  (`GenerationService._set_up`): the learner asked for it in advance; without `setup`
  nothing is added until the learner picks (ADR-012).
- **A lesson in a natural voice is made with its voice** (ADR-051). `build_services` wires
  it: `on_begun` warms the voice as a lesson is asked for (`NarrationService.warm`, a job
  in the voice lane that loads the models), `on_stored` starts or wakes the one recording
  that follows the lesson part by part until it is whole (`record_ahead`, `_record`),
  `voice_pending` says whether its first part can be heard yet (the lesson job's
  `voicing`), `on_voiced` tells the lesson job when more can be, and `ready_after` counts
  the voice in how long a lesson usually takes. Every voice is timed where it runs
  (ADR-052, `voice/timing.py`, pure; kept in `voice/timing.json`): at setup
  (`VoiceInstaller.verify` says a first part's worth from cold), by every line once loaded,
  and by every lesson made; a voice slower than speech there makes `voice_pending` wait
  for a head start (`kept_ahead`). Never assume a voice is fast. The engine is kept loaded between
  recordings (`_Engines`) and closed before a voice is set up or removed and when the
  core stops. It does nothing when no voice is chosen. What is said never changes after a
  part is stored: a picture that does not come changes what is shown, not what is said.
  **A voice the learner shapes** (ADR-057): two natural voices (`TIERS`); one no longer
  offered is in `RETIRED` and taken off a computer as the core starts (`_retire`). The
  Expressive voice is the learner's description (`status().design`) plus the lesson's
  delivery (`Lesson.voice`), designed saying `REFERENCE_TEXT`. **The description can be
  put together from parts** (ADR-062, `voice/design.py`, pure): who speaks, age, pitch,
  pace, tone, feeling, steadiness, accent, style, each a choice with a name for the
  learner and a phrase for the voice; `compose` writes the one sentence they make (no
  parts at all is `DEFAULT_DESIGN`), and nothing else writes it, because a recording is
  named by its description. The parts are kept beside the description
  (`design_parts`) and are only how it was made: `parts_of` lets them go once they no
  longer make it (the learner wrote over it, or a version changed a phrase), and the
  description goes on being read as it is. Voices to start from are choices of parts
  (`PRESETS`). A new part or choice is an entry there; changing a phrase changes every
  voice made with it, so add, do not reword. A change of voice (`_identity`) records the lessons opened last at once
  (`_record_recent`, `start(ahead=True)`); a recording follows the voice chosen line by line,
  and lessons recorded ahead step aside for what the learner opens or a sample
  (`_step_aside`). Samples are made in the voice lane and kept under `samples/<size>/`.
  Every voice's clips are kept; only removing a voice removes them.
- **Text from the learner or their documents goes in a `_block(...)`** in `prompts.py`. Never
  concatenate it into an instruction. That includes what a document is called: a file's
  name and a heading go inside the block with the excerpt (`_excerpt`).
- `adle_core/generation/data/` is generated (`npm run wanim-names`, `npm run scene-guide`) and
  excluded from ruff. Do not edit it by hand.
- **No score leaves the core.** `api/schemas.py` must not expose the tracing estimate or anything
  that reads like a percentage. The interface gets a state, a label, and what is missing.
- **Text shown to the learner about their knowledge** is written in `learner_model/tracing.py`
  and `mastery.py`. Keep it free of blame and of numbers that imply precision.
- Tests that need "a later version of the schema" use `use_migrations_with_extra_revision` in
  `test_database.py`, which chains a test-only revision after the real newest one.
- No provider call in any test. The `provider` fixture (`tests/support/model.py`) answers in
  process; queue answers, failures, or nonsense with `provider.queue(...)`. The test container
  lifts the per-minute limit so a test with five requests does not wait a minute.

## Style

Ruff (rules in `pyproject.toml`) and mypy strict must be clean. Type-annotate everything. Prefer
frozen dataclasses for domain values and small functions over classes with hidden state.
Docstrings explain decisions and invariants, not what the next line does.
