# Sprout — Adle's design system

**A quiet study.** Adle should look like a well-made book that happens to be software: calm,
exact, and warm enough to invite a first try. The second edition (ADR-022) keeps what the first
got right (tokens, one accent, honest states) and replaces what made it look like every other
app: one typeface at one weight for everything, large radii, a tinted ground with white boxes
on it. Sprout is original: it borrows the clarity of good learning tools and good editorial
design, not anyone's mascot, palette, layouts, or sounds.

Code: `packages/design-system`. Import components from `@adle/design-system`; import
`@adle/design-system/base.css` once at the app entry.

## Principles

1. **Clarity before charm.** If a flourish makes a state harder to read, it goes.
2. **One primary action per view.** Everything else is secondary or tertiary.
3. **Two voices.** What is *read* (a title, a lesson's own words, a question) is set in the
   serif. What is *operated* (a label, a button, a count) is set in the sans. The difference
   tells the learner which is which before they have read a word.
4. **Three grounds.** The `canvas` is the frame of the app. The `page` is what content is
   read on. A `surface` is a thing lying on the page. Nothing else gets a background of its
   own without a reason.
5. **The brand colour is spent sparingly.** Teal is the one filled action and the mark of
   selection. It does not decorate. A page with teal everywhere has no primary action.
6. **Honest progress.** Show what the evidence supports. Qualitative labels for learning state;
   percentages only for tasks with a real denominator (an import, a lesson's parts).
7. **Encourage, never pressure.** No streaks, guilt, or "you failed". Say what happened and what
   to try next.
8. **Works without colour, mouse, sound, or motion.** Each is an enhancement.

## Tokens

All values live in `src/styles/tokens.css` as `--ad-*` custom properties. Nothing else may define
a colour (a test enforces this). Why the values are what they are:
`docs/decisions/ADR-006-design-tokens-and-theme.md` (the first edition),
`docs/decisions/ADR-011-brand-mark-and-colour.md` (the brand colour), and
`docs/decisions/ADR-022-sprout-second-edition.md` (the structure), and
`docs/decisions/ADR-027-neutral-palette.md` (these colours: neutral grounds, no tint in any grey).

### Colour

| Token | Light | Dark | Use |
|---|---|---|---|
| `canvas` | `#F3F3F3` | `#0A0A0A` | The frame of the app: the rail lies on it |
| `page` | `#FCFCFC` | `#0E0E0E` | What content is read on: the main panel |
| `surface` | `#FFFFFF` | `#141414` | A thing on the page: cards, dialogs, fields |
| `surface-subtle` | `#F6F6F6` | `#1A1A1A` | Quiet regions, hover fills |
| `surface-sunken` | `#ECECEC` | `#070707` | A well: a track, the ground of a segmented control, a neutral badge |
| `ink` | `#171717` | `#EDEDED` | Main text |
| `muted` | `#5C5C5C` | `#A3A3A3` | Secondary text |
| `faint` | `#696969` | `#8C8C8C` | The quietest text that is still text: a count, a date, a label above a group |
| `border` | `#E7E7E7` | `#232323` | Hairlines, card outlines |
| `border-control` | `#D4D4D4` | `#383838` | The edge of a button, which its label already identifies |
| `border-strong` | `#808080` | `#737373` | Boundaries of fields and switches (3:1) |
| `primary` | `#167D8D` | `#3FB4C5` | The brand teal: the mark, progress, selection |
| `primary-soft` | `#E6F3F4` | `#0F272C` | Selected and highlighted backgrounds |
| `primary-text` | `#0D6370` | `#5CC8D6` | Teal used as text or icon |
| `action` / `-hover` / `-pressed` | `#12707E` / `#0E616D` / `#0B525C` | `#147989` / `#16808F` / `#106874` | Filled primary buttons: a deep fill in both themes |
| `on-action` | `#FFFFFF` | `#FFFFFF` | Text on `action` |
| `brand-ink` | `#071B2B` | `#EDEDED` | The dark letter of the mark. Nothing else |
| `success` / `-soft` / `-text` | `#269B62` / `#E4F3EA` / `#1B7549` | `#3DBE7F` / `#11261A` / `#6AD3A0` | Something went well: success badges, callouts, toasts |
| `sun`, `coral`, `blue`, `violet` | `#F2C14E` `#EF806C` `#5B8DE6` `#9178D7` | `#E9BE5A` `#F08F7D` `#7BA4EE` `#A694E3` | Accents and visualization. **Not for text.** |
| `*-soft` / `*-text` | — | — | Tinted background and its readable text, per accent |
| `danger` / `-soft` / `-text` | `#C84E4E` … | `#C24545` … | Errors and destructive actions (a white label on the fill, in both themes) |
| `focus` | `#1F6FD6` | `#8AB4F8` | Focus ring |
| `scene-background` / `-ink` / `-muted` | `#FFFFFF` `#17251E` `#5F6E65` | `#141414` `#E7EFE9` `#9DB0A5` | The stage of a scene and what is drawn on it. The ink and the muted text are frozen (see "Scenes"); the background is the player's and follows `surface` |

Contrast is checked by `tokens.test.ts` for both themes: text pairs ≥ 4.5:1 (ink ≥ 7:1), control
boundaries and marks ≥ 3:1, on every ground a text colour is used on.

**Do** pair an accent's `-soft` background with its `-text` colour.
**Do** use `success` for an outcome and `primary` for the product: they are different colours on
purpose.
**Don't** put `sun`, `coral`, `blue`, or `violet` text on a surface. For a filled control use
`action` with `on-action`, never a colour pair of your own.
**Don't** mark a card as important with a coloured bar down its side. If one thing on a page
matters most, it is the only one with a filled button, and it may carry a wash of
`primary-soft` from its top edge (`NextSteps`).

### Typography

One family, Geist, in three voices, all bundled (no network), each with one job (ADR-025):

| Face | Token | For |
|---|---|---|
| Geist Serif (Regular) | `--ad-font-serif` | What is read: titles, lesson text, questions |
| Geist Sans (variable) | `--ad-font-sans` | What is operated: labels, controls, data, descriptions |
| Geist Mono (variable) | `--ad-font-mono` | What is typed or copied exactly: an address, a model's name, a key on the keyboard |

Geist Serif is drawn in **one weight and no italic**. Every serif text style is weight 400,
and `font-synthesis: none` is set for the whole app, so the browser never fakes a bold or a
slanted version of it. Emphasis inside serif text is said in words, or set in the sans.

| Token | Family | Size / line | Weight | Use |
|---|---|---|---|---|
| `text-display` | serif | 46 / 50 | 400 | Welcome headline only |
| `text-title` | serif | 32 / 38 | 400 | Page title (`h1`) |
| `text-subtitle` | serif | 23 / 30 | 400 | A part of a lesson, a dialog's title, an empty state |
| `text-reading-large` | serif | 22 / 31 | 400 | A question, a point written on the board |
| `text-reading` | serif | 19 / 29 | 400 | A lesson's narration as text |
| `text-heading` | sans | 16 / 24 | 600 | Section titles |
| `text-body` | sans | 15 / 24 | 400 | Default |
| `text-body-strong` | sans | 15 / 24 | 550 | The name of a thing in a row |
| `text-control` | sans | 14 / 20 | 550 | Buttons, tabs, the rail, field labels |
| `text-supporting` | sans | 13.5 / 20 | 400 | Descriptions, hints |
| `text-caption` | sans | 12 / 16 | 500 | Badges, meta. Never the only place an instruction appears |
| `text-eyebrow` | sans | 11 / 16 | 600 | A label above a group, in capitals with `tracking-eyebrow` (`.ad-eyebrow`) |
| `text-mono` | mono | 13 / 20 | 400 | Addresses, identifiers |

Sizes are in `rem`, so text scales with the user's zoom. Titles take `tracking-display`; names
and labels take `tracking-tight`. Use the `ad-tabular` class for numbers that change (timers,
counts). Headings balance their lines and paragraphs avoid a stray last word
(`text-wrap`). Mathematics is set by KaTeX at the size of the words around it, never in a UI
text style.

**Do** set a lesson's own words in the serif, wherever they appear.
**Don't** set a button, a field, or a number in the serif, or a paragraph of interface copy in
capitals. An eyebrow is two or three words. **Don't** put `font-weight` above 400 or
`font-style: italic` on serif text: there is no such drawing of it, and nothing will change.

Scenes are drawn with their own typeface (Inter, in the player frame), like their colours:
see "Scenes".

### Space, shape, elevation, motion

- **Space:** `--ad-space-1…9` = 4, 8, 12, 16, 24, 32, 40, 48, 64 px. An 8 px grid with a 4 px half step.
- **Radius:** `small` 6 (badges, compact controls), `control` 8, `card` 12, `large` 16 (dialogs,
  the main suggestion), `pill` (tracks and dots only: a badge is not a pill).
- **Elevation:** three heights, and most things have none. `shadow-1`: a card resting on the
  page. `shadow-2`: a card under the pointer, the lesson's bar. `shadow-3`: a dialog, a toast.
  `shadow-control` and `shadow-action` give a button its edge. In the dark theme borders
  carry separation.
- **Motion:** `duration-fast` 120 ms, `duration-base` 200 ms, `duration-slow` 320 ms, one
  easing curve. All collapse under `prefers-reduced-motion`. Motion confirms an action or
  shows where something went (a page settling, a dialog arriving, a line of the board being
  written); it never decorates.
- **Focus:** one ring everywhere: `2px solid var(--ad-color-focus)`, 2 px offset.
- **Scroll bars:** a rounded bar the colour of a control's edge, darker under the pointer,
  with no track and no arrows (`base.css`). They are drawn with the browser's own parts;
  do not set `scrollbar-width` or `scrollbar-color` anywhere, which would switch those off.

### Theme

Light and dark only, selected by `prefers-color-scheme`. The shell maps the learner's choice
(System / Light / Dark) onto it. There is no theme class or attribute to set.

## Components

| Component | Purpose | Variants and states |
|---|---|---|
| `Button` | An action | `primary`, `secondary` (default), `tertiary`, `destructive`; `small`/`medium`/`large`; hover, pressed, focus, disabled, **loading** (stays focusable, ignores clicks, `aria-busy`); optional leading icon. A `secondary` button with `aria-pressed` is a toggle and shows when it is on |
| `IconButton` | An icon-only action | `label` is required. `variant="stage"` on the lesson's screen, which is dark in either theme |
| `TextField`, `TextArea`, `Select` | Form input | Label (hideable, never absent), description, **error** (sets `aria-invalid`, announced), disabled, trailing slot. A `Select`'s list is drawn by the page in the theme's colours (`appearance: base-select`), never by the system, whose list takes its colours from the computer and not from the theme; it keeps a native select's keys (arrows, typing, Escape) and its meaning for assistive technology |
| `InfoPopover` | Something worth knowing that nobody needs to read every time (what a request sends and where, who wrote a lesson) | An icon button and a note that opens beside it, above everything else; Escape or a press elsewhere closes it; the button says whether it is open. Never the only place for something the learner must act on |
| `Switch` | An immediate on/off setting | `role="switch"`, optional description |
| `Checkbox` | One of several independent choices in a form that is submitted | Native checkbox; label, optional description, disabled |
| `SegmentedControl` | Two to four exclusive options | Radio group, arrow keys, single tab stop |
| `ChoiceButtons` | One of a few options that takes effect, and is recorded, the moment it is pressed (which provider to use) | A group of buttons with `aria-pressed`; arrow keys change nothing; each named by its title, badge, and description in that order; `pending` while the choice is being put into force |
| `RadioGroup` | One of a few options that may each be a sentence long, confirmed with a button | Native radios in a fieldset; the whole row is the target; each option named by its own text, with an optional description; disabled; **`readOnly`**: a settled choice that can be read but not changed, nothing dimmed, the chosen row marked without the action tint |
| `Slider` | A bounded number | Native range input; value always shown as text |
| `Card` | Group related content | `surface` / `subtle`; padding `none`/`compact`/`comfortable`; semantic element via `as` |
| `ActionCard` | A whole-card choice | Media, title, description, meta; hover, pressed, disabled |
| `Badge` | Short status | `neutral`, `success`, `info`, `warning`, `danger`, `accent`; optional icon |
| `Callout` | Explain a state or consequence in place | `info`, `success`, `warning`, `danger`; `urgent` to announce immediately; actions |
| `ProgressBar` | Task or content progress | Determinate, indeterminate; `showLabel`; `valueText` |
| `Tabs` | Sections of one page | WAI-ARIA tabs; arrows, Home, End |
| `Dialog` | A decision that must be made now | Native `<dialog>`; `dismissible={false}` while an operation must finish. Focus starts on the close button; a form marks the field to start in with `data-autofocus`; focus goes back to what opened it. It keeps clear of the window's strip, and a press on it is never a hold on the window |
| `ToastProvider` / `useToast` | Confirm something just done | `success`, `info` auto-dismiss (pause on hover/focus); `danger` stays until dismissed |
| `EmptyState`, `LoadingState`, `ErrorState` | The three non-content states | Title, description, actions; correct live-region role each |
| `Spinner` | Indeterminate activity | Sizes; slows instead of stopping under reduced motion |
| `AppShell`, `WindowStrip`, `NavItem`, `NavSection`, `Page`, `Section`, `Stack` | Layout | `WindowStrip` is what the window is moved by where it has no title bar of the system's (see "The window"). The rail lies on the canvas and the main region is a panel set into it; `focus` leaves the rail out and gives one thing the whole window (a lesson, a round of questions); `NavSection` is a labelled group in the rail (the learner's courses). Rail collapses to icons below 960 px; `Page` width `wide`/`reading`, and `density="compact"` (a smaller title and less air) for a page that gives its room to one thing, such as a lesson's screen; a page's actions sit on the line of its title |
| `Logo` | The mark and wordmark | `medium`/`large`; mark only |

App-level components that are not in the package (they depend on app state):

- `ScenePlayer` (`apps/desktop/renderer/src/components`): a Wanim scene with a loading state,
  mirrored accessible controls, and a text fallback. `onStage` puts it on the lesson's
  screen and draws it with the dark palette whatever the theme.
- `StageFrame` (`renderer/src/components`): the lesson's screen. A header line, the screen
  at 16 to 9, and the words being said along its foot.
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
| One of a few options, each a sentence, that takes effect at once and matters | `ChoiceButtons` |

### After an answer

Say what happened in words, not in colour. The chosen option reads "Your answer", the correct one
"Correct answer" ("Your answer · correct" when they are the same); the result is a `Callout` (`success` for right, `info` for anything else,
never `danger`) inside a live region, with the explanation and what the answer changed. A wrong
answer is "Not quite", never "Wrong".

### What next

A suggestion is shown the same way everywhere (`NextSteps`, in the app): the Learn tab, the end
of a lesson, the end of a set of questions. One card with "Up next" as an eyebrow,
the step as a heading in the serif, **Why:** and the reason, and one primary button. It is the
only card with a wash of the brand colour. Under it, "Other options": the alternatives as a quiet
list, each with its own reason and a secondary button. A suggestion is never the only way
forward and never a blocker.

- The button says what it does ("Start lesson", "Start review", "Answer a few questions"); the
  heading says what with. The button is described by the heading, so two "Start lesson" buttons
  on one screen are told apart by a screen reader.
- A step that needs something the learner has not set up says so beside its button and leads
  there. It is never hidden, and never placed before a step that can be done.
- A step with nothing to do ("Nothing is due") has no button.
- What Adle has noticed about a concept is a `Badge` for how far the evidence goes
  ("Suspected, not established", "Seen more than once", "Set aside", "Sorted") and a sentence.
  Never `danger`: a hypothesis is not an error.

### Work the AI is doing

Anything the provider is asked to do takes a while and may fail, so it is always shown the same
way (`GenerationStatus`, in the app): a progress bar with what is happening now and a Cancel
button; then either the result where it belongs, or a `Callout` that says what happened and
offers the one useful next step ("Try again", "Open AI settings"), or nothing but "Dismiss"
when waiting is the only remedy. Before the request: say what will be sent and to whom, in the
words the core plans at that moment (`destination` in `lib/provider.ts`).

A lesson takes minutes. So the wait is said honestly ("Usually takes about 12 minutes. You'll
be notified when it's ready."), and the same card offers a break. What is being
written is in the rail under "Now", one click from anywhere.

### A break

A break (`screens/break`) has the whole window, like a lesson, and the opposite purpose: one
clock that needs no watching, one small idea of what to do away from the screen, and what Adle
is writing meanwhile. The time left is the only large number in the app that changes; it is
set in the serif with `ad-tabular`, inside a ring that fills as the time passes.

**Do** offer a break; **don't** start one, count them, or remind anyone they did not take one.
Ending early and adding five minutes are equally good outcomes and look it.

### A question asked during a lesson

A learner can ask about the part in front of them ("Ask a question", in the lesson's bar).
It is a note in the margin, not a conversation:

- **Asking** is a dialog: their own words, or one of a few ready-made questions; what will
  be sent and where; and one button. Nothing is sent before it.
- **Waiting** is optional. The dialog says so ("No need to wait here") and offers
  "Continue lesson"; opened again, it shows the answer on its way, with "Stop".
- **The note** is kept beside its part, folded away under "Your questions about this part".
  The learner's words are theirs: the sans, behind a rule, shown exactly as typed. The answer
  is something to read: the serif, with mathematics typeset. Under it, one line: who
  answered, and that AI can make mistakes.

**Don't** show earlier questions as a thread, give the field a "send" arrow, or put a typing
indicator anywhere. Each question stands alone.

### A lesson has the whole window

A lesson, and a round of questions, are one thing to attend to: the rail is left out
(`AppShell focus`) and the way back is the first thing on the page.

- **Where the learner is** is a strip cut into as many pieces as the lesson has parts: done in
  teal, the present one in ink, the rest sunken. Each piece is a button with a name ("Part 3:
  The bias"); it shows no number.
- **A lesson is watched on a screen** (`StageFrame`, ADR-035): one dark surface in either
  theme (`--ad-color-stage*`), as wide as the page allows and no taller than leaves the
  title above it and the controls below it in view. A picture is on it at 16 to 9, always
  drawn with the dark scene palette. A part without a picture puts its board on it; a
  board with nothing on it yet shows the part's title. Along its top, one quiet line:
  what the part is, the picture in words if asked for, and "Part 3 of 10". A question is
  not on the screen: it is a card of the page.
- **The words being said run along the foot of the screen**, one line at a time, the word
  the voice has reached marked (`--ad-color-stage-mark`). They are the transcript: every
  line is in the page, and one press unfolds them into a list, the line being said in ink
  with a rule beside it. With nothing spoken the list starts unfolded.
- **The lesson's own words** are in the serif: the board, the words being said, a question.
- **The controls stay within reach.** One bar (Previous, Start / Pause / Play again, Continue)
  floats at the bottom edge while a long part scrolls behind it. The primary button is
  whatever moves the learner on: Start before anything has played, Continue once the part
  has come to rest.
- **The lesson can fill the screen** ("Full screen", Escape gives it back). The ground is
  then the screen's own dark; the bar of controls keeps its place and fades while the
  lesson plays and nothing is being done. What is not on the lesson's screen keeps the
  page's colours, on a card of the page's. On that dark ground use `IconButton
  variant="stage"`; a control in the page's colours goes on a surface of the page's.
- **What a lesson is, where it draws from and who wrote it** is one press away, beside its
  title (`InfoPopover`, "About this lesson"), not under it.

### Messages

| Situation | Use |
|---|---|
| Confirm a completed action | Toast (`success`) |
| An action failed and the learner must know | Toast (`danger`) or inline `error` on the field |
| A standing condition of the page | `Callout` |
| A decision that blocks progress | `Dialog` |

### Writing

The rule is ADR-028: short, plain, and about the learner's task. In American English
(ADR-044): practice, math, color, gray, license, canceled.

- One sentence where one will do, the point first, in ordinary speech with contractions:
  "Couldn't save your goal", "Key saved", "Loading library…".
- A confirmation asks one question, says what goes and what stays, and offers "Cancel" and
  the action by its name: "Remove the AIHubMix key?" / "Remove key". Not "Are you sure?"
- Errors: what happened, then what to do. Never blame.
- Nothing about how the app works unless the learner has to act on it. No "local service",
  no request counts beside a button, no sentence about what a setting does inside.
- **Say less** (ADR-036). A sentence stays where the learner has to act on it or decide by
  it: why the next step was chosen, what a destructive action removes, what went wrong
  and what to do, that importing uploads nothing. What a request to an AI provider sends,
  where it goes and how long it takes is one press away from the control that sends it
  (`WhatIsSent`, an `InfoPopover`), in the words "Sends *what* to *where*."; what a lesson
  is made from and who wrote it is one press away beside its title. Under an answer the
  learner asked for, "Answered by *model* on *provider*. AI can make mistakes." is part of
  what is read, and stays. Settings is where explanations live, kept short.
- Learning state: *Not started*, *Learning*, *Nearly there*, *Understood*. Never a bare score,
  never from one answer. A right answer that counts for less is "with help".
- Typographic quotation marks and apostrophes; a title is quoted “like this”.
- No exclamation-mark cheerleading, no baby talk.

### Layout

- One `h1` per page (`Page`), `h2` per `Section`.
- **Sections of a page stand 32 px apart** (`--ad-space-6`), and what belongs to a section
  12 px under its title (`--ad-space-3`). `Page` and a tab's panel lay their children out
  that way: a screen hands them its sections and sets no distance between them itself.
- Prefer sections and spacing to nested cards. A card inside a card needs a reason.
- Reading text stays under about 44 rem wide (`width="reading"` or `--ad-layout-reading-max`).
- Target sizes: controls are 36 px tall (30 px for `small`, used in rows and toolbars; 44 px
  for `large`, used for the one way forward on a screen such as the welcome). Nothing that can
  be pressed is smaller than 24 px in either direction.
- A page's title and what can be done to the whole page share one line; a way back sits above
  them.

### The window

On Windows and macOS the window has no title bar of the system's (ADR-030): the app's own
canvas runs to the top edge, and the system lays its own buttons over the corner in the
theme's colours.

- `WindowStrip` lies along the top, 40 px tall, and is what the window is moved by. It holds
  nothing. The mark in the rail sits in it, level with the window's buttons; the main panel
  begins below it.
- **Nothing that can be pressed lies under the strip**: a press there moves the window. A
  screen drawn outside `AppShell` leaves that much room. What has to appear there (the link
  that skips to the content, a dialog) is cut out of it with `app-region: no-drag`.
- A dialog is never taller than the window less twice the strip, so it stays clear of the
  window's buttons as well, and it dims the page from below the strip: the strip keeps its
  look while a dialog is open.
- Linux keeps the frame it is given; there the strip has no height and nothing moves.

## Accessibility baseline

- Keyboard: everything reachable and operable; visible focus; a skip link; composite widgets
  (tabs, segmented control) use one tab stop and arrow keys.
- Names and state exposed through native elements and ARIA; icons are decorative unless labelled.
- Colour is never the only signal (badges carry text, bars change position as well as hue).
- Text scales to 200% without horizontal scrolling at 1280 px.
- `prefers-reduced-motion` and `prefers-color-scheme` are honoured.
- axe (WCAG 2.2 AA) runs on every screen in both themes in the end-to-end suite.

## The mark

The Adle mark is the letters "a" and "d" as two interlocking rings, the "d" in front.

| What | Where |
|---|---|
| The owner's artwork | `apps/desktop/assets/brand/adle-logo.png` |
| The same shapes as vectors | `apps/desktop/assets/brand/mark.svg` |
| In the interface | `Logo` (`@adle/design-system`), with or without the word "Adle" |
| App icons | `apps/desktop/assets/icons/` (`npm run icons`; do not edit by hand) |

- In the interface the "d" is `primary` and the "a" is `brand-ink`, so the mark follows the
  theme. Do not recolour it, outline it, tilt it, or put it on a busy background.
- Keep clear space of at least the width of one ring's stroke on every side.
- Smallest size: 20 px high. Below that the gap between the rings closes.
- The app icon is the mark on a rounded tile of the artwork's own backdrop (`#EEEEEE`).
- `npm run icons:verify` checks that the vectors still match the artwork.

## Scenes

Wanim scenes have a small palette of their own (`src/scene-palette.ts`, mirrored from the tokens
and listed in `skills/wanim-scene-authoring/SKILL.md`). Its `green` is the `success` green, not
the brand teal: inside a picture colours tell things apart, they do not carry the brand.

A lesson shows its pictures on a screen of its own, dark in either theme (`stage*`
tokens, which a test holds equal to the dark scene palette), and draws them with the dark
palette (ADR-035). The check in Settings still follows the theme, and every scene is run
in both, so both palettes stay true.

The stage, its ink, and its muted text are the `scene-*` tokens. The ink and the muted text
are **frozen**: their values are written into every scene file there is (the sample course, the
skill's examples, and lessons already generated on people's computers), so they did not move
when the interface around the stage was redesigned, and must not move without rewriting those
files. The background is in no file: the player supplies it, so it follows `surface`
(ADR-027). The interface's own `surface`, `ink`, and `muted` are free to change.

## Seeing it

`npm run e2e` writes a screenshot of every screen, in both themes and at the minimum window size,
to `apps/desktop/test-results/screens/`. That set is the current visual reference.

## Changing the system

1. Change tokens or components here first, never in a screen.
2. Add contrast pairs for new colours, on every ground they are used on; keep the dark theme
   complete.
3. Update this document and, for the accents scenes share, the scene skill. Leave the
   `scene-*` tokens alone.
4. Run `npm run check` and `npm run e2e`; look at the screenshots. A check for contrast waits
   for motion to finish (`settled` in `e2e/support/courses.ts`): something fading in has, for a
   moment, a colour nobody is meant to read.
