# ADR-038: A picture is tried before it is shown, and one that breaks is written again, told why

- **Status:** Accepted
- **Date:** 2026-11-21
- **Changes:** ADR-012 in one respect: what the one deliberate retry of a scene is told.
  The number of requests is unchanged.

## Context

A scene is a Python file a model wrote. The static rules (`scene_policy`, ADR-004) say what
it may not do, and a file that breaks one is asked for once more, told which (ADR-012).
Whether it *works* only running it says: a name spelled wrong, a method that does not take
those arguments, a control whose reaction divides by zero. Such a file passed every check,
was kept, and failed in front of the learner: "Couldn't show the animation. Here's the
same idea in words."

The owner: "test out the animation before presenting to the user — sometimes animations
fail … so it should fix the error it got and then continue."

A scene can only run in the app's scene player: a sandboxed frame of the desktop app, on an
origin of its own (ADR-004). It cannot run in the core, which has no browser and must not
grow one. And it runs at a learner's pace: a 15-second scene takes 15 seconds.

## Decisions

- **The player can rehearse.** A load says whether it is a rehearsal (`rehearsal` in the
  event protocol). For a rehearsal the frame hands out animation frames as fast as they
  are asked for, one task each, its own housekeeping with them, and its clock
  (`performance.now()`, by which Wanim paces frames and waits) runs 25 times as fast. The
  scene is drawn small. Everything it reports is what it reports at a learner's pace. A
  sample scene goes by in 0.3 to 1 second instead of 14 to 17.
- **The core offers each picture it would keep for a trial, and waits for the verdict**
  (`SceneTrials`): after the rules pass, before the picture joins the lesson. The app asks
  for trials while a lesson is being written (`scenes.trials`, every second); asking is
  how the core knows it is there. When it is not there, or does not answer within a
  minute, the picture is kept untried, as before, and the player still says it in words if
  it fails.
- **The app runs each trial in a player frame nobody sees** (`SceneTrials` in the app,
  `lib/scene-trial.ts`): the whole scene, each interactive page with every control moved
  to its ends and back, the next page, the last. What went wrong is reported as the
  player said it (`scenes.report_trial`): where (compile, runtime, a control, a stall) and
  the message, cut to 500 characters. A scene not seen to fail in 30 seconds passes.
- **A picture that fails its trial is asked for once more, told what went wrong**: the
  error, quoted as data, and the file that failed, quoted with its lines as they were.
  This is the one deliberate retry ADR-012 allows, now told by the trial instead of only by
  the rules: a picture still costs at most two requests. A second file that fails its trial
  is not kept: that part is explained in words, and the learner is told once, as for a
  picture that could not be made.
- Logs say a trial failed and at which stage, never what the scene said (ADR-029).

## Consequences

- A picture that breaks in its first seconds, or when a control is moved, is no longer met
  by the learner; it is fixed, or the part is said in words before the lesson is opened.
- A picture that fails only after more than 30 seconds of rehearsal (twelve minutes of a
  scene), or only on another computer, can still fail in front of the learner. The
  player's fallback stays.
- The page asks the core for scene sources while a lesson is written. These are the
  sources it would be given to show anyway; the frames they run in are the ordinary,
  sandboxed player frames, removed when the trial ends.
- What a scene said when it failed reaches the provider in the second request. It is the
  model's own code failing, cut short and quoted; it carries nothing of the learner's.
- Unit tests: the trial registry, the routes, a lesson whose picture passes, fails once,
  fails twice; the frame clock rushing and the time warp; the trial runner on a scripted
  player. Journeys: a rehearsal runs a sample scene through in under a quarter of its
  time with the same messages (`scene-player.spec.ts`); a scene that breaks halfway is
  written again told why and the lesson shows the one that runs; one that breaks twice is
  said in words (`generation.spec.ts`).
