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
        self.set_storyboard([[None, self.step_0], [None, self.step_1], [None, self.step_2]])

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

    def make_axes(self, key, xr, yr, size, xs, ys, cross, x_label, y_label):
        axes = Axes(x_range=xr, y_range=yr, x_length=size[0], y_length=size[1], axis_config={"color": self.muted, "include_tip": False})
        marks = VGroup()
        for tick in xs:
            marks.add(MathTex(tick[1], font_size=36, color=self.muted).next_to(axes.c2p(tick[0], yr[0]), DOWN, buff=0.15))
        for tick in ys:
            if tick[0] != yr[0]:
                marks.add(MathTex(tick[1], font_size=36, color=self.muted).next_to(axes.c2p(xr[0], tick[0]), LEFT, buff=0.15))
        if x_label:
            marks.add(self.shown(x_label, 28, self.ink).next_to(axes.c2p(xr[1], cross[1]), RIGHT, buff=0.2))
        if y_label:
            marks.add(self.shown(y_label, 28, self.ink).next_to(axes.c2p(cross[0], yr[1]), UP, buff=0.2))
        self.ax[key] = axes
        self.e[key + "/body"] = axes
        self.e[key + "/frame"] = marks
        self.e[key] = VGroup(axes, marks)

    def make_vector(self, key, axes, start, end, name, hue):
        tail = self.ax[axes].c2p(start[0], start[1])
        tip = self.ax[axes].c2p(end[0], end[1])
        self.e[key] = Arrow(tail, tip, buff=0, color=hue, max_tip_length_to_length_ratio=0.2, max_stroke_width_to_length_ratio=10)
        if name:
            self.e[key + "/name"] = self.shown(name, 28, hue).next_to(tip, UP + RIGHT, buff=0.1)

    def build(self):
        self.e = {}
        self.ax = {}
        self.trackers = {}
        self.rings = []
        self.followers = []
        self.amount = ValueTracker(0.0)
        self.make_axes('plane', [-1.0, 5.0, 1.0], [-1.0, 4.0, 1.0], [10.6, 6.05], [[-1.0, '-1'], [0.0, '0'], [1.0, '1'], [2.0, '2'], [3.0, '3'], [4.0, '4'], [5.0, '5']], [[0.0, '0'], [2.0, '2'], [4.0, '4']], [0.0, 0.0], None, None)
        self.put(['plane'], [0.0, 0.0, 12.4, 6.8], 1)
        self.make_vector('u', 'plane', [0.0, 0.0], [3.0, 1.0], [True, 'u'], self.blue)
        self.make_vector('v', 'plane', [3.0, 1.0], [4.0, 3.0], [True, 'v'], self.green)
        self.make_vector('w', 'plane', [0.0, 0.0], [4.0, 3.0], [True, 'u + v'], self.sun)

    def step_0(self):
        self.build()
        self.play(LaggedStart(Create(self.e['plane/body']), FadeIn(self.e['plane/frame']), GrowArrow(self.e['u']), FadeIn(self.e['u/name']), lag_ratio=0.3), run_time=1.38)
        self.post_message("step", 0)

    def step_1(self):
        self.play(LaggedStart(GrowArrow(self.e['v']), FadeIn(self.e['v/name']), lag_ratio=0.3), run_time=1.14)
        self.post_message("step", 1)

    def step_2(self):
        self.play(LaggedStart(GrowArrow(self.e['w']), FadeIn(self.e['w/name']), lag_ratio=0.3), run_time=1.14)
        self.post_message("step", 2)
