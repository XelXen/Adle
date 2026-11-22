<!-- GENERATED FILE: do not edit. Source: skills/wanim-scene-authoring. Regenerate with `npm run scene-guide`. -->

# Writing a Wanim scene for Adle

## The one-file rule

A scene is produced by **one request that returns one complete `.py` file**: imports, one scene
class, every helper it needs. Never fragments, patches, or continuations. If a scene does not fit
comfortably in one response, the scene is too ambitious; make it smaller.

## Anatomy of a scene

```python
from manim import *


class NeuronWeight(InteractiveScene):
    """One sentence: what the learner sees and does."""

    def setup(self):
        # 1. Colours. Always derive them from the theme; never set a background.
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"

    def blueprint(self):
        # 2. The live page: build the picture and its controls once.
        weight = Slider(start=[-5, -2.7, 0], end=[0.5, -2.7, 0],
                        value_range=(-2, 2), init_value=0.5, color=self.green)
        # 3. Name the controls so Adle can mirror them as accessible inputs.
        self.adle_controls = {"weight": weight}

        bar = Rectangle(width=1.2, height=1.0, color=self.blue, fill_opacity=0.55)
        # 4. Reactions keep the picture in sync. Update existing objects; create nothing.
        bar.add_reaction(lambda m: m.stretch_to_fit_height(max(0.04, abs(weight.get_value()))))

        # 5. Tell the host what the learner did, using the closed event vocabulary.
        weight.on_input(lambda control, previous, value: self.post_message("explored", True))
        self.add(bar, weight)

    def construct(self):
        # 6. The animation that plays after the learner continues.
        note = Text("A larger weight makes this input matter more.", font_size=30, color=self.ink)
        self.play(FadeIn(note.to_edge(DOWN, buff=0.4)), run_time=0.8)
        self.wait(0.6)
```

- **Animation only?** Subclass `Scene` and write just `construct()`.
- **Interaction only?** Subclass `InteractiveScene` and write just `blueprint()`. The scene then
  stays interactive until the lesson moves on.
- **Both?** The `blueprint()` page shows first and waits; `construct()` plays when the learner
  continues.
- **Never override `__init__`.** Put setup in `setup()`, `blueprint()`, or `construct()`.

## Adle conventions (required)

### Colour

Scenes cannot read CSS, so they pick colours from `self.theme` in `setup()`. Use only this palette.
It mirrors the Sprout design tokens (`green` is the success green, not the app's teal accent);
`packages/design-system/src/tokens.test.ts` fails if the two drift apart.

| Name | Light | Dark | Use |
|---|---|---|---|
| `ink` | `#17251E` | `#E7EFE9` | Primary text and formulas |
| `muted` | `#5F6E65` | `#9DB0A5` | Labels, axes, secondary lines |
| `green` | `#269B62` | `#3DBE7F` | The main subject, controls |
| `blue` | `#5B8DE6` | `#7BA4EE` | Data, inputs, positive values |
| `coral` | `#EF806C` | `#F08F7D` | Contrast, negative values, the point of attention |
| `sun` | `#F2C14E` | `#E9BE5A` | Highlight (shapes only, never text) |
| `violet` | `#9178D7` | `#A694E3` | A second series |

**Never set the background.** The player supplies it (`#FFFFFF` light, `#141414` dark). Do not
use colour as the only carrier of meaning: pair it with position, a label, or a sign.

### Layout

- The stage is 16:9 and about **14.2 × 8** world units, origin at the centre.
- Keep everything inside the safe area: `|x| ≤ 6.3`, `|y| ≤ 3.5`.
- **Title** at the top: `Text(..., font_size=30–36).to_edge(UP, buff=0.5)`.
- **Controls** in a band at the bottom, around `y = -2.7`, each with a `Text` label
  (`font_size=24–26`, `muted`) placed with `next_to(control, UP, buff=0.3)`.
- **Body text and labels** `font_size=24–32`; **formulas** `MathTex(..., font_size=40–48)`;
  **key numbers** `DecimalNumber(..., font_size=40–56)`.
- **No `MathTex` below `font_size=32`**, not even a small label. A lesson shows the picture
  at under half the size it is drawn, and a formula's thin strokes (a minus sign, the bars
  of an equals sign) are the first thing to fade.
