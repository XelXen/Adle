# ADR-007: Persistence, migrations, and document ingestion

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

M2 gives Adle a database, lets a learner import course materials, and makes that text searchable
with provenance. The plan requires SQLite with migrations from day one, FTS5, local parsing with
type/size limits and timeouts, and that a learner's data is never silently replaced.

## Decisions

### Database

- **SQLite through SQLAlchemy 2 (synchronous).** Request handlers run in FastAPI's thread pool;
  one background worker thread runs jobs. WAL mode lets the UI read during an import.
- **Transactions are explicit.** The driver's implicit transaction handling is switched off and
  SQLAlchemy emits `BEGIN` itself. This makes schema changes transactional, so a failed migration
  rolls back completely instead of leaving a half-changed database (tested).
- **Timestamps are timezone-aware UTC** (`UtcDateTime`); naive values are refused.
- **Identifiers** are random, prefixed strings (`crs_…`, `src_…`, `job_…`).

### Migrations

- Alembic revisions live **inside the package** (`adle_core/migrations/`), not in
  `services/core/migrations/` as the plan sketched, so they ship with the code in a packaged build
  without extra data-file plumbing.
- `infrastructure/migrate.py` runs at startup:
  1. Already current → nothing happens.
  2. Tables present but no Alembic version → **refused** (`UnrecognisedDatabaseError`).
  3. Revision unknown to this build → **refused** (`DatabaseTooNewError`): never downgrade.
  4. Otherwise a consistent copy is written to `backups/` with SQLite's online backup API
     (it includes WAL contents), then the upgrade runs in one transaction. On failure the
     database is unchanged and the error carries the backup path.
  5. The five most recent automatic backups are kept.
- A startup migration failure is reported to the desktop shell as a `fatal` event with a
  learner-readable message; the app shows it instead of starting with broken data.
- A test compares the migrated schema with the ORM models, so the two cannot drift.

### Search

- **FTS5 external-content index** over `source_chunks.text`, kept in step by triggers (verified to
  fire for cascading deletes, and checked with FTS5's `integrity-check`). It can be rebuilt from
  the table at any time.
- User input is never FTS5 syntax: every term is extracted with `\w+`, quoted, and combined by
  the code. All terms must match; if nothing does, any term may. The last term is a prefix.
- Highlights use private-use characters as markers, which cannot occur in stored text, and are
  returned as plain segments. No markup crosses the API.
- **Vector search is not built yet.** FTS5 alone meets M2. `sqlite-vec` and a local embedding
  model will go behind a retrieval adapter when packaging can be validated (plan §5.4).

### Ingestion

- **Type is decided by content as well as extension** (`ingestion/detect.py`): PDF header, DOCX
  zip structure, or text without binary bytes. Common unsupported formats get a specific hint.
- **Parsers:** `pypdf` (per page), `python-docx` (heading styles, tables), `markdown-it-py`
  (heading tree), and a text decoder (UTF-8, UTF-16 with BOM, else Windows-1252 with a warning).
  No OCR, and no upload to do OCR. Scanned PDFs are rejected with an explanation; partly scanned
  ones import with a warning and a lower confidence on the affected source.
- **PDF text is reflowed.** A PDF stores lines, so sentences are rejoined when a line fills at
  least 80% of the page's widest line, unless it ends a sentence and a capital follows.
- **Chunks follow structure:** never across a page or section, split at paragraphs, then
  sentences, with exact character offsets. Target 1,200 characters, hard limit 1,800.
- **Limits:** 50 MB per file (10 MB for text), 2,000 pages, 5 M characters, 120 s per parse,
  50 files per import.
- **Originals are copied** into the app's `sources/` directory under the source id. The
  learner's path is used once and never stored; the display name is never used as a path.
- **Duplicates** are detected by SHA-256 per course.

### Parsing runs in a child process started with `subprocess`

Parsers face hostile input, so each parse runs in a killable child process.

`multiprocessing` was the first implementation and **hung every import in the real app on
Windows**. The service keeps a thread blocked reading its own stdin (ADR-002: that is how it
notices the desktop app closing). A `multiprocessing` child shares that stdin handle, and
interpreter start-up in the child then blocks on it. Unit tests could not see this because they
parsed in-process.

The worker is therefore `python -m adle_core.ingestion.worker` (or `adle-core --parse-worker` when
frozen), started with `subprocess` and **its own stdin and stdout pipes**. Request and reply are
JSON. That also removes pickle from the boundary: a parser subverted by a hostile file cannot run
code in the service by crafting its reply, and the reply is type-checked and bounded before use.

**Rule:** the core never uses `multiprocessing`, and every child process gets explicit
`stdin`/`stdout`/`stderr`. A regression test starts the service exactly as Electron does and
imports files through it.

### Paths never come from the renderer

`sources.import_paths` is an internal operation. Paths reach it only from the main process:
from the OS file dialog, or from files the learner dropped, which the preload script resolves
with `webUtils.getPathForFile`. A `File` built by page script has no path and is rejected.

### Jobs

Imports (and later generation) are jobs: a database row plus a function on a single worker
thread. Progress and outcome are persisted and polled; cancellation is cooperative and keeps
partial results; jobs left active by a previous run are marked `interrupted` on start.

## Alternatives considered

- **PyMuPDF** for PDFs: better extraction, but AGPL. Rejected on licence.
- **Async SQLAlchemy:** no benefit for a single-user local database, and more moving parts.
- **Store failed imports as rows:** rejected; a rejected file leaves nothing behind. The outcome
  is reported in the job result and shown in the import summary.
- **Run migrations from the desktop shell:** the core owns its data; one owner is simpler.

## Consequences

- Each imported file costs one short-lived process (about 100–300 ms of overhead).
- Extraction quality for complex PDFs (multi-column, tables, equations) is limited by `pypdf`.
  The source's confidence and warnings are where that is surfaced; improving it is future work.
- Restoring one of the automatic backups is manual for now; export/restore in the app is M7.
