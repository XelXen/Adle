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

### Every model, every kind of request (2026-11-21)

Each model NVIDIA lists for chat was asked once for each kind of request, through Adle's
own prompts (`scripts/dev/benchmark_models.py`, by hand). "Usable" means Adle could take
what came back as it was; a scene file passed the static rules (whether it runs is tried
in the player since ADR-038). Times from the request to the end of the answer:

| Model | A question | Suggested concepts | A lesson's words | A scene file | An interactive scene |
|---|---|---|---|---|---|
| Nemotron 3 Ultra (550B) | 8 s | 30 s, 8 concepts | 113 s, 10 parts, 2 pictures | 20 s | 10 s |
| Nemotron 3.5 Super (120B) | 7 s | 39 s, 6 concepts | not usable (fields left out) | 93 s | empty |
| Kimi K3.1 Pro | 66 s | 123 s | 254 s, 8 parts, 1 picture | 134 s | 151 s |
| Laguna XS 2.1 | 2 s (one wrong statement) | 14 s, 10 concepts | not usable (titles left out) | 9 s | 12 s |
| Mistral Large 4 | 144 s | not asked | not asked | not asked | not asked |
| GLM 5.3 Flash | 151 s | not asked | not asked | not asked | not asked |

Others were not usable for a question at all: Nemotron 3.5 Lightning spent its whole
allowance thinking; Nemotron 3.5 Bolt answered in a sentence; Step 5 Preview took 33 s for
a question and eight minutes for concepts; MiniMax M3.1 Flash (81 s), Muse Glimmer (205 s)
and Gemma 4 (no answer) were slower still. Each kind of request now goes first to the model
that did it well and soonest (ADR-039), so with NVIDIA a lesson's words take about two
minutes, a question about ten seconds.

A whole lesson is the text and one or two scenes: nine to twelve minutes when every answer
was written by Kimi, about five with each request at its own model. Adle cannot make a model quicker. **What the learner waits for
is the text only** (ADR-031): the lesson can be started when that is written, about five to
six minutes in, and each picture appears in it when it is drawn. Besides: the work is a
job that leaves the app usable, the job says what the model is doing ("thinking it
through", "writing"), and it can be stopped. Finding out that a model is not there takes a
quarter of a second; finding out that it is silent takes three minutes, once, after which
that model is left alone for ten.

### A whole way through a chapter of notes (2026-11-22)

The owner's own chapter of lecture notes (a PDF of 26 pages, ten sections), imported, a
course planned from it, a lesson written on its first concept, and a question asked in
that lesson, each step timed, through NVIDIA with each request at the model measured best
for it (`scripts/dev/real_provider_check.py document:<file>`, by hand):

| Step | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Import (read, cut into sections, indexed) | 1 s | 1 s | 1 s |
| A course plan | 32 s, 9 concepts, every section | 18 s, 8 concepts, every section but the summary of formulas | 52 s, the same 8 |
| A lesson, until it can be started | none: refused twice, 56 s + 149 s | 259 s: refused once (116 s), then 143 s | 232 s, its first answer |
| Its pictures, after that | | 5 figures, none lost, no wait | 5 figures, then left out for want of a description |
| A question in the lesson | | 10 s | 16 s |

Each run found something the core now mends (ADR-047): run 1's refusals were notation in
the narration, then a practice question without its explanation; run 2's was three
checkpoints without a title; run 3 was usable at once, but its figures had no descriptions
and its board's formulas were written with every backslash twice. With what was changed,
every one of those answers is a usable lesson as it came, with all its figures (twenty-seven
of twenty-seven, on all five answers), after one request: about two to four minutes
of the model's time, which varies with how long it thinks. Before figures (ADR-045) a picture
was a request of its own, two to two and a half minutes each, one or two to a lesson; a
figure is drawn in milliseconds and tried in the player in a second or two.

### Thinking less, and a lesson begun at its first part (2026-11-22)

Most of a lesson's wait was the model thinking before it wrote (18,000 to 35,000
characters of it, at the default `reasoning_effort` of "high"). The same lesson asked at
"medium" (ADR-048), and then the whole way again with the lesson begun at its first part:

| Step | Run 4 (medium) | Two more lessons (medium) | Run 7 (medium, begun at its first part) |
|---|---|---|---|
| A course plan | 62 s (left at the default since) | | 37 s, 8 concepts, every section but the summary of formulas |
| A lesson, until it can be started | 74 s, its first answer | 71 s and 53 s, each its first answer | **77 s, at its first part** |
| Every part of it written | the same | the same | 122 s, 10 parts |
| The model's thinking first | 1,500 to 3,300 characters | | 9,600 characters |
| A question in the lesson | 20 s | | 19 s |

At "medium" every lesson was usable at its first answer, so the lesson is no worse for the
minutes saved. Run 7 thought three times longer than the others and could still be begun
at 77 seconds; the rest of its parts were written while it would have been studied. Its
figures showed what was still lost to the format: one of its five was drawn. The four
others, and three in the two lessons before it, were shapes a model means that the format
did not take: a step of an equation with words in it, seven steps where six were taken,
two rises given as a list, a curve flat over most of its range taken for one that jumps, a
choice written `a ? b : c`, and a label with words beside its formula. Each is now taken as
the model meant it (ADR-045), and the figures of every lesson the model wrote that day are
drawn: fifty of fifty, in nine answers. Eight requests for these runs.

