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
  application/    service container; courses, sources, jobs, curriculum, learner, retrieval
  curriculum/     PURE rules: concept graph (loops, order, layers), outline from headings
  learner_model/  PURE rules: knowledge tracing, mastery states, review schedule, preferences,
                  hypotheses about mistakes, which questions to practise, the next step
  lessons/        PURE: the Lesson IR, the validating gateway (bundle.py), the player view
  evaluation/     PURE: deterministic scoring of answers
  sample_course/  package data: course outline, lesson templates, scene files
  domain/         pure models shared across areas (empty so far)
  infrastructure/ database, ORM models, migrate (with backup), asset store, ids
  migrations/     Alembic revisions (shipped inside the package)
  ingestion/      type detection, parsers, chunking, the parser worker process
  generation/     provider credentials and client, quota rules (pure), scene policy,
                  drafts (what a model writes -> Lesson IR), prompts, data/ (generated files)
  orchestration/ audio/   (M5–M6)
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
- Routes only the main process may call get `openapi_extra={"x-adle-internal": True}`.
- **Errors:** raise an `AdleError` subclass with a stable `code` and a learner-readable message.
  Never return framework error shapes; never put submitted values or internals in a message.
- **Secrets:** the provider key lives in `CredentialVault` (memory). Never write it anywhere,
  include it in a model's `repr`, or log it. Loggers carry `SecretRedactionFilter` as a backstop.
- **Logging:** log event types and identifiers, not document text, answers, or prompts.
- **Paths:** store only under `Settings.data_dir`, under generated names. Never use a
  user-supplied path as a destination.
- **SQL:** parameterised only.
- **Two kinds of unit of work** (ADR-015). `database.read()` for anything that only reads: it
  cannot write, takes no lock, and never waits. `database.session()` for anything that may
  write: it takes the write lock when it begins. Never open a `session()` inside another (it
  is refused at once); finish the first, or make the inner one a `read()`. Nothing slow
  (parsing, a model request) happens inside a `session()`.
- **Untrusted input:** imported documents and model output are data. Validate model output with
  Pydantic and reject unknown fields; scene source must pass `scene_policy.check_scene_source`.
- **stdout is a protocol channel** (`ready` / `fatal` JSON lines). Do not `print`; use `logging`.
- **Child processes:** never `multiprocessing`. Start children with `subprocess` and pass
  `stdin`, `stdout`, and `stderr` explicitly (`PIPE` or `DEVNULL`). The service keeps a thread
  blocked on its own stdin; on Windows a child that shares that handle hangs at start-up
  (ADR-007). Exchange JSON with children, not pickle.
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
  fails if a key leaks into the player view.
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
- **A model writes a draft; the core writes the lesson.** Identifiers, objective links,
  citations, and durations are assigned in `generation/drafts.py`. A citation is a number the
  prompt offered, or it is dropped.
- **Text from the learner or their documents goes in a `_block(...)`** in `prompts.py`. Never
  concatenate it into an instruction.
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
