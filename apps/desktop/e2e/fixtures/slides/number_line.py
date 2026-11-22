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

    def plot(self, axes, index, a, b, hue, pieces):
        p = self.amount.get_value()
        if pieces:
            return axes.plot(lambda x: self.value(index, x, p), x_range=[a, b, (b - a) / 400], color=hue, use_smoothing=False)
        return axes.plot(lambda x: self.value(index, x, p), x_range=[a, b], color=hue)

    def make_curve(self, key, axes, index, a, b, hue, pieces, follows):
        if follows:
            self.e[key] = always_redraw(lambda: self.plot(axes, index, a, b, hue, pieces))
            self.followers.append(key)
        else:
            self.e[key] = self.plot(axes, index, a, b, hue, pieces)

    def spot(self, on, index, x, a, b):
        if index < 0:
            return self.e[on].n2p(x)
        if x < a:
            x = a
        if x > b:
            x = b
        return self.ax[on].c2p(x, self.value(index, x, self.amount.get_value()))

    def marker(self, on, index, tracker, a, b, name, hue):
        dot = Dot(color=hue, radius=0.1).move_to(self.spot(on, index, tracker.get_value(), a, b))
        if name:
            return VGroup(dot, self.shown(name, 26, self.ink).next_to(dot, UP + RIGHT, buff=0.1))
        return VGroup(dot)

    def make_point(self, key, on, index, x, a, b, name, hue):
        tracker = self.amount
        if x is not None:
            tracker = ValueTracker(x)
        self.trackers[key] = tracker
        self.e[key] = always_redraw(lambda: self.marker(on, index, tracker, a, b, name, hue))
        self.followers.append(key)

    def make_number_line(self, key, xr, length, ticks, name):
        line = NumberLine(x_range=xr, length=length, include_numbers=False, color=self.muted)
        marks = VGroup()
        for tick in ticks:
            marks.add(MathTex(tick[1], font_size=36, color=self.muted).next_to(line.n2p(tick[0]), DOWN, buff=0.2))
        if name:
            marks.add(self.shown(name, 28, self.ink).next_to(line, RIGHT, buff=0.3))
        self.e[key + "/body"] = line
        self.e[key + "/frame"] = marks
        self.e[key] = VGroup(line, marks)

    def build(self):
        self.e = {}
        self.ax = {}
        self.trackers = {}
        self.rings = []
        self.followers = []
        self.amount = ValueTracker(0.0)
        self.make_number_line('line', [0.0, 10.0, 2.5], 11.21, [[0.0, '0'], [2.5, '2.5'], [5.0, '5'], [7.5, '7.5'], [10.0, '10']], [True, 'x'])
        self.e['where'] = self.lines([[False, 'X lands somewhere between 0 and 10.']], 34, self.ink)
        self.put(['line'], [0.0, -1.519, 12.4, 3.762], 1)
        self.put(['where'], [0.0, 2.056, 12.4, 2.688], 1)
        self.make_point('X', 'line/body', -1, 2.0, 0.0, 10.0, [True, 'X'], self.coral)

    def step_0(self):
        self.build()
        self.play(LaggedStart(Create(self.e['line/body']), FadeIn(self.e['line/frame']), FadeIn(self.e['where'], shift=UP * 0.15), lag_ratio=0.3), run_time=1.26)
        self.post_message("step", 0)

    def step_1(self):
        self.play(FadeIn(self.e['X']), run_time=1.02)
        self.post_message("step", 1)

    def step_2(self):
        self.play(self.trackers['X'].animate.set_value(7.0), run_time=1.6, rate_func=smooth)
        self.post_message("step", 2)
