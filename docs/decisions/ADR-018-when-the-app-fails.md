# ADR-018: When the app itself fails, it says so, recovers here, and reports nowhere

- **Status:** Accepted
- **Date:** 2026-11-19
- **Builds on:** ADR-002 (the core process), ADR-008 (the window).

## Context

The plan asks for a "crash/error reporting design that does not upload learner data by
default" and for no unhandled start-up or shutdown failures.

Until now three failures had no handling at all. If the page's process crashed, the learner
was left with an empty window. If the main process threw something nobody caught, Electron
showed its own dialog with a stack trace and carried on in whatever state it was in. If the
core died while the learner was working, every screen failed until they found the restart
button in Settings.

A product would usually answer the first half of the plan's sentence with a crash-reporting
service. Adle has no account, no server, and a promise that nothing leaves the computer but
the request the learner started.

## Decisions

- **Nothing is reported to anyone.** There is no crash reporter, no upload, and no opt-in to
  one. Electron's `crashReporter` is never started.
- **A local log of the app's own failures**, `logs/app.log`: one JSON line per event, with
  the kind of event and a few fixed facts (a reason, an exit code, the name and message of
  an error). It never holds what the learner typed, opened, or answered: callers pass named
  fields, values are cut short, and the file starts afresh at 512 KB. Settings → About has
  "Show log files", which opens the folder; showing a file to someone is the learner's act.
- **A page that crashes** (`render-process-gone`, for any reason but a clean exit): the main
  process says so in a window of the operating system and offers Reload or Quit. Reload is
  the default. The message says that answers and progress were saved as they went, which is
  true because the core saves each as it happens, and that nothing is sent anywhere.
- **A page that stops answering** (`unresponsive`): Wait or Reload, with Wait the default,
  since it may only be busy.
- **An error nobody caught in the main process**: it is logged, the learner is told in the
  same plain way, and the app restarts or quits. It never carries on. A restart is offered
  only once the app has run for fifteen seconds, so a failure at start-up cannot loop.
- **A promise rejected with nobody waiting** is logged and nothing more: one piece of work
  failing is not the whole app failing.
- **A core that stops by itself is started again**, after a second, at most twice in five
  minutes. After that it stays stopped and says so, and the learner can start it from
  Settings. Screens that could not load meanwhile already say so and offer to try again.
- **One question at a time.** A second failure while the learner is still reading about the
  first does not stack another window on top.
- The decisions are plain functions in `electron/main/recovery.ts`, without Electron, and
  `index.ts` only connects them.

## Consequences

- When something goes wrong on a learner's computer, nobody knows unless they say so. That is
  the price of the promise, and the log exists so that saying so is easy.
- The log can contain the message of an error, which may name a file of the app. It is on
  the learner's own disk, in their own profile, beside the data it is about.
- A real crash is tested end to end (`e2e/recovery.spec.ts` kills the page's process). The
  test reads the reloaded window through the main process, because the test driver's own
  handle on a page does not survive that page's process.
- Not covered: a crash of the main process itself in native code. The core then notices its
  parent is gone and stops (ADR-002); nothing is lost, and nothing is logged.
