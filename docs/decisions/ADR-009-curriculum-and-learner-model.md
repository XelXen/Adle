# ADR-009: Curriculum graph and learner model

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

M3 gives a course its curriculum (concepts, objectives, prerequisites, links to the learner's
materials) and gives Adle a way to record what a learner has shown about each concept. The plan
asks for a graph with no unresolved loops or references, knowledge stored structurally rather than
in vectors, and mastery changes that can always be explained from recorded evidence.

## Decisions

### The graph is validated on every write, and again on every read

- The rules are pure functions in `adle_core/curriculum/graph.py`: loops (Tarjan, written without
  recursion), unknown or repeated prerequisites, a stable learning order, depth for the map.
- A write that would close a loop is refused with the loop spelled out
  (`"Weights" needs "Gradient descent" needs "Loss" needs "Weights"`). The stored graph is
  therefore always learnable.
- Reading still validates and reports, because data also changes underneath (a source is removed,
  a later version imports a model's proposal). Errors block starting; warnings do not.

### One order, shown as "the path"

A concept has a position (the learner's own order). The **learning order** is the topological
order that follows that position wherever prerequisites leave a choice. The interface shows only
the learning order and lets the learner swap neighbours; a swap that a prerequisite forbids is
explained instead of silently ignored. The whole order is saved at once (`curriculum.reorder`),
so what is stored always equals what was shown.

### A first draft without AI

Headings of imported materials are offered as candidate concepts (`curriculum/outline.py`):
numbering is removed, administrative headings ("Assessment", "References") are skipped, and a
single document title is not mistaken for a topic. Nothing is created until the learner picks.
Titles come from the stored headings, never from the request, so a concept's link to the
materials is genuine. **No prerequisite is inferred from heading order.**

The model-written proposal (plan §6.4) arrives with the provider client in M5 and will go through
the same service and the same rules.

### Knowledge tracing: Bayesian Knowledge Tracing, kept small

- `learner_model/bkt.py`: prior 0.2, learn 0.15, guess 0.2, slip 0.1. A question may supply its
  own guess probability. A hint or a stated lack of confidence can only make a correct answer
  count for *less*. The estimate is clamped away from 0 and 1 so evidence can always move it.
- Parameters are configuration (`TracingConfig`), versioned, and the version is stored with every
  observation.

### What the learner sees is a state, never a score

`learner_model/mastery.py` maps evidence to *Not assessed*, *Building understanding*, *Needs more
evidence*, or *Demonstrated for now*, plus what is still missing. "Demonstrated" needs all of:
estimate ≥ 0.85, three correct answers without help, across two kinds of question, one of them a
transfer question, and no unresolved misunderstanding. One answer can never be enough: the
criteria refuse a configuration that would allow it.

**The estimate never leaves the core.** No API schema has a probability field, and a test checks
that the word does not appear in what the interface receives.

### The record is the source of truth

`learner_observations` is append-only. Each row stores the observation, the state before and
after, and the sentence shown to the learner. `learner_concept_states` is derived from it and can
be rebuilt at any time (`LearnerService.rebuild`, tested against damage).

### Self-rating is a claim, not evidence

A learner can say how well they know a concept. It moves the starting estimate (at most to 0.6)
and, for "I know this well", shows *Needs more evidence*. Once there are answers it only nudges.
It is recorded like any other observation.

### Review scheduling

`learner_model/review.py`: first review a day after the first success above the "promising"
threshold; each recall on time multiplies the gap (2.5 clean, 1.3 with help), scaled by how
strong the evidence is; a miss brings it back the next day; repeating straight away earns
nothing; a late recall earns credit for the longer gap, capped at twice the plan; 90 days at
most. Every decision returns a sentence.

### Retrieval

`application/retrieval.py` defines a `Retriever` interface with one implementation (FTS5, BM25,
any-term queries built from quoted key terms). Results are spread across sources: one passage per
section, and no document takes more than about half the places while another has something.

## Deviations from the plan

- **Working memory and the interaction event log are not built yet.** Their events come from
  lessons, which do not exist until M5. They will be designed with the lesson session rather than
  guessed now.
- **`learning_objectives.id` is stable across edits** (objectives are replaced by id, not by
  position), because lessons and questions will refer to them.

## Alternatives considered

- **Storing only the current state:** simpler, but a mastery change could not be explained or
  recomputed after a parameter change.
- **Exposing the estimate as a percentage:** rejected by the product rules; a handful of answers
  cannot support that precision.
- **Inferring prerequisites from document order:** wrong often enough to be harmful, and
  indistinguishable from real ones once stored.

## Consequences

- Changing a tracing parameter does not rewrite history: old rows keep their explanation, and a
  rebuild shows what the new parameters would say.
- A course with hundreds of concepts returns its whole curriculum on every edit. The limit is 200
  concepts; revisit if that proves small.
