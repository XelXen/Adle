# ADR-059: A check runs what a change can reach

- **Status:** Accepted
- **Date:** 2026-11-24
- **Changes:** the working method of `AGENTS.md` and `TESTING.md`: a check on this computer
  runs what a change can reach, not every test.
- **Keeps:** ADR-043: GitHub runs every check for every push, and a version is published
  only from a commit for which every check has passed.

## Context

A whole check took 37 minutes on this computer (2026-11-24): 34 for the 204 journeys, 3.3
for the core's 1,751 tests, 44 seconds for the rest. Most changes touch one part of Adle, and
every check ran every test anyway. The owner: "if anything changes- do tests related to
that ... some things are not even affected by it- why even retest that?"

Half the journeys ran the same example twice, once in each theme, though a theme changes
only a picture's colors and the journeys look at where its words lie and whether it
finishes. The figure and scene examples ran at a learner's pace, though their journey is
about finishing, not pace.

## Decisions

- **What changed is everything not on origin/main yet**: commits not pushed, files changed,
  files new.
- **The static checks run whole**, as before: contracts, names, scene guide, secrets,
  licences, format, lint, types. They take seconds and are about the repository as a whole.
- **The unit tests of the TypeScript** are those related to the files changed, by what
  imports what (`vitest --changed`).
- **The core's tests** are those whose code changed since they last ran, read from the code
  each test ran (`pytest-testmon`, a development dependency under the MIT licence; its
  record, `.testmondata`, stays out of git), and the integration tests whenever the core's
  code changed: they run the core as a program of its own, which the record cannot see.
  All of them run when what changed is something the record cannot follow: the data the
  core carries, its dependencies, the tests' shared fixtures and helpers.
- **The journeys** are those `scripts/affected.mjs` maps the changed files to. A path it
  does not know runs every journey; words, decisions, tooling and unit tests run none.
- **Each slide, figure and scene example runs once**, the two themes taking turns along
  each set (`e2e/support/themes.ts`). `ADLE_E2E_EVERY_THEME=1` runs every example in both.
- **Figure and scene examples run as rehearsals**, many times faster, which say what a
  learner's run says (tested). The slides keep a learner's pace: theirs is the journey
  about pace.
- **`--all` runs everything**, and on GitHub (`CI`) everything always runs.

## Alternatives

- **Fewer journeys.** Each covers something no other does; choosing among them for each
  change keeps all of them and runs few.
- **Choosing the core's tests by what imports what.** The fixtures most tests share build
  the whole service, so almost any change would choose the 24 files that use them.
- **Leaving the themes doubled.** A color that breaks a picture in one theme would break it
  in the examples that run in that theme; every set runs both.

## Consequences

- A change to one part of Adle is checked in minutes rather than 37.
- A rule missing from `affected.mjs` makes a check slower, never weaker. A rule that is
  wrong can leave a journey out here; GitHub runs it on the push.
- The first check on a computer runs every core test, to make the record.
