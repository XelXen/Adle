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

    def die(self, spots, hue):
        body = RoundedRectangle(corner_radius=0.16, width=1.1, height=1.1, color=hue)
        body.set_fill(hue, 0.22)
        made = VGroup(body)
        for spot in spots:
            made.add(Dot(color=self.ink, radius=0.09).move_to([spot[0] * 0.28, spot[1] * 0.28, 0]))
        return made

    def roll(self, key, spots, hue):
        body = self.e[key + "/body"]
        size = body.height
        middle = body.get_center()
        self.play(Rotate(body, angle=PI / 2), run_time=0.22)
        self.play(Rotate(body, angle=PI / 2), run_time=0.22)
        fresh = self.die(spots, hue)
        fresh.scale_to_fit_height(size)
        fresh.move_to(middle)
        body.become(fresh)
        self.play(body.animate.scale(1.12), run_time=0.14)
        self.play(body.animate.scale(1 / 1.12), run_time=0.14)

    def build(self):
        self.e = {}
        self.ax = {}
        self.trackers = {}
        self.rings = []
        self.followers = []
        self.amount = ValueTracker(0.0)
        self.e['die/body'] = self.die([[0, 0]], self.blue)
        self.e['die/frame'] = self.shown([False, 'roll'], 28, self.ink).next_to(self.e['die/body'], DOWN, buff=0.2)
        self.e['die'] = VGroup(self.e['die/body'], self.e['die/frame'])
        number = DecimalNumber(0.0, num_decimal_places=0, font_size=58, color=self.sun)
        self.e['sixes/value'] = number
        title = self.shown([False, 'sixes'], 36, self.ink)
        equals = MathTex("=", font_size=52, color=self.ink)
        self.e['sixes'] = VGroup(title, equals, number).arrange(RIGHT, buff=0.2)
        self.put(['die'], [-3.4, 0.0, 5.6, 6.8], 1)
        self.put(['sixes'], [3.05, 0.0, 6.3, 6.8], 1)

    def step_0(self):
        self.build()
        self.play(LaggedStart(GrowFromCenter(self.e['die/body']), FadeIn(self.e['die/frame']), FadeIn(self.e['sixes'], shift=UP * 0.15), lag_ratio=0.3), run_time=1.26)
        self.post_message("step", 0)

    def step_1(self):
        self.roll('die', [[-1, 1], [1, 1], [-1, -1], [1, -1]], self.blue)
        self.post_message("step", 1)

    def step_2(self):
        self.roll('die', [[-1, 1], [1, 1], [-1, 0], [1, 0], [-1, -1], [1, -1]], self.blue)
        self.play(ChangeDecimalToValue(self.e['sixes/value'], 1.0), run_time=1.2)
        self.post_message("step", 2)
