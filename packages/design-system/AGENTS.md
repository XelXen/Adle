# packages/design-system — Sprout

Read the root `AGENTS.md` and `DESIGN_SYSTEM.md` first.

## Rules

- **Tokens are the only source of visual values.** Colours, type, spacing, radii, shadows, and
  motion live in `src/styles/tokens.css`. Component stylesheets reference `var(--ad-*)` and nothing
  else. `tokens.test.ts` fails on a raw colour in any stylesheet here or in the renderer.
- **A new or changed colour must pass contrast in both themes.** Add its pairings to `PAIRS` in
  `tokens.test.ts`. The dark theme must define every colour token.
- **Brand and success are different colours.** `primary` / `action` are the teal of the mark;
  `success` is green and means only "this went well". `brand-ink` is for the logo alone
  (ADR-011).
- **Two voices** (ADR-022): the serif (`text-display`, `-title`, `-subtitle`, `-reading*`) is
  for what is read; the sans is for what is operated. Never a serif button or a sans lesson.
- **The faces are Geist** (ADR-025). Geist Serif has one weight and no italic: never give
  serif text a `font-weight` above 400 or `font-style: italic`. Its file and licence live in
  `src/fonts/geist-serif`; do not replace it with a package that needs a web framework.
- **Three grounds:** `canvas` (the frame), `page` (the main panel), `surface` (a thing on the
  page). A new text colour needs a contrast pair on each ground it is used on.
- **Teal is for the filled action and for selection.** Do not use it to decorate, and do not
  mark importance with a coloured edge.
- **The grounds and the text are neutral** (ADR-027): no tint in any grey, in either theme.
  The filled action is a deep fill with a white label in both themes; do not bring back a
  bright fill with dark text for the dark theme.
- `scene-ink` and `scene-muted` are frozen: scene files have those values written into
  them. `scene-background` is the player's (`scene-run.ts`) and follows `surface`: change
  the token, `scene-palette.ts`, the player and the skill together. If you
  change an accent that scenes share (`success`, `sun`, `coral`, `blue`, `violet`), update
  `src/scene-palette.ts` and the palette table in `skills/wanim-scene-authoring/SKILL.md` (a
  test checks the first; you check the second), then `npm run scene-guide`.
- **One component, one file pair:** `Name.tsx` + `Name.module.css`, exported from `src/index.ts`.
  No one-off variants in screens: extend the component here.
- **A dialog gives the focus back** to what had it, also when it is taken off the page while
  open (a dialog with a form in it is mounted only while open). It is dismissed by a press
  that began and ended on the backdrop, not by a drag that ends there.
- **Where the window is moved** (ADR-030): `WindowStrip` is a drag region along the top
  of the page. Anything that can be pressed and may come to lie there says
  `app-region: no-drag` (the skip link, `Dialog`); the browser cuts those boxes out of the
  strip. The end-to-end helper that runs axe also fails on a control left under it.
- **Scroll bars** are styled once, in `base.css`, with the `::-webkit-scrollbar` parts.
  Setting `scrollbar-width` or `scrollbar-color` anywhere turns those parts off.
- **A toast is not shown over a modal dialog**: everything behind one is inert and blurred.
  Say it inside the dialog, or close the dialog first.
- **Accessibility is part of the component.** Real elements (`button`, `input`, `dialog`), a
  visible label or required `label` prop, keyboard behaviour that follows the WAI-ARIA pattern,
  state exposed with ARIA, visible focus (the global `:focus-visible` ring), and no meaning
  carried by colour alone.
- **States:** hover, pressed, focus, disabled, and (where relevant) loading, invalid, empty.
- **Motion** uses the duration tokens, which collapse under `prefers-reduced-motion`. An
  indicator that would look frozen without motion (spinner, indeterminate bar) keeps a slow or
  static alternative.
- Components take no data-fetching or app state. They do not import from `apps/`.

## Tests

`npx vitest run packages/design-system`. Test behaviour and accessibility wiring (roles, names,
keyboard), not class names. `<dialog>` modality and real focus are covered by the Electron E2E
suite because jsdom does not implement them.
