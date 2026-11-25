You write one chapter of a narrated teaching film for Adle. The film teaches a whole course, a chapter for each concept, in the order they are learned; it is watched from start to end, like a video of 3Blue1Brown: nothing waits for the viewer and nothing is operated. A chapter is one complete Python file for ManimGX, an animation engine with the API of Manim Community Edition.

Answer with the Python file only: no explanation before or after it.

# The file

- Begin with `import manimgx as m`. You may also `import numpy as np` and `import math`. Nothing else may be imported.
- Define exactly one class, `class Chapter(m.Scene):`, with `def construct(self):`. Helper functions and constants go at the top of the file; helper methods on the class are fine. No other class.
- Everything of the engine is on `m`: `m.Text`, `m.MathTex`, `m.Circle`, `m.Create`, `m.UP`, `m.BLUE`. Never write a bare `Circle` or `from manimgx import`.
- Time passes only in `self.play(...)` (one second unless `run_time=`), `self.wait(seconds)` and `self.say(...)`. `self.add(...)` shows something without animating it.
- The chapter begins on an empty stage. It never refers to anything of another chapter.

# The narration

- Every idea is said aloud with `self.say("...", animation, animation)`. The first argument is what is said. Put square brackets around the words during which each animation plays: one bracketed span for each animation, in the same order.
  `self.say("Here is a rectangle, [four wide] and [two tall].", m.Write(wide), m.Write(tall))`
- A line with no animation is fine: `self.say("Now look at the two sides.")`.
- The line is one plain string written out in the call. Never a variable, an f-string or strings joined with `+`.
- It is read aloud by a voice, so it is plain spoken words: no symbols, no LaTeX, no digits glued to letters. Write "x squared", "two thirds", "H two O", "ten newtons".
- One or two sentences a line, at most 40 words. Never put the narration's sentences on the screen: the screen shows the picture and its labels.
- A chapter says 16 to 28 lines: three to four minutes. It covers every objective it is given, each with an example of its own, in the order given. Do not write fewer than 12 lines.

# The frame

- The frame is 14.2 units wide and 8 high, centered on the origin. Keep everything within x from -6.4 to 6.4 and y from -3.5 to 3.5.
- The background is dark; do not change it. Words are `m.WHITE`. Give each thing the film talks about one color and keep it for the whole chapter (`m.BLUE`, `m.YELLOW`, `m.GREEN`, `m.RED`, `m.TEAL`, `m.ORANGE`, `m.PURPLE`), and write a symbol in the color of the thing it stands for.
- Sizes: the chapter's title `font_size=44` at the top (`.to_edge(m.UP, buff=0.5)`); labels 28 to 34; never under 24. Formulas are `m.MathTex(r"...", font_size=44)`; plain words are `m.Text("...")`, never `m.Tex`.
- To color the parts of a formula, write it in parts and color each by its place: `law = m.MathTex("a", "=", r"\frac{F}{m}")`, then `law[0].set_color(m.YELLOW)`. Never use `tex_to_color_map`, `substrings_to_isolate` or `set_color_by_tex`: they cut the formula at every place a key occurs, also inside a command (`a` inside `\frac`), and the formula breaks.
- Words must never lie over other words or under a line, and nothing may leave the frame: the engine checks every moment and sends the chapter back. So:
  - place with `.next_to(other, m.DOWN, buff=0.3)`, `.to_edge(...)`, `.move_to([x, y, 0])`, and `m.VGroup(a, b, c).arrange(m.DOWN, buff=0.4)`; do not guess coordinates for things that sit beside other things;
  - keep the picture on the left half or in the middle and what is written about it on the right, or the picture above and the writing below;
  - before something new goes where something stands, take the old thing away (`m.FadeOut(old)`) or turn it into the new (`m.ReplacementTransform(old, new)`); a `Transform` leaves the old object on stage under the new shape, so prefer `ReplacementTransform`;
  - a box with words in it is made around the words, never the words fitted into a box of a size you guessed: `label = m.Text("Debt", font_size=30)`, then `box = m.SurroundingRectangle(label, buff=0.25, corner_radius=0.15)`; for two lines, arrange them in a `VGroup` and put the box around the group;
  - an arrow goes from the edge of one thing to the edge of another, `m.Arrow(box.get_right(), other.get_left(), buff=0.15)`, and only where nothing written lies between its ends;
  - a label for a line or an arrow goes beside it (`.next_to(line, m.UP, buff=0.2)`), never on it;
  - long text: at most about 45 characters on a line at `font_size=30`. Break it into two `m.Text` lines in a `VGroup` arranged downward;
  - something wide (a table, a row of boxes, a long formula) is made to fit: `.scale_to_fit_width(6)` before it is placed. A table holds short words and numbers: `m.Table([["2", "4"], ["3", "9"]], col_labels=[m.Text("x"), m.Text("x squared")])`, at most four columns; for formulas in a table, `m.MathTable`.
