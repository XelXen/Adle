# Performance

What a learner waits for, how long it takes, and how that was measured. Every number here
came from `node scripts/measure.mjs` or `node scripts/smoke-packaged.mjs` on the machine
below. They describe that machine on that day; run the scripts again rather than quote them.

- **Measured:** 2026-11-19 and 2026-11-20
- **Machine:** Intel Core i9-14900HX, 32 GB memory, NVMe disk, Windows 11 Pro (10.0.26300)
- **Build:** Electron 45.4.1, Python 3.12.11

A fast laptop. Expect everything to take longer on an ordinary one; the proportions should
hold.

## What the learner waits for

Five fresh starts each, on an empty profile. Median, with the slowest in brackets.

| | Packaged build | Built files (development) |
|---|---|---|
| Window with its first screen | 0.52 s (0.63) | 0.48 s (0.61) |
| Local service ready, from launch | 1.34 s (1.51) | 2.84 s (2.92) |
| Sample course added and its first suggestion shown | 0.37 s (0.39) | 0.42 s (0.44) |
| Lesson opened | 0.10 s (0.15) | 0.33 s (0.33) |
| Live scene: from asking for it to its first frame | 0.89 s (1.49) | 0.93 s (0.95) |

The window never waits for the local service: the first screen is up in about half a second
and says "Local service starting…" until the service answers.

The live scene figure is the whole path the plan asks to be measured separately: a new
sandboxed frame on a fresh origin and process, the Wanim runtime loading, the scene being
compiled from Python-like source, and the first frame drawn. They were not timed apart
here; under a second in total, there was nothing to chase.

## The first start after installing

`scripts/smoke-packaged.mjs` starts a freshly built release from outside. On its first ever
start the local service took **3.6 s** for one build and **6.8 s** for another to come up; on
every start after that, about one.
The difference is the operating system examining files it has not seen before: the build
has about 3,900 of them, nearly all in the bundled Python. Nothing in Adle can shorten it,
and the interface says what it is waiting for.

## Why the packaged service starts faster than the development one

0.9 s against 2.3 s for the service alone (`spawn` to its `ready` line, four runs each).
The packaged Python has its bytecode compiled at build time and is started with `-I`, so it
neither compiles on the way nor looks at the environment or the user's own packages. The
development run does both.

## Size

| | |
|---|---|
| Packaged folder | 459 MB (the sum of its files; about 10 MB more on disk) |
| of which Electron and Chromium | about 357 MB |
| of which the core: Python, its packages, the service | 93 MB |
| of which the app itself (`app.asar`) | 9 MB |

The largest parts of the core are SQLAlchemy (20 MB with bytecode), lxml (10 MB, for Word
files), and Pydantic's compiled core (6 MB). Tests, Tk, IDLE, pip, and headers are left out
of the Python that ships.

## What was not measured

- **Generating a lesson with the model.** The provider has not answered a request yet (see
  PROJECT_STATE.md), and its time would be the provider's, not Adle's. Each request is one
  at a time, at most four a minute, by design.
- **Large courses.** The sample course has eight concepts and eight lessons. Opening a course
  reads every answer given in it; the session summary bounds its own look back at 600.
  Nothing here says how a course with thousands of answers behaves.
- **Large documents.** Importing is bounded by size, page, and time limits
  (`ingestion/types.py`) and runs outside the service, so it cannot hold the interface up;
  how long a 300-page PDF takes was not timed.
- **Memory.** Not profiled. Each scene runs in its own process, which ends with the frame.
- **Other machines and other operating systems.** One laptop, one system.

## The end-to-end suite as a timing check

The whole suite (83 journeys) takes about eleven minutes against either build, with one
worker. No journey waits on a fixed delay for the app; a regression in any of the paths above
shows up there as a slower run long before it becomes a failure.
