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
  application/    service container; courses, sources, jobs (three lanes), curriculum,
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
- **Jobs run in three lanes** (`application/jobs.py`). Long work (an import, a lesson, a
  list of concepts) runs one at a time in the main lane. What the learner waits for (an ask,
  a check of a key) runs in the quick lane, so it never queues behind a lesson. A natural
  voice's work (setting one up, recording a lesson) runs in the voice lane, one at a time,
  so that a recording never runs while its programs are being replaced. One request is in
  flight at each provider, whichever lane asks.
- **A natural voice is set up only by `VoiceInstaller`, at the learner's word** (ADR-042).
  A model file is kept only if its size and hash are the catalogue's; a program only from
  the lock for this system, by its hash. A new file is a new pinned entry; a new version of
  a program is `scripts/dev/voice_locks.sh`, then each voice set up by hand. Only the
  voice's own folders are ever removed (`VoicePaths.environment`), never a Python a
  developer pointed Adle at (`borrowed`).
- **Looking for work that is under way and starting it are one step**
  (`GenerationService._starting`). Two requests arriving together must not both find
  nothing and both begin, and the provider must not be chosen under a job that has just
  started. A new way of starting model work takes the same lock around its look and its
  `submit`.
- **An ask is a note, not evidence** (`application/asks.py`, ADR-024). Only its existence is
  ever read by anything else: an answer to a checkpoint given after an ask about that part
  is an aided answer. Removing one takes its words and leaves the row (`REMOVED`), so that
  it still counts; a skip counts too, because it shows the explanation. Never send an answer key in `prompts.ask_request`: see
  `_part_brief` for what a part may show a model.
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
  `_paced`); a scene's `steps` are counted by the policy, never read from input. A new kind
  of element or verb is a template, an example in `tools/export_slides.py`, and
  `npm run slides` (the player steps through every example in both themes). The prompt's
  own example (`prompts.visual_example`) is one of them: change it and run `npm run slides`.
  The case comes first (ADR-050): `defer_theory` moves a formula or a rule that a first
  step shows beside its case to the next step, and `show` with `from` makes a formula's
  `{{ }}` parts out of copies of the picture (`TransformFromCopy`, then the whole formula
  put back as one thing).
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
  or markup is left as it is, to be refused); a practice question that is not whole is left
  out (`LessonDraft`); a board line left open is left off; a figure that cannot be drawn is
  told in words, and a shade under a cumulative curve is drawn as its rise. Anything else
  that does not validate is still the one retry, told what was wrong.
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