Run 8 went the whole way again with every fix in: the plan in 81 s, the lesson begun at
205 s and whole at 245 s, its pictures all there at 472 s (one was an interaction, a scene
Kimi K3.1 Pro wrote in 228 s), a question in 10 s. The model thought for 30,000 characters
at "medium" this time, as long as at "high": how long it thinks varies from one request
to the next by ten times, and nothing Adle sends changes that.

So the one setting below "medium" that the model's reference lists, "none", was measured
too, by hand, on a copy of the code, and not kept:

| | The chapter's first concept | Backpropagation | Derivatives and the chain rule |
|---|---|---|---|
| Thinking | none | none | none |
| A lesson, until it can be started | **5.5 s** | | |
| Every part of it written | 44 s | 80 s | 59 s, refused; written again in 51 s |
| Its figures | 5 of 5 (one area under a cumulative curve) | 4 of 6 | 4 of 5 |
| What was wrong in it | an area shaded under F(x) | nothing found: every number of its worked example checks out | its first answer left a line of the board open; the second has a question whose answer key, 880, is not what its own explanation works out (292,820), and the explanation has the model's second thoughts in it ("Wait… Let me recheck") |

A learner who answered that question right would be told they were wrong. Without
thinking first, the model does its working out in the answer itself, and an answer key
that disagrees with its explanation is not something Adle can mend. A lesson is asked at
"medium" (ADR-048). The rest of what these answers showed is mended for every setting
(ADR-045, ADR-047): the area under a curve the figure calls cumulative is drawn as how
much it rises (three answers at "high" had done the same), tanh and erf are read, a table
may have eight rows and an equation ten steps, and a board line left open is left off.
Across every answer the model wrote that day, fourteen, 74 figures of 75 are drawn; the
one left is a flow of eight steps, which is told in words. Nine more requests.

### A lesson as a slideshow, and a model that does not think first (2026-11-22)

Asked for a lesson in which every part that teaches has a slide (ADR-049), through NVIDIA,
by hand, one request a lesson to Nemotron 3 Ultra:

| Lesson | Prompt, thinking | Thinking | Can be started | Every part written | Parts kept | Slides |
|---|---|---|---|---|---|---|
| Sample spaces and events | first, "medium" | 53,462 characters | 313 s | 352 s | 7 of 9 | 3 |
| The derivative as a slope | first, "medium" | 58,960 | 297 s | 348 s | 7 of 9 | 4 |
| Active and passive voice | first, "medium" | 36,691 | 263 s | 328 s | 6 of 8 | 3 |
| Linked lists | first, "medium" | 19,036 | 118 s | 177 s | 8 of 9 | 5 |
| Sample spaces and events | revised, "medium" | 35,989 | 214 s | 263 s | 9 of 9 | 6 |
| Sample spaces and events | revised, "none" | none | **13.5 s** | 63 s | 10 of 10 | 6 |
| The derivative as a slope | revised, "none" | none | **11.5 s** | 97 s | 8 of 8 | 5 |
| Active and passive voice | revised, "none" | none | **12.0 s** | 66 s | 9 of 9 | 5 |

The parts the first prompt lost were refused by the lesson's format, not by their slides:
a summary or a worked example with no line on the board, which a slide now stands for, and
a worked example with no problem, which is now an explanation. What those answers scripted
is drawn as the model meant it since (part names copied from the prompt's examples, items
written as parts, a cell counted from 0, a sentence left empty for a step to fill, set
symbols in plain words): every slide of the eight answers draws with nothing left out but
one label on a word a later step adds.

Every question of the three answers written without thinking was checked by hand: all right
but one practice question, which offered 12/52 and 3/13 as different answers with one marked
right. That slip, and the one ADR-048 saw (a key its own explanation did not reach), are
caught in drafts now; with them caught, a lesson is asked for without thinking (ADR-049), and
can be begun about twelve seconds after it is asked for, every part of it written within
about a minute and a half. Eight requests for these runs; with those earlier the same day,
48 of the 80 a day allowed by hand.

## A natural voice (2026-11-21)

On the development machine (an RTX 4080 Laptop GPU with 12 GB, Windows 11), with the voices
set up by Adle's own installer into a folder of their own (ADR-042):

| | Natural (Kokoro) | Rich (Qwen3-TTS 0.6B) | Expressive (Qwen3-TTS 1.7B) |
|---|---|---|---|
| Downloaded to set it up | 0.33 GB of models, 0.23 GB of programs | 2.88 GB of models (the aligner included), 2.91 GB of programs | 8.76 GB of models, 2.91 GB of programs |
| Set up | 378 s: programs about 4 minutes, models about 2 | Programs: 4 minutes to download, 4 to install (its models were here) | Not timed through the installer |
| On the disk, set up | 1.4 GB | about 8 GB with its programs | — |
| Speaking | 4.6 times faster than it is said, on the processor; ready 2.3 s after it starts | 11.2 s of speech in 8.0 s on the card | A voice designed and two lines said in 36 s, loading included |
| Finding each word | its own durations | 0.18 to 0.39 s a line (wav2vec 2.0) | the same |

A lesson is recorded line by line in the background and never waited for: a line not
recorded yet is read by the computer's voice.

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
- **A natural voice anywhere else.** Linux and macOS set a voice up only on GitHub's
  machines' terms (the environment is made there by every package check; nothing is
  downloaded). A card with less memory, or a slower connection, was not tried.
- **Other machines and other operating systems.** One laptop, one system, for every timing
  in this document except the first starts on GitHub's machines above.

## The end-to-end suite as a timing check

The whole suite (106 journeys) takes fourteen to seventeen minutes against the development build, with one
worker. No journey waits on a fixed delay for the app; a regression in any of the paths above
shows up there as a slower run long before it becomes a failure.
