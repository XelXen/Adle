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

    def make_set(self, key, keys, specs, rows, cols, name, hue):
        chips = VGroup()
        for index in range(len(keys)):
            chip = self.chip(specs[index], hue, True)
            self.e[keys[index]] = chip
            chips.add(chip)
        if len(keys) > 1:
            chips.arrange_in_grid(rows=rows, cols=cols, buff=0.4)
        width = 2.2
        height = 1.6
        if len(keys) > 0:
            # The smallest oval around a block passes through its corners: half again as
            # wide and high, and a little more, holds them inside.
            width = chips.width * 1.42 + 0.6
            height = chips.height * 1.42 + 0.6
        frame = Circle(radius=1, color=hue).stretch_to_fit_width(width).stretch_to_fit_height(height)
        if len(keys) > 0:
            frame.move_to(chips.get_center())
        self.e[key + "/frame"] = frame
        whole = VGroup(frame, chips)
        if name:
            title = self.shown(name, 30, hue)
            title.move_to([frame.get_left()[0] + title.width / 2 + 0.1, frame.get_top()[1] + title.height / 2 + 0.08, 0])
            self.e[key + "/name"] = title
            whole.add(title)
        self.e[key] = whole

    def build(self):
        self.e = {}
        self.ax = {}
        self.trackers = {}
        self.rings = []
        self.followers = []
        self.amount = ValueTracker(0.0)
        self.make_set('omega', ['omega.1', 'omega.2', 'omega.3', 'omega.4'], [[False, 'HH'], [False, 'HT'], [False, 'TH'], [False, 'TT']], 2, 2, [True, '\\Omega'], self.blue)
        self.e['count'] = MathTex(*['P(E) =', '\\color{#E9BE5A}{2}', '/', '\\color{#7BA4EE}{4}'], font_size=52, color=self.ink)
        self.e['count.1'] = self.e['count'][1]
        self.e['count.2'] = self.e['count'][3]
        self.e['rule'] = MathTex(*['P(E) =', '\\color{#E9BE5A}{|E|}', '/', '\\color{#7BA4EE}{|\\Omega|}'], font_size=52, color=self.ink)
        self.e['rule.1'] = self.e['rule'][1]
        self.e['rule.2'] = self.e['rule'][3]
        self.put(['omega'], [-3.195, 0.0, 6.01, 6.8], 1)
        self.put(['count'], [3.255, 0.0, 5.89, 6.8], 1)
        self.fit(self.e['rule'], 5.89, 6.8)
        self.e['rule'].move_to(self.e['count'].get_center())
        self.e['event'] = SurroundingRectangle(self.group(['omega.1', 'omega.2']), color=self.sun, buff=0.16, corner_radius=0.14)
        self.e['event/name'] = self.shown([True, 'E'], 28, self.sun).next_to(self.e['event'], UP, buff=0.1)

    def step_0(self):
        self.build()
        self.play(LaggedStart(Create(self.e['omega/frame']), FadeIn(self.e['omega/name']), GrowFromCenter(self.e['omega.1']), GrowFromCenter(self.e['omega.2']), GrowFromCenter(self.e['omega.3']), GrowFromCenter(self.e['omega.4']), lag_ratio=0.3), run_time=1.62)
        self.post_message("step", 0)

    def step_1(self):
        self.play(self.tint(self.e['omega.1'][0], self.sun, 0.45), self.tint(self.e['omega.2'][0], self.sun, 0.45), run_time=0.7)
        self.play(LaggedStart(Create(self.e['event']), FadeIn(self.e['event/name']), lag_ratio=0.3), run_time=1.14)
        self.post_message("step", 1)

    def step_2(self):
        self.play(self.ring(['event/name'], self.sun), self.ring(['omega/frame', 'omega/name', 'omega.1', 'omega.2', 'omega.3', 'omega.4'], self.blue), TransformFromCopy(self.e['event/name'], self.e['count'][1]), TransformFromCopy(self.group(['omega/frame', 'omega/name', 'omega.1', 'omega.2', 'omega.3', 'omega.4']), self.e['count'][3]), FadeIn(self.e['count'][0]), FadeIn(self.e['count'][2]), run_time=1.5)
        self.remove(*self.e['count'].submobjects)
        self.add(self.e['count'])
        self.post_message("step", 2)

    def step_3(self):
        self.unmark()
        self.play(TransformMatchingTex(self.e['count'], self.e['rule']), run_time=1.4)
        self.post_message("step", 3)
