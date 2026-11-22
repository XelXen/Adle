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

    def make_grid(self, key, keys, specs, rows, cols, side, row_names, col_names, name, hue):
        cells = VGroup()
        for index in range(len(keys)):
            square = Square(side_length=side, color=self.muted)
            square.set_fill(hue, 0.08)
            token = self.shown(specs[index], 28, self.ink)
            self.fit(token, side - 0.16, side - 0.16)
            token.move_to(square.get_center())
            cell = VGroup(square, token)
            self.e[keys[index]] = cell
            cells.add(cell)
        cells.arrange_in_grid(rows=rows, cols=cols, buff=0)
        marks = VGroup()
        for index in range(len(row_names)):
            marks.add(self.shown(row_names[index], 26, self.muted).next_to(self.e[keys[index * cols]], LEFT, buff=0.2))
        for index in range(len(col_names)):
            marks.add(self.shown(col_names[index], 26, self.muted).next_to(self.e[keys[index]], UP, buff=0.2))
        if name:
            lift = 0.25
            if len(col_names) > 0:
                lift = 0.75
            marks.add(self.shown(name, 30, hue).next_to(cells, UP, buff=lift))
        self.e[key + "/frame"] = marks
        self.e[key] = VGroup(marks, cells)

    def build(self):
        self.e = {}
        self.ax = {}
        self.trackers = {}
        self.rings = []
        self.followers = []
        self.amount = ValueTracker(0.0)
        self.make_grid('g', ['g.1.1', 'g.1.2', 'g.1.3', 'g.1.4', 'g.2.1', 'g.2.2', 'g.2.3', 'g.2.4', 'g.3.1', 'g.3.2', 'g.3.3', 'g.3.4'], [[False, ' '], [False, ' '], [False, ' '], [False, ' '], [False, ' '], [False, ' '], [False, ' '], [False, ' '], [False, ' '], [False, ' '], [False, ' '], [False, ' ']], 3, 4, 0.72, [], [], None, self.blue)
        self.e['area'] = MathTex(*['\\color{#3DBE7F}{3}', '\\times', '\\color{#7BA4EE}{4}', '= 12'], font_size=52, color=self.ink)
        self.e['area.1'] = self.e['area'][0]
        self.e['area.2'] = self.e['area'][2]
        self.put(['g'], [-3.195, 0.0, 6.01, 6.8], 1)
        self.put(['area'], [3.255, 0.0, 5.89, 6.8], 1)
        self.e['w'] = Brace(self.group(['g.1.1', 'g.1.2', 'g.1.3', 'g.1.4']), UP, color=self.blue)
        self.e['w/name'] = self.shown([True, '4'], 28, self.ink).next_to(self.e['w'], UP, buff=0.12)
        self.keep(self.e['w/name'])
        self.e['h'] = Brace(self.group(['g.1.1', 'g.2.1', 'g.3.1']), LEFT, color=self.green)
        self.e['h/name'] = self.shown([True, '3'], 28, self.ink).next_to(self.e['h'], LEFT, buff=0.12)
        self.keep(self.e['h/name'])

    def step_0(self):
        self.build()
        self.play(LaggedStart(FadeIn(self.e['g/frame']), FadeIn(self.e['g.1.1'], shift=UP * 0.15), FadeIn(self.e['g.1.2'], shift=UP * 0.15), FadeIn(self.e['g.1.3'], shift=UP * 0.15), FadeIn(self.e['g.1.4'], shift=UP * 0.15), FadeIn(self.e['g.2.1'], shift=UP * 0.15), FadeIn(self.e['g.2.2'], shift=UP * 0.15), FadeIn(self.e['g.2.3'], shift=UP * 0.15), FadeIn(self.e['g.2.4'], shift=UP * 0.15), FadeIn(self.e['g.3.1'], shift=UP * 0.15), FadeIn(self.e['g.3.2'], shift=UP * 0.15), FadeIn(self.e['g.3.3'], shift=UP * 0.15), FadeIn(self.e['g.3.4'], shift=UP * 0.15), lag_ratio=0.12), run_time=2.46)
        self.post_message("step", 0)

    def step_1(self):
        self.play(self.tint(self.e['g.1.1'][0], self.blue, 0.45), self.tint(self.e['g.1.2'][0], self.blue, 0.45), self.tint(self.e['g.1.3'][0], self.blue, 0.45), self.tint(self.e['g.1.4'][0], self.blue, 0.45), run_time=0.7)
        self.play(LaggedStart(GrowFromCenter(self.e['w']), FadeIn(self.e['w/name']), lag_ratio=0.3), run_time=1.14)
        self.post_message("step", 1)

    def step_2(self):
        self.play(self.tint(self.e['g.1.1'][0], self.green, 0.45), self.tint(self.e['g.2.1'][0], self.green, 0.45), self.tint(self.e['g.3.1'][0], self.green, 0.45), run_time=0.7)
        self.play(LaggedStart(GrowFromCenter(self.e['h']), FadeIn(self.e['h/name']), lag_ratio=0.3), run_time=1.14)
        self.post_message("step", 2)

    def step_3(self):
        self.play(Write(self.e['area']), run_time=1.32)
        self.play(self.ring(['area.1'], self.sun), self.ring(['area.2'], self.sun), self.e['area.1'].animate.scale(1.12), self.e['area.2'].animate.scale(1.12), run_time=0.45)
        self.play(self.e['area.1'].animate.scale(1 / 1.12), self.e['area.2'].animate.scale(1 / 1.12), run_time=0.25)
        self.post_message("step", 3)