- At most about seven distinct visual elements. If it needs a legend, it is too dense.
- **A `Dot` is created with keywords and then placed:**
  `Dot(color=self.coral, radius=0.12).move_to(point)`. Given its position as an argument
  (`Dot(point, color=...)`), a dot loses its colour in this runtime and is drawn white, which
  cannot be seen on the light stage. The static policy rejects that form.
- **`set_fill` and `set_color` take their arguments in order, without names:**
  `box.set_fill(self.blue, 0.3)`, `label.set_color(self.ink)`. To change only how solid a
  fill is, keep its colour with `None`: `box.set_fill(None, 0.3)`. Written with names they
  go wrong in this runtime: `set_fill(opacity=0.3)` and `set_color(color=...)` stop the
  scene with an error, and `set_fill(self.blue, opacity=0.3)` runs and leaves the shape with
  no fill at all. **Verified.** The static policy rejects every named form. (`set_stroke` and
  the shapes' own `fill_opacity=` are fine with names.)
- Words and numbers are drawn in `ink` or `muted`. The accent colours are for shapes: as text
  they are too pale to read on the light stage.

### Text and maths

- `Text` is for prose; `MathTex` is for anything mathematical. `Text` is drawn with Inter and has
  Latin, Latin Extended, and Greek glyphs only. Put symbols (→, ≤, ∑, ×, ∂) in `MathTex`.
- Math is typeset by MathJax: standard TeX math only, no `\usepackage`.
- Fractions shrink in inline style. Use `\dfrac{...}{...}` or a larger `font_size`.
- Always use raw strings for TeX: `MathTex(r"\sigma(z)")`.

### Controls and accessibility

Register every learning-relevant control by a short snake_case name:

```python
self.adle_controls = {"weight": weight_slider, "bias_on": bias_switch}
```

Adle mirrors these as native sliders and switches below the scene, so the interaction works with
a keyboard or a screen reader. Supported for mirroring: `Slider`, `PathSlider` (must have a
`value_range`), `Switch`, `Chip`, and `InputDecimalNumber` with a `value_range`. At most 16.

- Put controls directly on the stage (`self.add(...)`), never inside a group that moves or scales.
- A value set from the host triggers the control's `on_input` listeners, exactly like a drag.
- The scene must still make sense if the learner never touches a control: the initial state
  should already show the idea, and the narration and text fallback carry it too.

### Events

`self.post_message(name, value)` reports to the lesson. The vocabulary is **closed**; anything else
is silently dropped twice (by the player and by the host).

| Name | Value | Meaning |
|---|---|---|
| `explored` | `True` | The learner changed a control at least once. Send once. |
| `progress` | number 0–1 | How far through an in-scene task the learner is. |
| `passed` | `True` | The learner reached the scene's stated goal. Send once. |

Values must be a boolean, a finite number, a string of at most 200 characters, or `None`. Events are
weak evidence of engagement, never proof of understanding; the lesson's questions decide that.

### Motion: draw the idea happening

A lesson is watched (ADR-035): while its words are said, the picture is most of what the
learner looks at. Draw the idea happening, the way a good mathematics video does, and not a
slide with things fading in. **Verified:** every tool named here runs in the pinned runtime
(`examples/sum_to_output.py`).

- **Follow the narration, a step for each sentence.** Build the picture in the order the
  narration says it. Pace it to the narration, which is read at about two and a half words a
  second: an animation where something happens, a `self.wait(...)` where the voice explains
  what is already on screen. The whole scene lasts about as long as the narration, 8 to 40
  seconds, and ends on a frame that holds the idea.
- **Show change as change.** When one thing becomes another, transform it: `Transform` or
  `ReplacementTransform` for a shape, `TransformMatchingTex` for an equation that is rewritten
  (split the `MathTex` into the parts that move, `MathTex("z", "=", "w_1", "x_1", ...)`, and
  keep the same pieces in the next one), `TransformFromCopy` to show where a term comes from.
  Never fade one formula out and the next in.
- **Let a value move, and everything that depends on it with it.** A `ValueTracker` animated
  with `self.play(tracker.animate.set_value(...))`, and the shapes and numbers that depend on
  it rebuilt by `always_redraw(lambda: ...)`, show cause and effect in one motion.
- **One colour, one meaning.** A quantity keeps its colour everywhere it appears: the input
  dots and the `x` in the formula are both `blue`, the weights `green`. Colour the parts of a
  `MathTex` with `formula[i].set_color(...)`. Words stay `ink` or `muted`.
- **Point at what the narration names**: `Indicate(...)` on the part in the picture and the
  symbol in the formula together, or a `SurroundingRectangle(..., color=self.sun)` drawn with
  `Create` and taken away with `FadeOut`. (`Circumscribe`, and `Indicate` given a colour, stop the scene in this runtime; the static policy refuses both.)
  `LaggedStart(...)` for things that arrive together; `GrowArrow`, `GrowFromCenter`, `Create`
  for lines and shapes, `Write` for formulas, `FadeIn(..., shift=...)` for labels.
- **Keep the stage clear.** At most about seven things at once; `FadeOut` what the narration
  has finished with. Little text: a label, not a sentence (the words are said).
- `run_time` 0.6–2.5 s for each animation. No flashing, strobing, shaking, or rapid colour
  cycling. No decorative movement.

## Performance rules for reactions

Reactions run **every frame** while a `blueprint()` page is live.

- Create objects once, outside the reaction. Inside it, only update: `set_value`, `move_to`,
  `set_color`, `set_width`, `stretch_to_fit_height`, `become`.
- **Never construct `Text`, `MathTex`, or `Matrix` inside a reaction.** For a changing number use
  one `DecimalNumber` and `set_value(...)`.
- Reactions do not run during `construct()`. Use `add_updater`, `ValueTracker`, and
  `always_redraw` there.
- **Show or hide a curve by its stroke.** For anything drawn as a line (`Axes.plot`, `Line`,
  an arc, any open path) use `curve.set_stroke(opacity=1)` and `curve.set_stroke(opacity=0)`.
  `set_opacity(...)` also sets the fill, and a filled curve is painted solid between its two
  ends. **Verified.** `set_opacity` is right for `Text`, `MathTex`, `Dot`, and filled shapes.

## Prohibited (enforced)

A scene is untrusted, executable content. The static policy in the core rejects files that break
these rules, and the player's sandbox contains whatever gets through.

- Imports other than `manim`, `numpy`, `math`, `random`, `itertools`.
- Any name that is not defined in the file, a Python builtin on the allowlist, or part of the
  manim/numpy namespace. In particular no browser globals: `window`, `document`, `fetch`,
  `XMLHttpRequest`, `localStorage`, `globalThis`, `eval`, `Function`, `setTimeout`, `navigator`.
- Attribute tricks: `constructor`, `__proto__`, `prototype`, `__class__`, `getattr`/`setattr`.
- RapydScript's raw-JavaScript literal (`v'...'`). It is not valid Python and is rejected.
- Files, URLs, images, sound, SVG assets (`ImageMobject`, `SVGMobject`, `add_sound`): there is
  nothing to load them from.
- Wanim's share and notes APIs (`/api/save`, `/api/notes`). Adle is local-first; nothing is uploaded.
- 3D scenes, `ZoomedScene`, `MovingCameraScene`, and `InteractiveLinearTransformationScene`: not
  tested here. Use `Scene`/`InteractiveScene` with `Axes` or `NumberPlane`.
- Loops that never yield (`while True:` without `self.wait`). The watchdog will kill the scene
  after five seconds and the learner gets the text fallback.

## Complete examples

Each of these files runs in Adle exactly as shown.

### weighted_sum.py

An animation-only scene: shapes, text, a formula, simple animations.

```python
from manim import *


class WeightedSum(Scene):
    """Animation-only scene: introduces the weighted sum a neuron computes."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"

    def construct(self):
        title = Text("A neuron adds up weighted inputs", font_size=36, color=self.ink)
        title.to_edge(UP, buff=0.7)

        inputs = VGroup(
            Circle(radius=0.35, color=self.blue, fill_opacity=0.25),
            Circle(radius=0.35, color=self.blue, fill_opacity=0.25),
        ).arrange(DOWN, buff=1.2).shift(LEFT * 4)
        neuron = Circle(radius=0.6, color=self.green, fill_opacity=0.25)
        wires = VGroup(*[Line(dot.get_right(), neuron.get_left(), color=self.muted) for dot in inputs])

        formula = MathTex(r"z = w_1 x_1 + w_2 x_2 + b", font_size=44, color=self.ink)
        formula.to_edge(DOWN, buff=0.9)

        self.play(Write(title), run_time=0.8)
        self.play(FadeIn(inputs), Create(wires), GrowFromCenter(neuron), run_time=1.0)
        self.play(Write(formula), run_time=1.0)
        self.wait(0.4)
```

### neuron_weight.py

An interactive scene: a slider and a switch, reactions, events, named controls.

```python
from manim import *


class NeuronWeight(InteractiveScene):
    """Interactive scene: the learner changes one weight and toggles the bias."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"

    def blueprint(self):
        self.state = {"explored": False, "passed": False}

        weight = Slider(
            start=[-5, -2.7, 0],
            end=[0.5, -2.7, 0],
            value_range=(-2, 2),
            init_value=0.5,
            color=self.green,
        )
        bias_on = Switch(False).move_to([3.2, -2.7, 0])
        # Named controls are mirrored to the Adle host for keyboard/screen-reader access.
        self.adle_controls = {"weight": weight, "bias_on": bias_on}

        weight_label = Text("weight w", font_size=26, color=self.muted).next_to(weight, UP, buff=0.3)
        bias_label = Text("add bias 0.5", font_size=26, color=self.muted).next_to(bias_on, UP, buff=0.3)

        title = Text("Output z = w * x + b   (x = 1)", font_size=32, color=self.ink).to_edge(UP, buff=0.6)
        readout = DecimalNumber(0.5, num_decimal_places=2, font_size=56, color=self.ink)
        readout.move_to([3.2, 0.6, 0])

        baseline = Line([-4, -1.2, 0], [0, -1.2, 0], color=self.muted)
        bar = Rectangle(width=1.2, height=1.0, color=self.blue, fill_opacity=0.55)

        def output():
            return weight.get_value() + (0.5 if bias_on.get_value() else 0.0)

        def draw_bar(m):
            z = output()
            m.stretch_to_fit_height(max(0.04, abs(z)))
            m.set_color(self.blue if z >= 0 else self.coral)
            m.move_to([-2, -1.2 + z / 2, 0])

        bar.add_reaction(draw_bar)
        readout.add_reaction(lambda m: m.set_value(output()))

        def on_change(control, previous, next_value):
            if not self.state["explored"]:
                self.state["explored"] = True
                self.post_message("explored", True)
            if output() >= 2.0 and not self.state["passed"]:
                self.state["passed"] = True
                self.post_message("passed", True)

        weight.on_input(on_change)
        bias_on.on_input(on_change)

        self.add(title, baseline, bar, readout, weight, bias_on, weight_label, bias_label)

    def construct(self):
        note = Text("A larger weight makes this input matter more.", font_size=30, color=self.ink)
        note.to_edge(DOWN, buff=0.4)
        self.play(FadeIn(note), run_time=0.8)
        self.wait(0.6)
```

### activation_curve.py

Axes with a plotted curve and a point that moves along it.

```python
from manim import *


class ActivationCurve(InteractiveScene):
    """Interactive graph: slide the input z and read the sigmoid output off the curve."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"

    def sigmoid(self, z):
        return 1 / (1 + np.exp(-z))

    def blueprint(self):
        self.state = {"explored": False}

        axes = Axes(
            x_range=[-6, 6, 2],
            y_range=[0, 1, 0.5],
            x_length=8,
            y_length=3.2,
            axis_config={"color": self.muted, "include_tip": False},
        ).shift(UP * 0.5)
        curve = axes.plot(lambda z: self.sigmoid(z), x_range=[-6, 6], color=self.blue)
        title = Text("Sigmoid squashes any input into 0 to 1", font_size=30, color=self.ink)
        title.to_edge(UP, buff=0.45)
        formula = MathTex(r"\sigma(z) = \frac{1}{1 + e^{-z}}", font_size=34, color=self.ink)
        formula.move_to(axes.c2p(-3.6, 0.82))

        z_input = Slider(
            start=[-4, -2.9, 0],
            end=[4, -2.9, 0],
            value_range=(-6, 6),
            init_value=0,
            color=self.green,
        )
        self.adle_controls = {"z": z_input}
        z_label = Text("input z", font_size=24, color=self.muted).next_to(z_input, UP, buff=0.25)

        dot = Dot(color=self.coral, radius=0.1)
        dot.add_reaction(lambda m: m.move_to(axes.c2p(z_input.get_value(), self.sigmoid(z_input.get_value()))))
        readout = DecimalNumber(0.5, num_decimal_places=2, font_size=40, color=self.ink)
        readout.move_to(axes.c2p(4.4, 0.25))
        readout.add_reaction(lambda m: m.set_value(self.sigmoid(z_input.get_value())))
        readout_label = Text("output", font_size=22, color=self.muted).next_to(readout, UP, buff=0.2)

        def on_change(control, previous, next_value):
            if not self.state["explored"]:
                self.state["explored"] = True
                self.post_message("explored", True)

        z_input.on_input(on_change)
        self.add(axes, curve, title, formula, dot, readout, readout_label, z_input, z_label)

    def construct(self):
        tracker = ValueTracker(-6)
        axes = Axes(
            x_range=[-6, 6, 2],
            y_range=[0, 1, 0.5],
            x_length=8,
            y_length=3.2,
            axis_config={"color": self.muted, "include_tip": False},
        ).shift(UP * 0.5)
        sweep = always_redraw(
            lambda: Dot(color=self.green, radius=0.12).move_to(
                axes.c2p(tracker.get_value(), self.sigmoid(tracker.get_value()))
            )
        )
        note = Text("Large negative inputs give 0; large positive inputs give 1.", font_size=26, color=self.ink)
        note.to_edge(DOWN, buff=0.5)
        self.add(sweep)
        self.play(FadeIn(note), run_time=0.6)
        self.play(tracker.animate.set_value(6), run_time=2.0, rate_func=smooth)
        self.wait(0.4)
```

### sum_to_output.py

The style to aim for: a step for each sentence of narration, colours that keep their meaning, an equation rewritten with TransformMatchingTex, and a value that moves the picture.

```python
from manim import *


class SumToOutput(Scene):
    """Animation-only scene: a neuron's inputs become one number, step by step with the
    narration; each symbol keeps the colour of the thing it stands for."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"
        self.sun = "#E9BE5A" if dark else "#F2C14E"

    def construct(self):
        # 1. The picture: two inputs, two connections, one neuron.
        neuron = Circle(radius=0.55, color=self.ink).move_to([1.6, 1.0, 0])
        tops = [[-3.6, 2.0, 0], [-3.6, 0.0, 0]]
        inputs = VGroup(*[Dot(color=self.blue, radius=0.14).move_to(point) for point in tops])
        input_labels = VGroup(
            MathTex("x_1 = 2", font_size=36, color=self.ink).next_to(inputs[0], LEFT, buff=0.3),
            MathTex("x_2 = 1", font_size=36, color=self.ink).next_to(inputs[1], LEFT, buff=0.3),
        )
        links = VGroup(
            *[
                Arrow(dot.get_center(), neuron.get_left(), buff=0.18, color=self.green)
                for dot in inputs
            ]
        )
        weight_labels = VGroup(
            MathTex("w_1 = 0.5", font_size=34, color=self.ink).next_to(links[0], UP, buff=0.1),
            MathTex("w_2 = -1", font_size=34, color=self.ink).next_to(links[1], DOWN, buff=0.1),
        )
        self.play(
            LaggedStart(*[GrowFromCenter(dot) for dot in inputs], lag_ratio=0.3), run_time=1.0
        )
        self.play(FadeIn(input_labels, shift=RIGHT * 0.2), run_time=0.8)
        self.wait(1.2)
        self.play(LaggedStart(*[GrowArrow(link) for link in links], lag_ratio=0.3), run_time=1.0)
        self.play(FadeIn(weight_labels), Create(neuron), run_time=0.9)
        self.wait(1.5)

        # 2. The rule, each symbol in the colour of what it stands for.
        rule = MathTex("z", "=", "w_1", "x_1", "+", "w_2", "x_2", "+", "b", font_size=44)
        rule.move_to([0, -1.7, 0])
        rule.set_color(self.ink)
        for index in (2, 5):
            rule[index].set_color(self.green)
        for index in (3, 6):
            rule[index].set_color(self.blue)
        rule[8].set_color(self.coral)
        self.play(Write(rule), run_time=1.4)
        self.wait(1.0)
        # Each product, pointed out where it is in the picture.
        self.play(Indicate(rule[2]), Indicate(links[0]), run_time=0.9)
        self.play(Indicate(rule[3]), Indicate(inputs[0]), run_time=0.9)
        self.wait(1.0)

        # 3. The same rule with the numbers in it, and then what it comes to.
        numbers = MathTex("z", "=", "(0.5)", "(2)", "+", "(-1)", "(1)", "+", "0.5", font_size=44)
        numbers.move_to(rule)
        numbers.set_color(self.ink)
        for index in (2, 5):
            numbers[index].set_color(self.green)
        for index in (3, 6):
            numbers[index].set_color(self.blue)
        numbers[8].set_color(self.coral)
        self.play(TransformMatchingTex(rule, numbers), run_time=1.4)
        self.wait(1.2)
        result = MathTex("z", "=", "0.5", font_size=52, color=self.ink).move_to(numbers)
        self.play(TransformMatchingTex(numbers, result), run_time=1.2)
        frame = SurroundingRectangle(result, color=self.sun, buff=0.18)
        self.play(Create(frame), run_time=0.7)
        self.play(FadeOut(frame), run_time=0.5)
        self.wait(1.0)

        # 4. Turn one weight up and watch the sum follow it.
        weight = ValueTracker(0.5)
        live = always_redraw(
            lambda: DecimalNumber(
                weight.get_value() * 2 - 1 + 0.5,
                num_decimal_places=1,
                font_size=52,
                color=self.ink,
            ).next_to(result[1], RIGHT, buff=0.25)
        )
        label = always_redraw(
            lambda: MathTex(
                "w_1 = " + f"{weight.get_value():.1f}", font_size=34, color=self.ink
            ).next_to(links[0], UP, buff=0.1)
        )
        self.play(FadeOut(result[2]), FadeOut(weight_labels[0]), run_time=0.4)
        self.add(live, label)
        glow = always_redraw(
            lambda: Circle(
                radius=0.55 + 0.12 * weight.get_value(), color=self.sun, stroke_width=3
            ).move_to(neuron)
        )
        self.add(glow)
        self.play(weight.animate.set_value(2.0), run_time=2.5)
        self.wait(0.8)
        self.play(weight.animate.set_value(0.5), run_time=1.5)
        self.wait(1.0)
```
