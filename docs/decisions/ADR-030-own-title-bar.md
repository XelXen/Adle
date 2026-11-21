# ADR-030: The window has a title bar of the app's own

- **Status:** Accepted
- **Date:** 2026-11-20

## Context

The window had the title bar the operating system draws: a white (or grey) band with the
window's name, above an app whose every other surface is its own. On a near-black app it was
the one thing that did not belong. The owner: "why not make a custom window title bar
instead of using windows default, that look ugly".

There are two ways to do it in Electron. One removes the frame altogether and has the page
draw the buttons, which then need a way to ask the main process to minimise, maximise and
close: three new things for a page to call, and the loss of what the system's own buttons do
(on Windows 11, the layouts offered when the pointer rests on "maximise"). The other hides
only the title bar and has the system lay its own buttons over the page, in colours the app
names.

## Decisions

- **The title bar is hidden, and the window's buttons stay the system's**
  (`titleBarStyle: 'hidden'` with `titleBarOverlay` on Windows, `'hiddenInset'` on macOS).
  Nothing new crosses the bridge: the page cannot minimise, maximise, or close the window,
  and does not need to.
- **The buttons are drawn in the app's colours**: on the canvas, in the ink of the theme,
  40 pixels tall. They are repainted when the theme changes, with the window's background.
- **The page keeps a strip along its top to move the window by** (`WindowStrip`,
  `-webkit-app-region: drag`). The strip holds nothing; the mark in the rail sits in it,
  level with the buttons, and the main panel begins below it. Its height is the one the
  browser reports for the area beside the buttons, so it stays right when the text is
  enlarged.
- **Nothing that can be pressed lies under the strip**, where a press would move the window
  instead. What has to appear there is cut out of it (`app-region: no-drag`): the link that
  skips to the content, which appears there for the keyboard, and a dialog. A dialog was
  found to need it: at the smallest window, or with the text enlarged, a tall one reached to
  16 pixels from the top edge, and its close button would have moved the window. It is now
  also never taller than the window less twice the strip, so it stays clear of the window's
  own buttons.
- **A dialog dims the page from below the strip.** The system's buttons are drawn in the
  app's canvas colour on top of the page; with the page dimmed around them they stood out
  as a bright block in the corner. The strip is the window's and keeps its look, as a title
  bar does behind a dialog of the system's own.
- **Linux keeps the frame it is given.** The overlay is not something that could be tried
  there, and a window that cannot be moved is worse than a plain one. The page is told
  whether the window owns its title bar (`data-ad-titlebar` on the document, set from the
  platform before the first render); without it the strip has no height and nothing moves.
- **Scroll bars** are a rounded bar the colour of a control's edge, without arrows or a
  track, to match.

## Consequences

- The application menu is no longer reachable with the pointer on Windows (there is no bar
  to show it in). Its keys still work: text size is Ctrl with + or −, which is what the
  Appearance settings now say.
- The window's name is no longer written in the window. It is still its name in the taskbar.
- Checked on Windows 11 by drawing the app's own window into a picture, in both themes, at
  the default and the minimum size, with a dialog open, and with the text enlarged. **Not
  run on macOS** (the mark is moved clear of the window's buttons there by the area the
  browser reports, untried).
- `e2e/appearance-a11y.spec.ts` checks that the strip is there, that the window has no title
  bar of the system's, and that a dialog as tall as the smallest window allows stays below
  the strip. That nothing pressable is left under the strip is checked wherever a journey
  checks a screen for accessibility, which is every screen and state there is
  (`expectNoAccessibilityViolations`). A real press cannot be tried by a test: the tool's
  clicks do not pass through the window's frame, so the check is of where things lie.
