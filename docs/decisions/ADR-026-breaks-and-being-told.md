# ADR-026: A break while Adle writes, and being told when it is ready

- **Status:** Accepted
- **Date:** 2026-11-20

## Context

A lesson takes minutes to write whichever provider writes it: measured on 2026-11-20, about
twelve with NVIDIA NIM. The interface said "This can take a minute or two", which was not
true, and left the learner looking at a progress bar. The owner asked to use that time to
give the learner a break, like a pomodoro.

Two things limit how. PLAN.md 1 rules out "manipulative streak pressure, shame, arbitrary XP
grind". And a lesson has exactly one clock, its narrator (`apps/desktop/AGENTS.md`): no
timers in the lesson's controller or screen.

## Decisions

- **The wait is said honestly.** Where something is being written, the app says about how
  long that kind of work takes where it is going (ADR-023: measured here, or what is usual
  for the provider), and that the learner does not have to wait for it.
- **A break is offered beside the wait, and at the end of a lesson.** "Take a break" starts
  a timer sized to the wait (three to fifteen minutes; five when nothing says) and opens a
  screen with one clock, one small idea of what to do away from the screen, and what Adle is
  writing meanwhile. It can be made longer or shorter, or ended, at any moment.
- **A break is not counted.** Nothing about it is stored, sent to the core, or shown later:
  no streak, no total, no "you skipped your break". Ending one early is as fine as extending
  it. It exists in the page's memory and is gone when the app closes.
- **The break's clock belongs to the app, not to a lesson** (`app/BreakContext.tsx`). It is
  read from the wall clock each time, so a computer that slept through the end wakes to a
  break that is simply over.
- **What is being written is visible from anywhere.** The rail shows that a lesson or a list
  of concepts is on its way (`jobs.list_writing`), and a running break, one click away.
- **The learner is told when it is ready**, wherever they are: by the app (a toast, unless
  the screen in front of them already shows it), and by the operating system if Adle is not
  the window they are looking at.
- **A notification carries fixed words.** The page asks for one by its kind
  (`window.adle.app.notify('lesson_ready')`); the main process validates the kind against a
  closed list and chooses the title and the sentence itself (`electron/main/notices.ts`).
  No title of a course or lesson, no text of the learner's, and nothing a model wrote can
  reach the notification centre, where other people may read it and other programs may keep
  it. Clicking one brings back the window that is already open.
- **Notifications can be turned off** (Settings → Appearance), are on by default, and are
  never shown while Adle's window has the focus.

## Consequences

- A new function on the bridge, `app.notify(kind)`, and one more field in the interface
  state the main process keeps (`notifications`). The bridge's exact surface is asserted in
  `e2e/security.spec.ts`.
- Notifications are local to the computer (Electron's `Notification`). Nothing is sent
  anywhere, and no service is involved.
- In end-to-end tests notifications are recorded and never shown (`recordNotices` in
  `e2e/support/app.ts`): the app's decision runs as it does for a learner, and the last
  step is replaced.
- The suggestion of what to do in a break is one of six fixed sentences. One of them invites
  the learner to recall the last idea in a sentence; nothing checks whether they did.
- Opening a lesson while its pictures are still being drawn (PROMPT.md 3, "never make the
  learner wait for a whole chapter") is still not done: a lesson appears when all of it is
  ready. The break makes the wait easier; it does not shorten it.
