# ADR-010: Lesson IR, the lesson player, and where answers are judged

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

M4 turns a concept into something a learner can sit through: narration, pictures that move,
things to try, questions, and a record of what the answers showed. The same lesson format has to
serve a hand-written sample course now and model-generated lessons in M5, and it is the widest
door through which untrusted content (model output) will enter the app.

## Decisions

### One format, defined once, in the core

- The Lesson IR is a set of strict, frozen Pydantic models in `adle_core/lessons/ir.py`
  (`schema_version` "1.0"). Unknown fields are refused. Every text field is one of two kinds:
  **spoken** (plain words for the narrator) or **display** (plain words with inline `$…$`
  mathematics). Links, markup, file paths, and control characters are refused in both.
- A lesson is a list of typed segments: explanation, visualization, interaction, checkpoint,
  worked example, reflection, summary. Narration is a list of **beats**; a beat may put a line on
  the board (`show`) and may cue its segment's scene to move on (`advance_scene`).
- A segment that uses a scene must carry a `fallback_text` that says the same thing in words.
- Its JSON Schema is generated with the API contract
  (`packages/contracts/schemas/lesson-ir.schema.json`, checked for drift by `npm run check`).
  There is no separate `packages/lesson-ir`: a second definition would only be a second thing
  to keep in step. This replaces the package named in PLAN.md §5.

### One gateway in, and scenes are checked on the way out too

- `lessons.bundle.parse_bundle` is the only way a lesson reaches the database. It validates the
  shape and puts every scene through the static scene policy; whatever the input says about its
  own scenes (class name, controls, hash) is discarded and computed from the source.
- `LessonService.store` then checks that every course, concept, objective, and cited section the
  lesson refers to exists. A citation of something that is not in the learner's materials is
  refused: that is what an invented citation looks like.
- `LessonService.get` runs the policy **again** on every stored scene before handing it to the
  player. A database can be restored from a file made elsewhere, and the policy can become
  stricter between versions. A scene that does not pass is **withheld**, not fatal: the player
  shows that segment's description in words and the rest of the lesson plays.
- A lesson whose document no longer fits the IR is reported as `lesson_outdated` (409) rather
  than half-played. It can still be listed and deleted.

### Answer keys never leave the core

- `lessons.get` returns a **player view** (`lessons/player.py`): the lesson without correct
  options, expected values, accepted answers, per-option feedback, or rubric weights. Options
  and ordering items are shuffled in an order that is stable for a lesson.
- `lessons.answer` scores in the core (`evaluation/scoring.py`, deterministic), stores the attempt
  and the evidence in one transaction, and returns the outcome, the feedback for what was chosen,
  the explanation, the right answer, and what changed, in words. A repeat answer to the same
  question counts as aided. A skip is recorded as a skip and reveals nothing.
- An open explanation is self-assessed against a rubric and marked as such in the evidence.
  Model-assisted grading is a separate, bounded step for M6.

### The player: the narrator is the clock

- `LessonController` (plain TypeScript, no React, no timers) owns where the learner is. A beat
  ends when the narrator says it has ended; pausing pauses the narrator. The controller never
  measures time, so swapping the silent narrator for speech (M5) changes nothing else.
- `TimedNarrator` shows captions at the learner's reading pace. It reports no word positions
  because it does not know them; the transcript highlights the beat, not a guessed word.
- Nothing plays until the learner presses Start. After that, later segments start by themselves.
- `SceneCues` carries a beat's cue to the scene on screen. The two are not in step (the scene may
  still be loading, or not yet mounted), so a cue is kept, per segment, until that scene is
  holding on its live page, and is delivered once.
- A checkpoint must be answered or skipped the first time it is met. On a later visit it is only
  offered: going back through a lesson never traps the learner behind a question.
- Progress is saved at segment boundaries. Completion is sticky; a finished lesson reopens from
  the start with every part reachable.

### Mathematics in the interface

KaTeX renders `$…$` through `katex.render` into DOM nodes (never an HTML string), with `trust`
off and a bounded macro expansion. Text that fails to parse is shown as written. All assets,
including small fonts, are emitted as files: the renderer build sets `assetsInlineLimit: 0`,
because the Content Security Policy refuses `data:` fonts and is not going to be relaxed.

### The sample course is package data

`adle_core/sample_course/` holds the course outline, lesson templates, and scene files. Templates
name things by key (`@concept:weighted_sum`); the installer creates the course through the same
services a learner's edits use, substitutes real identifiers, and stores each lesson through
`parse_bundle`. Installing twice returns the same course; a failure removes the half-built one.
The files travel with the core into a packaged build. M4 ships one lesson; the rest arrive in M7.

## Consequences

- A generated lesson (M5) needs no new trust decision: it goes through `parse_bundle` like the
  sample.
- The renderer cannot be made to reveal an answer, because it never has one.
- Re-checking scenes on read costs a few milliseconds per lesson open and removes the database
  from the list of things that have to be trusted.
- The silent narrator makes lessons usable now; real speech is an engine behind an interface that
  already exists.

## Not decided here

Narration engines and voices (M5); how a model's lesson is requested and repaired, within the
one-request-per-scene rule (M5); the misconception lifecycle and the choice of the next step (M6).
