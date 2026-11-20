# ADR-016: A copy of the data is one file; restoring happens while the core starts; deleting everything is the main process's job

- **Status:** Accepted
- **Date:** 2026-11-19
- **Builds on:** ADR-002 (the core process and the bridge), ADR-005 (internal operations),
  ADR-007 (persistence), ADR-015 (units of work).

## Context

The plan asks for "course export, app data backup, and permanent deletion controls" and for a
journey that exports, deletes, and restores a course. `restore_database` had been built and
tested since M2, but nothing in the interface reached it, and nothing could write a copy for
the learner or remove everything.

Three constraints shaped the design:

- Page script must never name a file (SECURITY.md). A path may enter the app only from a
  window of the operating system that the main process opened.
- The core cannot replace its database while it is running: every service holds connections,
  and on Windows an open file can be neither replaced nor deleted.
- Until now the core wrote nowhere outside its own data directory.

## Decisions

- **A copy is the database, as one self-contained file** ending in `.adle`. It is written with
  SQLite's online backup, so the service keeps running and the copy is one consistent moment,
  and it is then switched to SQLite's single-file mode. A copy left in the live database's
  write-ahead mode gains a `-shm` and a `-wal` file beside it the first time anything opens it,
  even read-only, and keeps them; and it cannot be read from a disk that cannot be written to.
  `backup_database` now does this for every copy it makes, the automatic ones included.
- **What a copy does not hold.** The provider key was never in the database. The files that
  were imported are not in it either: nothing reads a stored original after import, so a
  restored copy is complete without them. That becomes a rule: **nothing may depend on a
  stored original being present.**
- **The three questions are asked by the operating system, from the main process:** where to
  save (a save dialog), which file to restore (an open dialog), and whether to delete (a
  message box whose default answer is Cancel). The bridge functions (`window.adle.data.*`)
  take no arguments, and the page is told only how it went and, for a saved copy, the name of
  the file. One of these runs at a time.
- **Saving is an internal core operation**, `data.save_copy`, given the path the dialog
  returned. It is the one place the core writes outside its data directory. The path is
  checked on both sides (absolute, ends in `.adle`, not inside the data directory, in a
  folder that exists) and the copy is written under another name and renamed when complete,
  so a failure never leaves a damaged file under the chosen name or destroys an older copy.
- **Restoring happens while the core starts, not through a route.** The main process stops
  the core and starts it with `restore_from` in the handshake line (beside the token, on
  stdin, never in the arguments). Before anything opens the database, the core:
  1. checks the file: readable, intact, at a schema revision this build knows, and holding
     Adle's own tables (another program's database can carry a version table too);
  2. makes a working copy and brings *that* to the current schema;
  3. keeps the current data as a safety copy in `data/backups/`;
  4. puts the working copy in place with one atomic rename.

  If any step fails the current data has not been touched. The outcome travels back in the
  `ready` line (`"restore": {"ok": ...}`); a refusal is not fatal, and the service runs on
  the data as it was. A start that restores is allowed three minutes instead of thirty seconds.
- **A restore can be undone with a restore.** Safety copies are copies like any other, the
  open dialog accepts them, and "Show safety copies" opens their folder in the file manager
  (a fixed folder; the page chooses nothing). The newest five copies of replaced data are
  kept; without a limit every restore would leave another whole database behind.
- **Deleting everything is done by the main process.** After the confirmation it stops the
  core, holds it stopped so that nothing else can start it (`CoreProcess.whileStopped`),
  removes the data directory, and starts the core again on an empty one. The provider key and
  the appearance settings are not learner data and stay; the new core is handed the key.
- **After a restore, stored originals that nothing refers to are removed**
  (`SourceService.forget_unreferenced_files`). Otherwise a file the learner can no longer see
  in any course would stay on disk with no way to remove it.
- **Nothing in a database file's schema is trusted** (`PRAGMA trusted_schema = OFF`,
  `cell_size_check = ON`, on every connection). The data may now come from a file the learner
  was given. Triggers that keep the search index in step still work: FTS5 is marked harmless
  by SQLite, which was checked before this was switched on.

## Not built

- **Exporting one course to a file for someone else.** A copy of everything covers backing up
  and moving to another computer, which is what the plan's journey exercises. A single course
  as a shareable file is a different feature: it needs a format of its own and an import that
  re-validates every lesson and re-keys every identifier. It can be added without changing
  anything decided here.
- **Encrypting a copy.** A copy is an ordinary file; the interface says so. Protecting it is
  left to where the learner keeps it.
- **Removing individual safety copies from the interface.** They can be deleted in the folder
  that "Show safety copies" opens, and "Delete everything" removes them all.

## Consequences

- A copy made by an older version of Adle restores (it is upgraded in the working copy first);
  one made by a newer version is refused with a sentence that says so.
- A restored copy brings its own count of today's requests. Adle's own estimate may then be
  low for the rest of the day; the provider's limit is the real one and is unaffected.
- Restoring a file from someone else gives their content the standing of the learner's own:
  it is shown as text, its scenes are checked again on every read and run only in the player
  (ADR-004, ADR-010). It gains nothing more.
- The handshake line is now a small protocol of its own: a token, and at most one instruction
  to carry out before the data is opened. Add to it only what cannot be done once the service
  is running.
- Tests: `test_data_copy.py` and `test_database.py` (the guarantees, each confirmed by removing
  it and watching a test fail), `test_process_lifecycle.py` (restore through the real process),
  `core.test.ts` (the instruction and its report; holding the core stopped), `data.test.ts`
  and `data-copy.test.ts` (the handlers and their path rules), `e2e/data.spec.ts` (save,
  delete a course, restore, undo; refusals; delete everything) and `e2e/security.spec.ts`
  (the page cannot steer any of it).
