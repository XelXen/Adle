---
name: wanim-scene-authoring
description: Write, review, or repair a Wanim scene file for an Adle lesson. Use when generating a visualization for a lesson segment, adding a scene to the sample course, debugging a scene that fails in the player, or updating the pinned Wanim version.
---

# Wanim scene authoring for Adle

Adle teaches with live, interactive visualizations. Each one is **one complete Python file**
written against the manim API and run in the browser by [Wanim](https://wanim.org/). This skill is
everything needed to write a scene that works in Adle's player on the first try.

| | |
|---|---|
| Tested runtime | `@wanimjs/wanim` **0.1.3** (MIT), an early preview |
| API target | manim Community **v0.21** |
| Upstream docs read | 2026-11-19: `wanim.org/llms.txt`, `/docs/intro/`, `/docs/interactive/`, `/docs/usage/` |
| Verified in | Electron 45.4.1 (Chromium 156), inside Adle's isolated player frame |
| Proof | `apps/desktop/e2e/scene-player.spec.ts` runs every file in `examples/` |

Everything below marked **Verified** was exercised against the pinned runtime in this repository.
Anything marked **Documented upstream** comes from Wanim's docs and has *not* been tested here: test
it before relying on it. See [reference.md](reference.md) for the full API notes.

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

**Never set the background.** The player supplies it (`#FFFFFF` light, `#18211C` dark). Do not
use colour as the only carrier of meaning: pair it with position, a label, or a sign.

### Layout

- The stage is 16:9 and about **14.2 × 8** world units, origin at the centre.
- Keep everything inside the safe area: `|x| ≤ 6.3`, `|y| ≤ 3.5`.
- **Title** at the top: `Text(..., font_size=30–36).to_edge(UP, buff=0.5)`.
- **Controls** in a band at the bottom, around `y = -2.7`, each with a `Text` label
  (`font_size=24–26`, `muted`) placed with `next_to(control, UP, buff=0.3)`.
- **Body text and labels** `font_size=24–32`; **formulas** `MathTex(..., font_size=40–48)`;
  **key numbers** `DecimalNumber(..., font_size=40–56)`.
- At most about seven distinct visual elements. If it needs a legend, it is too dense.

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

### Motion

- One idea per animation; `run_time` 0.5–1.5 s; end with a short `self.wait(0.3–0.6)`.
- No flashing, strobing, shaking, or rapid colour cycling. No decorative movement.
- Total `construct()` time under about 15 seconds. Longer explanations are separate segments.

## Performance rules for reactions

Reactions run **every frame** while a `blueprint()` page is live.

- Create objects once, outside the reaction. Inside it, only update: `set_value`, `move_to`,
  `set_color`, `set_width`, `stretch_to_fit_height`, `become`.
- **Never construct `Text`, `MathTex`, or `Matrix` inside a reaction.** For a changing number use
  one `DecimalNumber` and `set_value(...)`.
- Reactions do not run during `construct()`. Use `add_updater`, `ValueTracker`, and
  `always_redraw` there.

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

## Before a scene ships

1. It parses as Python and passes the static policy (`adle_core.generation.scene_policy`).
2. It runs in the player without an error in **both** themes.
3. Nothing is clipped at the 16:9 edges; text is legible at the smallest window size.
4. Every interactive control is in `self.adle_controls` and works from the mirrored input.
5. It still explains the idea with no interaction at all.
6. Its events use only the vocabulary above.
7. The lesson segment that uses it has a text fallback that says the same thing in words.

To try a scene, add it to `examples/` and run the example test, or load it through
**Settings → About & diagnostics** in a development build:

```bash
npm run e2e -- scene-player.spec.ts
```

## Examples (all executed by the end-to-end suite)

| File | Shows |
|---|---|
| [examples/weighted_sum.py](examples/weighted_sum.py) | Animation-only `Scene`: shapes, `Text`, `MathTex`, `Write`/`Create`/`FadeIn` |
| [examples/neuron_weight.py](examples/neuron_weight.py) | `InteractiveScene`: `Slider` + `Switch`, reactions, `on_input`, `explored`/`passed`, then `construct()` |
| [examples/activation_curve.py](examples/activation_curve.py) | `Axes.plot`, a point driven along a curve, `DecimalNumber`, `ValueTracker` + `always_redraw` |

## When the pinned version changes

1. Bump `@wanimjs/wanim` in `apps/desktop/package.json` to an exact version.
2. Re-read the upstream docs and update the table at the top of this file and `reference.md`.
3. Run the end-to-end suite. Every "Verified" claim here must still be true; fix the claim or the
   code, never leave them disagreeing.
4. Record anything that changed in a new ADR that supersedes ADR-004 if isolation is affected.
