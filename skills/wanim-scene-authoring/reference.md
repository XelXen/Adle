# Wanim reference for Adle

Companion to [SKILL.md](SKILL.md). Facts about `@wanimjs/wanim` **0.1.3** as used by Adle.

- **Verified** = exercised in this repository against the pinned runtime (see the test named).
- **Documented upstream** = stated by Wanim's docs, not tested here.
- **Observed** = behaviour found while integrating that the upstream docs do not state, or state
  differently.

Upstream docs read on 2026-11-19: <https://wanim.org/llms.txt>, <https://wanim.org/docs/intro/>,
<https://wanim.org/docs/interactive/>, <https://wanim.org/docs/usage/>.

## 1. How a scene runs

1. Wanim preprocesses the Python source and strips the supported imports.
2. A patched RapydScript-ng compiler (`browser/rapydscript.js`, a classic script exposing a global)
   turns it into JavaScript.
3. The JavaScript is evaluated against Wanim's TypeScript port of manim and drawn on a 2D canvas,
   one frame at a time.

Nothing leaves the page, and there is no Python process, LaTeX toolchain, or video file.

**Observed.** The compiled code is run with `eval` inside a hidden, same-origin `about:blank`
iframe that the bridge creates and removes per run. Consequences for the host:

- The page needs `'unsafe-eval'` in its Content Security Policy.
- The page cannot have an opaque origin: under `sandbox="allow-scripts"` alone the bridge fails
  with *"Blocked a frame with origin "null" from accessing a cross-origin frame"*. Adle therefore
  gives each player frame its own real origin (see ADR-004).
- Scene code has the full power of JavaScript in that page. RapydScript's `v'...'` literal emits
  raw JavaScript, and undeclared Python names resolve to browser globals.
  (Test: `security.spec.ts` › "raw JavaScript in a scene still runs only inside the sandbox".)

## 2. Entry points Adle uses

| Import | Used for | Status |
|---|---|---|
| `@wanimjs/wanim/bridge` → `runPythonOnCanvas(source, canvas, options)` | Compile and play | Verified |
| `bridge.wanim.configure_fonts(urls)` | Point `Text` at local fonts | Verified |
| `bridge.wanim.preload_submodules('fonts')` | Parse fonts before the first scene | Verified |
| `@wanimjs/wanim/browser/rapydscript` | The compiler script, loaded once with a `<script>` tag | Verified |
| `<wanim-scene>` element, iframe embed player, share/notes HTTP API | Not used by Adle | Documented upstream |

**Observed.** `preload_fonts` appears in the 0.1.3 type definitions but is **not exported** by the
browser bundle. `preload_submodules('fonts')` is the working call.

### `runPythonOnCanvas` options

