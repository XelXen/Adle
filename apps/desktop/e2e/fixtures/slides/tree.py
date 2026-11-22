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
        self.set_storyboard([[None, self.step_0], [None, self.step_1]])

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

    def chip(self, spec, hue, rounded):
        token = self.shown(spec, 32, self.ink)
        if rounded:
            r = token.width / 2 + 0.2
            if token.height / 2 + 0.2 > r:
                r = token.height / 2 + 0.2
            if r < 0.36:
                r = 0.36
            shape = Circle(radius=r, color=hue)
        else:
            shape = SurroundingRectangle(token, color=hue, buff=0.2, corner_radius=0.14)
        shape.set_fill(hue, 0.18)
        shape.move_to(token.get_center())
        return VGroup(shape, token)

    def ends(self, a, b):
        dx = b.get_center()[0] - a.get_center()[0]
        dy = b.get_center()[1] - a.get_center()[1]
        if abs(dx) * 0.6 >= abs(dy):
            if dx >= 0:
                return [a.get_right(), b.get_left()]
            return [a.get_left(), b.get_right()]
        if dy >= 0:
            return [a.get_top(), b.get_bottom()]
        return [a.get_bottom(), b.get_top()]

    def make_nodes(self, key, keys, specs, rounds, places, edges, directed, name, hue):
        nodes = VGroup()
        for index in range(len(keys)):
            chip = self.chip(specs[index], hue, rounds[index])
            chip.move_to([places[index][0], places[index][1], 0])
            self.e[keys[index]] = chip
            nodes.add(chip)
        links = VGroup()
        for edge in edges:
            points = self.ends(self.e[keys[edge[1]]], self.e[keys[edge[2]]])
            if directed:
                link = Arrow(points[0], points[1], buff=0.08, color=self.muted, max_tip_length_to_length_ratio=0.25, max_stroke_width_to_length_ratio=10)
            else:
                link = Line(points[0], points[1], color=self.muted)
            self.e[edge[0]] = link
            links.add(link)
        marks = VGroup()
        if name:
            marks.add(self.shown(name, 30, hue).next_to(nodes, UP, buff=0.35))
        self.e[key + "/frame"] = marks
        self.e[key] = VGroup(marks, links, nodes)

    def build(self):
        self.e = {}
        self.ax = {}
        self.trackers = {}
        self.rings = []
        self.followers = []
        self.amount = ValueTracker(0.0)
        self.make_nodes('calls', ['calls.1', 'calls.2', 'calls.3', 'calls.4', 'calls.5'], [[False, 'fib(3)'], [False, 'fib(2)'], [False, 'fib(1)'], [False, 'fib(1)'], [False, 'fib(0)']], [False, False, False, False, False], [[0.0, 1.6], [-1.3, 0.0], [1.3, 0.0], [-1.3, -1.6], [1.3, -1.6]], [['calls.e1', 0, 1], ['calls.e2', 0, 2], ['calls.e3', 1, 3], ['calls.e4', 1, 4]], True, None, self.blue)
        self.put(['calls'], [0.0, 0.0, 12.4, 6.8], 1)

    def step_0(self):
        self.build()
        self.play(LaggedStart(FadeIn(self.e['calls/frame']), GrowFromCenter(self.e['calls.1']), GrowFromCenter(self.e['calls.2']), GrowFromCenter(self.e['calls.3']), GrowFromCenter(self.e['calls.4']), GrowFromCenter(self.e['calls.5']), GrowArrow(self.e['calls.e1']), GrowArrow(self.e['calls.e2']), GrowArrow(self.e['calls.e3']), GrowArrow(self.e['calls.e4']), lag_ratio=0.12), run_time=2.1)
        self.post_message("step", 0)

    def step_1(self):
        self.play(self.tint(self.e['calls.2'][0], self.sun, 0.45), run_time=0.7)
        self.post_message("step", 1)
