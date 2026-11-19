# ADR-008: The main window is created visible

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

The usual Electron advice is to create a window hidden (`show: false`) and show it on
`ready-to-show`, so the learner never sees an unpainted window. Adle did that.

In automated launches on Windows, about 1 to 3 in 100 windows created this way never produced a
first frame. The page loaded and its script ran, but no `paint` entry was recorded, no animation
frame ever fired, `capturePage` timed out, and `ready-to-show` never arrived, so the window never
appeared. Hiding and showing the window, resizing it, `webContents.invalidate()`, and reloading
the page did not recover it. A launch loop showed the failure with several different test-side
behaviours and with none (`docs/engineering/PROJECT_STATE.md` has the table), so it is not a
side-effect of one test action. It was not seen in 40 launches with no test driver attached,
which is too few to say a learner would never meet it.

A window that never appears is the worst possible first impression, and an intermittent failure
at that rate also makes the end-to-end suite untrustworthy.

## Decision

Create the main window visible (`show: true`) and do not wait for `ready-to-show`.

The window's `backgroundColor` is the app's canvas colour for the active theme (chosen before the
window exists), so the learner sees the app's own background for the moment before content
appears, not a white flash.

The end-to-end helper waits for the window to be visible, requests keyboard focus, and checks
that the page produces animation frames before a test starts, so a launch that does not paint
fails at once with a clear message instead of timing out later.

## Evidence

- 0 stalls in 150 driven launches with the window created visible, against 6 in 390 across the
  hidden variants.
- The end-to-end suite passed twice in a row with no test needing its retry.

## Consequences

- For a fraction of a second after launch the window shows only its background colour. The
  welcome and library screens render within that time on the development machine.
- If a future change needs a hidden window (a splash screen, restoring a minimised state), it
  must not depend on `ready-to-show` alone: add a time limit after which the window is shown.
- The root cause inside Chromium or Electron is not known. This avoids the code path rather than
  fixing it; re-test when Electron is upgraded.