| Option | Adle passes | Notes |
|---|---|---|
| `quality` | `-ql` / `-qm` / `-qh` | 854×480, 1280×720, 1920×1080. The adapter asks for the one that suits the frame (`qualityForWidth`): under 640 pixels of the display wide the small one, over 1408 the large one. The browser scales the canvas to the frame, and shrunk by more than two a stroke one pixel thick is dropped, not thinned: a minus sign went missing from a formula (ADR-032). Verified: `scene-player.spec.ts` (26 small minus signs, all still there drawn 854 wide and shown 565 wide), `lesson.spec.ts` (a lesson's picture is drawn 854 wide). |
| `mode` | `'normal'` | Only interactive pages pause. `slides`, `two-view`, `animation` are documented upstream and unused. |
| `theme` | `'light'` / `'dark'` | Read by the scene as `self.theme` in `setup()`. Wanim never repaints for a theme change; Adle reloads the scene. Verified. |
| `background` | The Sprout surface colour | CSS hex override of the stage background. Verified. |
| `instanceId` | The run id | Attached to forwarded messages. |
| `realtime`, `fps` | `true`, `30` | `fps` is a target, not a guarantee. |
| `sceneName` | Optional | Run one class when a file defines several. |
| `signal` | An `AbortSignal` | Stops the run at the next frame boundary. Verified (dispose). |
| `onScene(name)` | — | The class name. Fires **after** `onSceneReady`. Observed. |
| `onSceneReady(scene)` | — | The scene instance, **before** `blueprint()` has run. Observed. |
| `onController(controller)` | — | `next()`, `previous()`, `replay()`, `restart()`, `abort()`, and a `state` getter. |
| `onMessage(message)` | — | `{ id, key, value, scene, sceneIndex, pageIndex, phaseKind }` for each `post_message`. Verified. |
| `preload` | default `'auto'` | Scans the source for MathJax and font use. |

**Observed.** `onStateChange` exists on the lower-level `render_presentation_to_canvas` but is not
forwarded by `runPythonOnCanvas`. Adle polls `controller.state` once per animation frame instead.

### Presentation state (`controller.state`)

`sceneName`, `sceneIndex`, `sceneCount`, `phaseIndex`, `phaseCount`, `phaseKind`
(`'blueprint' | 'construct'`), `slidesMode`, `done`, `canNext`, `canPrevious`, `canReplay`.

**Observed.** On a scene whose last page is a `blueprint()`, `canNext` is `false` and the run never
finishes: the scene stays live. Adle therefore reports two separate facts to the lesson:
`interactive` (a live page is showing) and `canNext` (another page follows).

## 3. What Wanim does not provide, and how Adle supplies it

| Need | Wanim | Adle |
|---|---|---|
| Pause / resume mid-animation | No API. Frames are paced on `requestAnimationFrame`. | The player gates `requestAnimationFrame`: held while paused, released on resume. Animations advance a fixed step per logical frame, so there is no jump. Verified: `scene-player.spec.ts` (identical screenshots 1.2 s apart while paused). |
| Hold on the first frame | — | Start with the gate closed (`autoplay: false`). Verified. |
| Run a scene through fast, to try it before it is shown (ADR-038) | No API. Its scheduler draws the next frame only once `performance.now()` says a frame's interval has passed, and a frozen `wait` lasts until `performance.now()` says its seconds have. | A load with `rehearsal: true`: the gate hands frames out as fast as they are asked for, the frame's `performance.now()` runs 25 times as fast (`time-warp.ts`), and the scene is drawn small. Messages are the same as at a learner's pace. Verified: `scene-player.spec.ts` (a sample scene in under a quarter of its time, the same messages); the sample scenes take 0.3 to 1 s against 14 to 17 s. |
| Restart | `controller.restart()` | Adle reloads the source instead: one code path, always a clean state. |
| Host sets a control value | `control.set_value(v)` is silent | Adle calls `set_value(v)` then `notify_input(previous, next)` so the scene's `on_input` listeners run as for a gesture. Verified. |
| Enumerate a scene's controls | — | Convention: `self.adle_controls = {...}`, read by the player after `blueprint()` runs. Verified. |
| Liveness | — | Host `ping` / player `pong`; five seconds of silence means the scene is stuck. Verified. |
| Navigation buttons | Draws `<`, `↻`, `>` over the canvas | Hidden with CSS (`[data-wanim-action]`); Adle's lesson shell owns navigation. |

## 4. Fonts and maths

- **Fonts.** `Text` is rendered from font outlines parsed by opentype.js, which reads TTF, OTF, and
  WOFF1 (**not WOFF2**). Wanim's default font chain is fetched from a public CDN (jsDelivr). Adle
  replaces it with local files copied from `@fontsource/inter` at build time
  (`inter-latin-400`, `inter-latin-ext-400`, `inter-greek-400`, all WOFF1, OFL-1.1). The first font
  in the chain that has a glyph wins. Verified offline: the session refuses every non-`adle:` request.
- **Glyph coverage.** Latin, Latin Extended, Greek. No arrows, no mathematical operators, no CJK.
  Use `MathTex` for symbols.
- **Maths.** MathJax, bundled as a lazily loaded chunk (about 2 MB). Standard TeX maths only.
  `DecimalNumber` digits are also typeset by MathJax.

## 5. Scene API notes

Write ordinary manim Community v0.21 Python. Only the Wanim-specific parts are listed here.

### Verified in the examples

`Scene`, `InteractiveScene`, `setup`, `blueprint`, `construct`, `self.theme`, `self.add`,
`self.play`, `self.wait`, `self.post_message`; `Text`, `MathTex`, `DecimalNumber`; `Circle`,
`Rectangle`, `Line`, `Dot`, `VGroup`; `Axes`, `Axes.plot`, `Axes.c2p`; `ValueTracker`,
`always_redraw`, `.animate`; `Write`, `Create`, `FadeIn`, `GrowFromCenter`; `Slider`, `Switch`;
`add_reaction`, `on_input`; positioning with `to_edge`, `next_to`, `move_to`, `shift`, `arrange`;
`set_value`, `set_color`, `set_width`, `stretch_to_fit_height`; `np.exp`; and from
`examples/sum_to_output.py`: `Arrow`, `LaggedStart`, `GrowArrow`, `Indicate`,
`TransformMatchingTex` (on `MathTex` split into parts), `SurroundingRectangle`, `FadeOut`,
`FadeIn(..., shift=...)`, `formula[i].set_color(...)`.

### Verified by a test of its own

- `set_stroke(opacity=...)` shows and hides a plotted curve and leaves it a line.
  `set_opacity(1)` on the same curve fills the area between it and the straight line joining
  its ends (`e2e/fixtures/scenes/curve_stroke.py` and `curve_opacity.py`, read back pixel by
  pixel in `e2e/scene-player.spec.ts`). Found in the first interactive scene a real model
  wrote for Adle, 2026-11-20.
- `set_fill(colour, opacity)` given in order fills a shape; `set_fill(colour, opacity=...)`
  runs and leaves it with no fill; `set_fill(opacity=...)` and `set_color(color=...)` stop
  the scene (`e2e/fixtures/scenes/fill_in_order.py`, `fill_by_name.py` and
  `fill_without_colour.py`, read back pixel by pixel in `e2e/scene-player.spec.ts`). Found
  by sitting a lesson a real model wrote, 2026-11-21: its interactive picture never ran.
- **Slides (ADR-049)**, every example in `e2e/fixtures/slides/` stepped through in both themes
  by `e2e/slide-player.spec.ts`, 2026-11-22:
  - `self.set_storyboard([[None, self.step_0], [None, self.step_1], ..., [self.blueprint,
    None]])`, called in `setup()`, plays the phases in order, and what a phase drew stays for
    the next. A scene that never defines `blueprint` has no page prepended for it.
  - Loaded with `pacing: 'cued'` (Wanim's `slides` mode) the scene holds after every phase,
    the last too, and says nothing more there (no `finished`). `next` plays the next phase.
    `next` while a phase is still playing cuts that phase short: a host says `next` only
    after the phase's own `post_message("step", n)`.
  - A blueprint page that comes after construct phases is live: its controls work, and
    `mobject.update(0)` runs an `always_redraw` mobject's updater there (updaters do not run
    by themselves on a live page; reactions do).
  - `MathTex` takes `\color{#E9BE5A}{...}` and `\color{yellow}` inside a formula; parts given
    as separate strings (or cut at `{{ }}`) can each be colored or pointed at (`formula[i]`).
    `MathTex(*words, arg_separator="\\ ")` of `\text{...}` parts sets a sentence on one
    baseline with each word a part.
  - TeX is drawn about two thirds the size of text at one font size: a formula, a
    `DecimalNumber` or words set in TeX beside `Text` need about 1.45 times the size.
  - `Circle(radius=1).stretch_to_fit_width(w).stretch_to_fit_height(h)` draws an oval;
    `RoundedRectangle`, `SurroundingRectangle(..., corner_radius=...)`, `Brace` (and
    `next_to` a label beside it), `CurvedArrow`, `DashedLine`, `Polygon`, `Square`,
    `NumberLine(...).n2p`, `arrange_in_grid(rows=..., cols=...)`, `Rotate(m, angle=...)`,
    `mobject.become(other)`, `ChangeDecimalToValue`, `FadeTransform`, `ReplacementTransform`,
    `Transform` and `copy()` all run.
  - **`Ellipse(width=..., height=...)` and `Flash(...)` stop the scene** ("non-finite point
    or vector value"). The scene policy refuses both.
- **A formula made of the picture (ADR-050)**, `e2e/fixtures/slides/prompt_example.py` and
  `counted_out.py` stepped through in both themes by `e2e/slide-player.spec.ts`, and looked
  at, 2026-11-22: `self.play(TransformFromCopy(source, formula[i]), ...,
  FadeIn(formula[j]), ...)` turns a copy of each source (a brace's label, a whole set as a
  `VGroup`) into a part of a `MathTex`, the source staying; then
  `self.remove(*formula.submobjects)` and `self.add(formula)` leave the formula one thing on
  the stage, drawn once, and a later `TransformMatchingTex(formula, other)` turns all of it
  into the other with no copy left behind. `TransformMatchingTex(sentence.copy(), other)`
  (sentences as `\text{...}` parts) and the same of formulas move what the two share and
  leave the first where it was (`rewritten.py`).

- **A picture that looks at its own words (ADR-055)**, every example in `e2e/fixtures/slides/`
  and `e2e/fixtures/figures/` run in both themes by `e2e/slide-player.spec.ts` and
  `e2e/scene-player.spec.ts`, 2026-11-23: `isinstance(m, Text)`,
  `isinstance(m, SingleStringMathTex)` (true of a `MathTex`) and `isinstance(m, DecimalNumber)`
  tell a word from a drawing, and `isinstance(m, Line)` (an arrow and an axis's line among
  them) and `isinstance(m, ParametricFunction)` (a plotted curve) a line; `get_anchors()`
  gives a line's path, point by point, each indexed `[0]` and `[1]` (ADR-056); `m.submobjects` and `self.mobjects` (what is on the stage) can
  be walked; `a is b`; `for key in a_dict`, `key not in a_list` and `a_dict.get(key, default)`;
  `get_left()`, `get_right()`, `get_top()` and `get_bottom()` of a word or a group, by
  index; `next_to` called again moves a label to another side of a mobject or a point, also
  inside an `always_redraw` function, which may keep a choice in an attribute of the scene.
  A word's box is the box of what is drawn, so letters set side by side touch and do not
  overlap. A scene's own method may be replaced by setting an attribute of the same name
  (`self.lines = []` made `self.lines(...)` fail with no message): give state names no
  method has.

- **What the pictures of other subjects are drawn with (ADR-061)**, the examples `code.py`,
  `vessels.py`, `molecules.py`, `timeline.py`, `causes.py`, `list_sorted.py` and `forces.py`
  in `e2e/fixtures/slides/`, stepped through by `e2e/slide-player.spec.ts` and looked at,
  2026-11-24:
  - **`Text` has one face.** `Text(..., font="monospace")` is drawn in the same face as any
    other text: the font chain the player is given is the only one there is. Code is set in
    it, and keeps every character.
  - **`Paragraph(*lines, font_size=..., line_spacing=...)`** lays lines out on their own
    baselines, keeps the spaces a line begins with, and gives each line's glyphs as
    `paragraph.chars[i]`. A `Text` of one line's words moved to `chars[i].get_center()`
    stands where that line stood.
  - **`ArcBetweenPoints(start, end, bend)`** draws an arc when the bend is given by place.
    **Given by name (`angle=bend`) it stops the scene** ("non-finite point or vector
    value"), as does `radius=`; `CurvedArrow(start, end, angle=bend)` runs either way.
  - `Polygon(*points, color=..., fill_opacity=..., stroke_width=0)` for a filled shape with
    no outline, a `Transform` of one such polygon into another of other corners (a liquid
    rising), and of a `Text(" ")` into a `MathTex` (an empty cell filled) all run.
  - `DIRECTION * number` held in a variable (`way = RIGHT`, then `point + way * 1.5`) adds
    as a vector; `n % 4` and a list indexed by it run.

### Documented upstream, not yet exercised here

`PathSlider`, `DraggablePoint`, `Chip`, `InputDecimalNumber`, `InputInteger`,
`InputDecimalMatrix`, `InputDecimalTable`; `self.add_reaction` (scene-level); `SEPARATE = True`;
`self.clear_stage()`; `set_script` (the same as `set_storyboard`); `self.next_slide()` (not in the pinned version);
`InteractiveThreeDScene`; `InteractiveLinearTransformationScene`.

Rules that come with the interactive API (documented upstream):

- `blueprint()` runs once; reactions then run every frame while the page is live.
- Reactions stop when `construct()` starts.
- `on_input(listener)` receives `(control, previous, next_value)` and fires only for reader
  gestures (and Adle's host-set values). `set_value` from scene code is silent.
- Do not put a control inside a group that is later moved or scaled.

### Known gaps and failure modes (verified)

| Source does this | Result | Stage |
|---|---|---|
| Invalid indentation or syntax | Message with file position | `compile` |
| `import os` (or any other module) | "cannot use Python module 'os'" with guidance | `compile` |
| No `Scene` subclass | "No Scene subclass found in the code." | `compile` |
| Exception during `construct()` | The JavaScript error message | `runtime` |
| `ImageMobject("x.png")` | "could not find x.png" | `runtime` |
| `while True:` without `self.wait` | The frame stops answering; watchdog fires | `unresponsive` |
| `set_fill(opacity=...)`, `set_fill(color=..., opacity=...)`, `set_color(color=...)` (no argument in first place) | "ManimColor only accepts int, str, ... not Object". The names are taken for the colour. The static policy rejects these forms. | `runtime` |
| `set_fill(colour, opacity=...)` (the opacity by name) | No error. The shape is left with no fill. Use `set_fill(colour, 0.3)`, or `set_fill(None, 0.3)` to keep the colour. The static policy rejects the named form. | none |
| `Circumscribe(..., color=...)` | "shape should be either Rectangle or Circle." The name is taken for the shape and the scene stops. Without a colour it runs, drawn in a yellow outside the palette. The static policy rejects both (`e2e/fixtures/scenes/circumscribe.py`). | `runtime` |
| `Indicate(..., color=...)` | "non-finite point/vector value (NaN/Infinity)." The scene stops. Without a colour it runs. The static policy rejects the colour (`e2e/fixtures/scenes/indicate_colour.py`). **Observed** 2026-11-22, in a figure. | `runtime` |
| `Dot(point, color=...)` (position as an argument) | No error. The dot is drawn white: invisible on the light stage. Use `Dot(color=..., radius=...).move_to(point)`. The static policy rejects the first form. **Observed** in the sample scenes' screenshots. | none |

Scenes and mobjects are JavaScript `Proxy` objects that throw an `AttributeError` for unknown
**string** attributes, so reading a missing attribute from the host is an exception, not `undefined`.

## 6. Timing baseline

Measured on the development machine (Windows 11, Electron 45.4.1), `-qm`, development build:

| Measure | Value |
|---|---|
| Player frame boot (document + runtime + fonts) | about 160–240 ms |
| Compile and construct a simple scene | about 290 ms |
| First frame after `load` | about 340 ms |

These are one machine's observations, not a guarantee. Re-measure for the release performance
report (M8).

## 7. Licences

| Component | Licence |
|---|---|
| `@wanimjs/wanim` | MIT |
| `numpy-ts` | MIT |
| `mathjax-full` | Apache-2.0 |
| `opentype.js` | MIT |
| Inter (via `@fontsource/inter`) | OFL-1.1 |
