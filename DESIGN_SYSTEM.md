# Sprout — Adle's design system

**Playful precision.** Warm, optimistic, and crisp; friendly enough to invite a first try and
serious enough for a university student or an adult learner. Sprout is original: it borrows the
clarity of good learning apps, not anyone's mascot, palette, layouts, or sounds.

Code: `packages/design-system`. Import components from `@adle/design-system`; import
`@adle/design-system/base.css` once at the app entry.

## Principles

1. **Clarity before charm.** If a flourish makes a state harder to read, it goes.
2. **One primary action per view.** Everything else is secondary or tertiary.
3. **Honest progress.** Show what the evidence supports. Qualitative labels for learning state;
   percentages only for tasks with a real denominator (an import, a lesson's segments).
4. **Encourage, never pressure.** No streaks, guilt, or "you failed". Say what happened and what
   to try next.
5. **Works without colour, mouse, sound, or motion.** Each is an enhancement.

## Tokens

All values live in `src/styles/tokens.css` as `--ad-*` custom properties. Nothing else may define
a colour (a test enforces this). Changes from the starting palette are explained in
`docs/decisions/ADR-006-design-tokens-and-theme.md`.

### Colour

| Token | Light | Dark | Use |
|---|---|---|---|
| `canvas` | `#F6F8F4` | `#101713` | App background |
| `surface` | `#FFFFFF` | `#18211C` | Cards, panels, the scene stage |
| `surface-subtle` | `#EEF3ED` | `#1F2A24` | Quiet regions, hover fills |
| `ink` | `#17251E` | `#E7EFE9` | Main text |
| `muted` | `#5F6E65` | `#9DB0A5` | Secondary text |
| `border` | `#DCE5DC` | `#2C3A32` | Hairlines, card outlines |
| `border-strong` | `#7F9084` | `#6C8176` | Boundaries of inputs and switches (3:1) |
| `primary` | `#269B62` | `#3DBE7F` | Brand marks, progress, selection |
| `primary-soft` | `#E2F4E9` | `#1C3327` | Selected and success backgrounds |
| `primary-text` | `#1B7549` | `#6AD3A0` | Green used as text or icon |
| `action` / `-hover` / `-pressed` | `#1F8352` / `#186B43` / `#135636` | `#4CC78C` / `#63D39D` / `#7BDCAE` | Filled primary buttons |
| `on-action` | `#FFFFFF` | `#0C1410` | Text on `action` |
| `sun`, `coral`, `blue`, `violet` | `#F2C14E` `#EF806C` `#5B8DE6` `#9178D7` | `#E9BE5A` `#F08F7D` `#7BA4EE` `#A694E3` | Accents and visualization. **Not for text.** |
| `*-soft` / `*-text` | — | — | Tinted background and its readable text, per accent |
| `danger` / `-soft` / `-text` | `#C84E4E` … | `#E57373` … | Errors and destructive actions |
| `focus` | `#1F6FD6` | `#8AB4F8` | Focus ring |

Contrast is checked by `tokens.test.ts` for both themes: text pairs ≥ 4.5:1 (ink ≥ 7:1), control
boundaries and marks ≥ 3:1.

**Do** pair an accent's `-soft` background with its `-text` colour.
**Don't** put `sun`, `coral`, `blue`, or `violet` text on a surface, or white text on `primary`.

### Typography

Inter Variable, bundled (no network). Six steps:

| Token | Size / line | Weight | Use |
|---|---|---|---|
| `text-display` | 32 / 40 | 700 | Welcome headline only |
| `text-title` | 24 / 32 | 650 | Page title (`h1`) |
| `text-heading` | 18 / 26 | 600 | Section and dialog titles |
| `text-body` | 15 / 24 | 400 | Default |
| `text-body-strong` | 15 / 24 | 600 | Labels, button text |
| `text-supporting` | 14 / 20 | 400 | Descriptions, hints |
| `text-caption` | 13 / 18 | 500 | Badges, meta. Never the only place an instruction appears |

Sizes are in `rem`, so text scales with the user's zoom. Use the `ad-tabular` class for numbers
that change (timers, counts). Mathematics is never set in UI text styles.

### Space, shape, elevation, motion

- **Space:** `--ad-space-1…9` = 4, 8, 12, 16, 24, 32, 40, 48, 64 px. An 8 px grid with a 4 px half step.
- **Radius:** `small` 8 (compact controls), `control` 12, `card` 18, `pill`.
- **Elevation:** `shadow-1` for resting cards, `shadow-2` for dialogs, toasts, and hover lift.
  In the dark theme borders carry separation.
- **Motion:** `duration-fast` 120 ms, `duration-base` 200 ms, one easing curve. Both durations
  collapse under `prefers-reduced-motion`. Motion confirms an action or shows where something
  went; it never decorates.
- **Focus:** one ring everywhere: `2px solid var(--ad-color-focus)`, 2 px offset.

### Theme

Light and dark only, selected by `prefers-color-scheme`. The shell maps the learner's choice
(System / Light / Dark) onto it. There is no theme class or attribute to set.

## Components

| Component | Purpose | Variants and states |
|---|---|---|
| `Button` | An action | `primary`, `secondary` (default), `tertiary`, `destructive`; `small`/`medium`/`large`; hover, pressed, focus, disabled, **loading** (stays focusable, ignores clicks, `aria-busy`); optional leading icon. A `secondary` button with `aria-pressed` is a toggle and shows when it is on |
| `IconButton` | An icon-only action | `label` is required |
| `TextField`, `TextArea`, `Select` | Form input | Label (hideable, never absent), description, **error** (sets `aria-invalid`, announced), disabled, trailing slot |
| `Switch` | An immediate on/off setting | `role="switch"`, optional description |
| `Checkbox` | One of several independent choices in a form that is submitted | Native checkbox; label, optional description, disabled |
| `SegmentedControl` | Two to four exclusive options | Radio group, arrow keys, single tab stop |
| `RadioGroup` | One of a few options that may each be a sentence long, confirmed with a button | Native radios in a fieldset; the whole row is the target; each option named by its own text, with an optional description; disabled; **`readOnly`**: a settled choice that can be read but not changed, nothing dimmed, the chosen row marked without the action tint |
| `Slider` | A bounded number | Native range input; value always shown as text |
| `Card` | Group related content | `surface` / `subtle`; padding `none`/`compact`/`comfortable`; semantic element via `as` |
| `ActionCard` | A whole-card choice | Media, title, description, meta; hover, pressed, disabled |
| `Badge` | Short status | `neutral`, `success`, `info`, `warning`, `danger`, `accent`; optional icon |
| `Callout` | Explain a state or consequence in place | `info`, `success`, `warning`, `danger`; `urgent` to announce immediately; actions |
| `ProgressBar` | Task or content progress | Determinate, indeterminate; `showLabel`; `valueText` |
| `Tabs` | Sections of one page | WAI-ARIA tabs; arrows, Home, End |
| `Dialog` | A decision that must be made now | Native `<dialog>`; `dismissible={false}` while an operation must finish. Focus starts on the close button; a form marks the field to start in with `data-autofocus` |
| `ToastProvider` / `useToast` | Confirm something just done | `success`, `info` auto-dismiss (pause on hover/focus); `danger` stays until dismissed |
| `EmptyState`, `LoadingState`, `ErrorState` | The three non-content states | Title, description, actions; correct live-region role each |
| `Spinner` | Indeterminate activity | Sizes; slows instead of stopping under reduced motion |
| `AppShell`, `NavItem`, `Page`, `Section`, `Stack` | Layout | Rail collapses to icons below 960 px; `Page` width `wide`/`reading` |
| `Logo` | The mark and wordmark | `medium`/`large`; mark only |

App-level components that are not in the package (they depend on app state):

- `ScenePlayer` (`apps/desktop/renderer/src/components`): a Wanim scene with a loading state,
  mirrored accessible controls, and a text fallback.
- `MathText` (`renderer/src/components`): text with inline `$…$` mathematics, typeset by KaTeX
  into DOM nodes with MathML for assistive technology. Text that does not parse is shown as
  written. Use it for anything that comes from a lesson.
- `ConceptMap` (`renderer/src/screens/course`): the curriculum as a picture. Concepts are real
  buttons laid over a decorative drawing of the links; the list view carries the same
  information as text.

## Patterns

### Choosing a button

- One `primary` per view or dialog: the action that moves the learner forward.
- `secondary` for alternatives; `tertiary` for low-emphasis and inline actions.
- `destructive` only on the confirming step of a deletion, never on the button that opens the dialog.
- Verb-first labels that say what happens: **Save key**, **Remove key**, **Try again**. Not "OK".

### Every asynchronous view has four states

`LoadingState` (names what is loading) → content, or `EmptyState` (what belongs here and the next
step) , or `ErrorState` (what happened, what to try). Use `useResource` in the renderer; do not
render nothing while waiting.

### Choosing a control for a choice

| The choice | Use |
|---|---|
| A setting that applies the moment it changes | `Switch` |
| One of two to four options, applied at once and harmless to step through | `SegmentedControl` |
| Several independent options confirmed with a Save button | `Checkbox` |
| An option whose selection *records* something | Separate `Button`s with `aria-pressed`. Never a control that changes as the arrow keys move through it |
| One answer to a question, checked with a button | `RadioGroup`; after checking, `readOnly` with a description on the options that says what each turned out to be |

### After an answer

Say what happened in words, not in colour. The chosen option reads "Your answer", the correct one
"The right answer"; the result is a `Callout` (`success` for right, `info` for anything else,
never `danger`) inside a live region, with the explanation and what the answer changed. A wrong
answer is "Not quite", never "Wrong".

### A lesson's controls stay within reach

The lesson's bar (Previous, Start / Pause / Play again, Continue) sticks to the bottom edge of the
page while a long part scrolls behind it. The primary button is whatever moves the learner on:
Start before anything has played, Continue once the part has come to rest.

### Messages

| Situation | Use |
|---|---|
| Confirm a completed action | Toast (`success`) |
| An action failed and the learner must know | Toast (`danger`) or inline `error` on the field |
| A standing condition of the page | `Callout` |
| A decision that blocks progress | `Dialog` |

### Writing

- Plain, specific, second person. "Adle will stop being able to generate new lessons until you add
  a key again." Not "Are you sure?"
- Errors: what happened, then what to do. Never blame.
- Learning state: *Not assessed*, *Building understanding*, *Needs more evidence*, *Demonstrated
  for now*. Never a bare score, never "mastered" after one answer.
- No exclamation-mark cheerleading, no baby talk.

### Layout

- One `h1` per page (`Page`), `h2` per `Section`.
- Prefer sections and spacing to nested cards. A card inside a card needs a reason.
- Reading text stays under about 44 rem wide (`width="reading"` or `--ad-layout-reading-max`).
- Target sizes: controls are 40 px tall (32 px for `small`, used only in dense toolbars).

## Accessibility baseline

- Keyboard: everything reachable and operable; visible focus; a skip link; composite widgets
  (tabs, segmented control) use one tab stop and arrow keys.
- Names and state exposed through native elements and ARIA; icons are decorative unless labelled.
- Colour is never the only signal (badges carry text, bars change position as well as hue).
- Text scales to 200% without horizontal scrolling at 1280 px.
- `prefers-reduced-motion` and `prefers-color-scheme` are honoured.
- axe (WCAG 2.2 AA) runs on every screen in both themes in the end-to-end suite.

## Scenes

Wanim scenes use the same palette through `src/scene-palette.ts` and the conventions in
`skills/wanim-scene-authoring/SKILL.md`. The stage background is the `surface` token, supplied by
the player.

## Seeing it

`npm run e2e` writes a screenshot of every screen, in both themes and at the minimum window size,
to `apps/desktop/test-results/screens/`. That set is the current visual reference.

## Changing the system

1. Change tokens or components here first, never in a screen.
2. Add contrast pairs for new colours; keep the dark theme complete.
3. Update this document and, for palette changes, the scene skill.
4. Run `npm run check` and `npm run e2e`; look at the screenshots.
