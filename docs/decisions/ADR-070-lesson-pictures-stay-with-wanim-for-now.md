# ADR-070: A lesson's pictures stay with Wanim, for now

- **Status:** Accepted
- **Date:** 2026-11-25
- **Keeps:** ADR-004 and ADR-049 (a lesson's pictures are Wanim scenes run in the sandboxed
  player frame), ADR-065 (ManimGX makes films, outside the frame, and nothing else).

## Context

The owner, on 2026-11-25, having watched a film made with ManimGX (ADR-065): "switch to
manimgx for film look if it can act the same way as wanim because i think it can be
embedded too ... because it uses pyodide but your choice". ManimGX's documentation
(rendering, "Embed in a web page", read the same day) says that it runs in a web page with
no server, as an npm package with a `<manimgx-player>` element: Pyodide runs the scene's
Python in a web worker and WebGPU draws it. The first video downloads Python and ManimGX,
about 26 MB. It needs WebGPU (Chrome and Edge 113 or later, Safari 26). It makes the video
from the scene and then plays it. Its own code is under the MIT licence.

A film is clean for another reason than its engine: each chapter is run by the engine,
which reports every overlap by line, and is sent back to its writer up to three times,
then looked over by a model that sees pictures (ADR-065, ADR-066). A lesson's slides had no
such loop.

## Decision

A lesson's pictures stay Wanim scenes in the sandboxed player frame. ManimGX's browser
player is not used for them yet, because:

1. **It needs WebGPU**, which Chromium leaves off by default on Linux and which older
   graphics hardware lacks; Wanim draws on a 2D canvas wherever Adle runs. A lesson must
   never be without its pictures because of the computer it is on.
2. **Every picture is a frame of its own**, on an origin and in a process of its own
   (ADR-004). Each would start Python and load about 26 MB before it could draw: seconds
   for every slide, where a Wanim scene starts at once.
3. **It makes a video and then plays it.** A slide steps with the narration's cues, holds
   between them, says its steps and its layout to the host, and has a keyboard mirror for
   each control: all of it would have to be built again around a video, and an interactive
   picture cannot be one.

What makes a film clean comes to slides instead: each is checked as it is tried in the
hidden frame, and one that is crowded is sent back to its writer, beside the writing of
the rest (ADR-073).

## When to look again

When ManimGX's player draws without WebGPU, starts in under a second in a frame of its own,
and can be held between steps and told to go on; or when a slide is made a film of its
own, drawn by the film maker in the background where it is set up, and played on the
lesson's screen with Wanim's as its fallback.