- A chapter is four to six stages. When a stage is full, clear it and start a fresh one: `self.play(m.FadeOut(m.VGroup(*self.mobjects)))`. Keep the title out of the group if it should stay.
- End the chapter by clearing the stage the same way.

# What exists (a short list; anything of Manim CE's two-dimensional API works)

- Shapes: `m.Square(side_length=2)`, `m.Rectangle(width=4, height=2)`, `m.Circle(radius=1)`, `m.Dot(point)`, `m.Line(a, b)`, `m.Arrow(a, b, buff=0)`, `m.DashedLine(a, b)`, `m.Polygon(a, b, c)`, `m.Brace(mob, m.DOWN)`, `m.SurroundingRectangle(mob, buff=0.15)`, `m.RoundedRectangle(corner_radius=0.2, width=3, height=1)`. Points are `[x, y, 0]`. Style with `color=`, `fill_opacity=`, `stroke_width=`.
- Text and numbers: `m.Text("words", font_size=30, color=m.WHITE)`, `m.MathTex(r"a^2 + b^2 = c^2")`, `m.DecimalNumber(3.5, num_decimal_places=1)`, `m.ValueTracker(0)` with `m.always_redraw(lambda: ...)`.
- Graphs: `axes = m.Axes(x_range=[0, 5, 1], y_range=[0, 10, 2], x_length=6, y_length=4, axis_config={"include_numbers": True})`, `axes.plot(lambda x: x**2, color=m.BLUE)`, `axes.c2p(x, y)` for a point, `axes.get_axis_labels(x_label="t", y_label="d")`, `axes.get_area(graph, x_range=[1, 3])`. Also `m.NumberLine(x_range=[0, 10, 1], length=10, include_numbers=True)`, `m.BarChart(values=[3, 5, 2], bar_names=["a", "b", "c"])`.
- Groups: `m.VGroup(a, b)`, `.arrange(m.RIGHT, buff=0.5)`, `.arrange_in_grid(rows=2, cols=4, buff=0.2)`.
- Animations: `m.Create`, `m.Write`, `m.FadeIn(mob, shift=m.UP * 0.3)`, `m.FadeOut`, `m.GrowArrow`, `m.GrowFromCenter`, `m.ReplacementTransform(a, b)`, `m.TransformFromCopy(a, b)`, `m.Indicate(mob)`, `m.Circumscribe(mob)`, `m.Flash(point)`, `m.MoveAlongPath(mob, path)`, `m.Rotate(mob, angle)`, and `mob.animate.shift(m.RIGHT).set_color(m.RED)`. Together: `m.AnimationGroup(a, b)`, `m.LaggedStart(*animations, lag_ratio=0.2)`, `m.Succession(a, b)`.
- Motion that shows a thing happening is better than a still picture: a point that travels along a curve, a quantity that grows, a bar that fills, an arrow that turns.

# What is refused

- Files, pictures from files, sound and the network: `ImageMobject`, `SVGMobject`, `Sound`, `add_sound`, `m.config`, `open`. Three-dimensional scenes and objects. `m.Code` with a file (use `m.Code(code_string="...", language="python")`).
- `while`, `try`, `with`, `global`, `print`, decorators, `**` in a call, any name beginning with an underscore, and `.format(...)` (the screen's text is written out).
- A font file or folder: `font="..."` takes a family name written out, and is rarely needed.

# How a chapter teaches

{TEACHING}

- Open on the case, not on a definition and not on a list of what the chapter will cover. The first thing on screen after the title is something to look at.
- Say how this chapter follows from the ones before it in one line, if it does.
- End with one line that says the idea again in plain words, then clear the stage.

# An example of the form (not of the content, and shorter than a chapter)

```python
{EXAMPLE}
```
