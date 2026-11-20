# ADR-015: A unit of work that may write takes the write lock first

- **Status:** Accepted
- **Date:** 2026-11-19
- **Amends:** ADR-007 (persistence), which chose SQLite in WAL mode with one kind of session.

## Context

An end-to-end run failed once and passed on retry. The learner had asked for a new lesson and
was taken to the course; the course screen said "The course could not be opened".

The cause was not in the test. Opening a course reads the course and then records that it was
opened. Every transaction began with a plain `BEGIN`, which in SQLite is a read transaction
until its first write. If another connection commits between that first read and that first
write, the write fails at once with `database is locked`: the transaction's snapshot is stale,
and SQLite does not wait, whatever the busy timeout. The job that had just been started was
writing its first rows at that moment.

Any request that reads before it writes could fail this way whenever a job or another request
was writing. Nearly every mutation reads first. It was rare only because the window is a few
milliseconds wide.

## Decisions

- **`Database.session()` is a unit of work that may write.** Its transaction begins with
  `BEGIN IMMEDIATE`: it takes the write lock up front and, if another writer holds it, waits
  (up to fifteen seconds) instead of failing later. Writers therefore run one at a time, which
  is what SQLite does anyway; the difference is that they now queue instead of colliding.
- **`Database.read()` is a unit of work that only reads.** It runs on a second engine whose
  connections have `PRAGMA query_only = ON`, so a write inside one is refused by SQLite itself
  rather than by convention. It takes no lock and sees a consistent snapshot: it never waits
  for a writer, and no writer waits for it. Everything the interface polls (jobs, usage) and
  every screen's first load uses it.
- **A writing unit of work cannot be opened inside another on the same thread.** It could only
  wait for itself until the timeout. `Database.session()` refuses with a clear error at once.
  A read inside a write is allowed, and sees what was last committed.
- A course is opened with a read, unless the visit is being recorded.

## Consequences

- The failure cannot occur for any unit of work that goes through `Database.session()`. A test
  reproduces the exact interleaving and fails with `database is locked` if the transaction
  mode is changed back.
- A long write transaction now makes other writers wait rather than fail. Writes are kept
  short: nothing slow (parsing a document, a model request) happens inside one. Keep it so.
- Readers must be declared. A method that only reads but uses `session()` is correct and merely
  takes a lock it does not need; a method that writes but uses `read()` fails loudly in its
  first test.
- The rule "a flaky end-to-end test is investigated, not ignored" paid for itself here.
