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
  learner_model/  PURE rules: knowledge tracing, mastery states, review schedule, preferences
  domain/         pure models shared across areas (empty so far)
  infrastructure/ database, ORM models, migrate (with backup), asset store, ids
  migrations/     Alembic revisions (shipped inside the package)
  ingestion/      type detection, parsers, chunking, the parser worker process
  generation/     provider credentials, scene policy (model client, quota: M5)
  orchestration/ evaluation/ audio/   (M5–M6)
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
- **No score leaves the core.** `api/schemas.py` must not expose the tracing estimate or anything
  that reads like a percentage. The interface gets a state, a label, and what is missing.
- **Text shown to the learner about their knowledge** is written in `learner_model/tracing.py`
  and `mastery.py`. Keep it free of blame and of numbers that imply precision.
- Tests that need "a later version of the schema" use `use_migrations_with_extra_revision` in
  `test_database.py`, which chains a test-only revision after the real newest one.
- No provider call in any test. Use the fake server fixture (added with the client in M5).

## Style

Ruff (rules in `pyproject.toml`) and mypy strict must be clean. Type-annotate everything. Prefer
frozen dataclasses for domain values and small functions over classes with hidden state.
Docstrings explain decisions and invariants, not what the next line does.
