from manim import *
import math


class Slide(InteractiveScene):
    """A picture drawn a step at a time, as the narration reaches each."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"
        self.sun = "#E9BE5A" if dark else "#F2C14E"
        self.violet = "#A694E3" if dark else "#9178D7"
        self.teal = "#4FC3C9" if dark else "#2B9EA5"
        self.orange = "#F0A45D" if dark else "#E8893A"
        self.e = {}
        self.set_storyboard([[None, self.step_0], [None, self.step_1], [None, self.step_2], [None, self.step_3]])

    def fit(self, m, w, h):
        if m.width > w:
            m.scale_to_fit_width(w)
        if m.height > h:
            m.scale_to_fit_height(h)
        return m

    def put(self, keys, box, cols):
        group = VGroup(*[self.e[key] for key in keys])
        if cols > 1:
            group.arrange_in_grid(rows=(len(keys) + cols - 1) // cols, cols=cols, buff=0.45)
        elif len(keys) > 1:
            group.arrange(DOWN, buff=0.45)
        self.fit(group, box[2], box[3])
        grow = min(1.35, 0.75 * box[2] / max(group.width, 0.01), 0.75 * box[3] / max(group.height, 0.01))
        if grow > 1:
            group.scale(grow)
        group.move_to([box[0], box[1], 0])

    def keep(self, m):
        # Inside the stage: smaller if it is larger, moved in where it sticks out.
        self.fit(m, 12.4, 6.8)
        dx = 0
        dy = 0
        if m.get_right()[0] > 6.2:
            dx = 6.2 - m.get_right()[0]
        if m.get_left()[0] < -6.2:
            dx = -6.2 - m.get_left()[0]
        if m.get_top()[1] > 3.4:
            dy = 3.4 - m.get_top()[1]
        if m.get_bottom()[1] < -3.4:
            dy = -3.4 - m.get_bottom()[1]
        m.shift(RIGHT * dx + UP * dy)

    def group(self, keys):
        return VGroup(*[self.e[key] for key in keys])

    def beside(self, keys, anchor, side):
        # Where a group goes beside another: 0 below it, 1 above, 2 left of it, 3 right.
        mine = self.group(keys)
        other = self.group(anchor)
        if side == 0:
            return [other.get_center()[0], other.get_bottom()[1] - 0.55 - mine.height / 2, 0]
        if side == 1:
            return [other.get_center()[0], other.get_top()[1] + 0.55 + mine.height / 2, 0]
        if side == 2:
            return [other.get_left()[0] - 0.55 - mine.width / 2, other.get_center()[1], 0]
        return [other.get_right()[0] + 0.55 + mine.width / 2, other.get_center()[1], 0]

    def shown(self, spec, size, hue):
        if spec[0]:
            return MathTex(spec[1], font_size=round(size * 1.45), color=hue)
        return Text(spec[1], font_size=size, color=hue)

    def lines(self, specs, size, hue):
        made = VGroup(*[self.shown(spec, size, hue) for spec in specs])
        if len(specs) > 1:
            made.arrange(DOWN, buff=0.14)
        return made

    def unmark(self):
        if len(self.rings) > 0:
            self.play(*[FadeOut(ring) for ring in self.rings], run_time=0.3)
        self.rings = []

    def ring(self, keys, hue):
        ring = SurroundingRectangle(self.group(keys), color=hue, buff=0.12, corner_radius=0.12)
        self.rings.append(ring)
        return Create(ring)

    def tint(self, m, hue, fill):
        look = m.copy()
        look.set_color(hue)
        if fill > 0:
            look.set_fill(hue, fill)
        return Transform(m, look)

    def shift_to(self, keys, point):
        mine = self.group(keys)
        dx = point[0] - mine.get_center()[0]
        dy = point[1] - mine.get_center()[1]
        return [self.e[key].animate.shift(RIGHT * dx + UP * dy) for key in keys]

    def follow(self):
        for key in self.followers:
            self.e[key].update(0)

    def build(self):
        self.e = {}
        self.ax = {}
        self.trackers = {}
        self.rings = []
        self.followers = []
        self.amount = ValueTracker(0.0)
        self.e['active'] = MathTex(*['\\text{The}', '\\text{dog}', '\\text{chased}', '\\text{the}', '\\text{ball.}'], font_size=49, color=self.blue, arg_separator="\\ ")
        self.e['active.1'] = self.e['active'][0]
        self.e['active.2'] = self.e['active'][1]
        self.e['active.3'] = self.e['active'][2]
        self.e['active.4'] = self.e['active'][3]
        self.e['active.5'] = self.e['active'][4]
        self.e['passive'] = MathTex(*['\\text{The}', '\\text{ball}', '\\text{was}', '\\text{chased}', '\\text{by}', '\\text{the}', '\\text{dog.}'], font_size=49, color=self.green, arg_separator="\\ ")
        self.e['passive.1'] = self.e['passive'][0]
        self.e['passive.2'] = self.e['passive'][1]
        self.e['passive.3'] = self.e['passive'][2]
        self.e['passive.4'] = self.e['passive'][3]
        self.e['passive.5'] = self.e['passive'][4]
        self.e['passive.6'] = self.e['passive'][5]
        self.e['passive.7'] = self.e['passive'][6]
        self.e['first'] = MathTex(*['2x', '+', '3', '=', '7'], font_size=52, color=self.ink)
        self.e['next'] = MathTex(*['2x', '=', '4'], font_size=52, color=self.ink)
        self.put(['active'], [0.0, 1.852, 12.4, 3.096], 1)
        self.put(['first'], [0.0, -1.723, 12.4, 3.354], 1)
        self.fit(self.e['passive'], 12.4, 6.8)
        self.e['passive'].move_to(self.beside(['passive'], ['active'], 0))
        self.keep(self.e['passive'])
        self.fit(self.e['next'], 12.4, 6.8)
        self.e['next'].move_to(self.beside(['next'], ['first'], 0))
        self.keep(self.e['next'])

    def step_0(self):
        self.build()
        self.play(Write(self.e['active']), run_time=1.32)
        self.post_message("step", 0)

    def step_1(self):
        self.play(TransformMatchingTex(self.e['active'].copy(), self.e['passive']), run_time=1.4)
        self.post_message("step", 1)

    def step_2(self):
        self.play(Write(self.e['first']), run_time=1.32)
        self.post_message("step", 2)

    def step_3(self):
        self.play(TransformMatchingTex(self.e['first'].copy(), self.e['next']), run_time=1.4)
        self.post_message("step", 3)
