# Performance

What a learner waits for, how long it takes, and how that was measured. Every number here
came from `node scripts/measure.mjs` or `node scripts/smoke-packaged.mjs` on the machine
below. They describe that machine on that day; run the scripts again rather than quote them.

- **Measured:** 2026-11-19 to 2026-11-21 (the date of each figure is beside it where they differ)
- **Machine:** Intel Core i9-14900HX, 32 GB memory, NVMe disk, Windows 11 Pro (10.0.26300)
- **Build:** Electron 45.4.1, Python 3.12.11

A fast laptop. Expect everything to take longer on an ordinary one; the proportions should
hold.

## What the learner waits for

Five fresh starts each, on an empty profile. Median, with the slowest in brackets.

| | Packaged build (2026-11-21) | Built files (development, 2026-11-21) |
|---|---|---|
| Window with its first screen | 0.41 s (0.49) | 0.39 s (0.43) |
| Background service ready, from launch | 1.24 s (1.50) | 2.62 s (2.65) |
| Sample course added and its first suggestion shown | 0.31 s (0.36) | 0.27 s (0.35) |
| Lesson opened | 0.31 s (0.42) | 0.32 s (0.44) |
| Live scene: from asking for it to its first frame | 0.84 s (0.86) | 0.83 s (0.84) |

The window never waits for the background service: the first screen is up in under half a
second, and the rail says "Starting…" until the service answers. "Ready" now includes
handing the service the learner's choice of provider and their keys before anyone is told
(ADR-029); measured again after that change, neither build is slower for it. The packaged
column is from the build made of the tree of ADR-032; the development column was measured
before ADR-031 and ADR-032, which change nothing on these paths except the size a scene is
drawn at.

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
| Packaged folder | 460 MB (the sum of its files; about 10 MB more on disk) |
| of which Electron and Chromium | about 357 MB |
| of which the core: Python, its packages, the service | 93 MB |
| of which the app itself (`app.asar`) | 9 MB |

The largest parts of the core are SQLAlchemy (20 MB with bytecode), lxml (10 MB, for Word
files), and Pydantic's compiled core (6 MB). Tests, Tk, IDLE, pip, and headers are left out
of the Python that ships.

Those figures are this computer's, Windows. What GitHub's machines built for
0.1.0-alpha.1, and what a person downloads (commit `a812d34`, 2026-11-21):

| System | The folder | of which the core | Downloaded as |
|---|---|---|---|
| Windows (x64) | 463 MB | 96 MB | `setup.exe`, 133 MB |
| macOS (Apple) | 386 MB | 119 MB | `.dmg`, 151 MB |
| macOS (Intel) | 384 MB | 110 MB | `.dmg`, 156 MB |
| Linux (x64) | 431 MB | 148 MB | `.deb`, 126 MB; `.tar.gz`, 171 MB |

Installed on a machine that did not build it and started on an empty profile, the service was up after 1.7 s on Windows, 3.0 s and 2.1 s on macOS (Apple, Intel) and 3.0 s on Linux. The core is larger on macOS and Linux than on Windows because the Python there carries its library twice, once inside the program and once beside it (17 to 31 MB each).

## Waiting for a real model

Everything above is Adle's own time. Once a learner asks for a lesson, almost all of the
wait is the provider's. Measured on 2026-11-20 through NVIDIA NIM, by hand (no test calls a
real provider), one request at a time:

| What is written | By | Time | Of which before the first word of the answer |
|---|---|---|---|
| A lesson's text (about 12,000 characters) | Kimi K3.1 Pro | 4.6 to 5.9 min | 1.5 to 2.5 min (the model thinks first) |
| The same | Mistral Large 4 | 7.6 min | 4 min |
| One scene file (about 4,500 characters) | Kimi K3.1 Pro | 2.6 to 4.1 min | about 1.5 min |
| A curriculum of ten to twelve concepts | Kimi K3.1 Pro | 2.1 min | 1.2 min |
| The same | Mistral Large 4 | 5 min | not timed |

A whole lesson is the text and one or two scenes: nine to twelve minutes when every answer
is usable as first written. Adle cannot make a model quicker. **What the learner waits for
is the text only** (ADR-031): the lesson can be started when that is written, about five to
six minutes in, and each picture appears in it when it is drawn. Besides: the work is a
job that leaves the app usable, the job says what the model is doing ("thinking it
through", "writing"), and it can be stopped. Finding out that a model is not there takes a
quarter of a second; finding out that it is silent takes three minutes, once, after which
that model is left alone for ten.

## What was not measured

- **Generating with AIHubMix's model.** That provider has not answered a request yet (see
  PROJECT_STATE.md). The times above are NVIDIA's models on one afternoon; they are a shared
  service and will vary. Each request is one at a time, at most four a minute, by design.
- **Large courses.** The sample course has eight concepts and eight lessons. Opening a course
  reads every answer given in it; the session summary bounds its own look back at 600.
  Nothing here says how a course with thousands of answers behaves.
- **Large documents.** Importing is bounded by size, page, and time limits
  (`ingestion/types.py`) and runs outside the service, so it cannot hold the interface up;
  how long a 300-page PDF takes was not timed.
- **Memory.** Not profiled. Each scene runs in its own process, which ends with the frame.
- **Other machines and other operating systems.** One laptop, one system, for every timing
  in this document except the first starts on GitHub's machines above.

## The end-to-end suite as a timing check

The whole suite (106 journeys) takes fourteen to seventeen minutes against the development build, with one
worker. No journey waits on a fixed delay for the app; a regression in any of the paths above
shows up there as a slower run long before it becomes a failure.
