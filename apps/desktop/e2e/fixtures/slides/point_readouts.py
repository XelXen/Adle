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
        self.set_storyboard([[None, self.step_0], [None, self.step_1], [None, self.step_2], [self.blueprint, None]])

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

    def touching(self, axes, index, tracker, a, b, hue):
        x = tracker.get_value()
        if x < a:
            x = a
        if x > b:
            x = b
        p = self.amount.get_value()
        h = (b - a) / 2000
        left = axes.c2p(x - h, self.value(index, x - h, p))
        right = axes.c2p(x + h, self.value(index, x + h, p))
        middle = axes.c2p(x, self.value(index, x, p))
        dx = right[0] - left[0]
        dy = right[1] - left[1]
        size = math.sqrt(dx * dx + dy * dy)
        if size < 0.000001:
            dx = 1
            dy = 0
            size = 1
        ux = dx / size * 1.8
        uy = dy / size * 1.8
        return Line([middle[0] - ux, middle[1] - uy, 0], [middle[0] + ux, middle[1] + uy, 0], color=hue)

    def make_tangent(self, key, axes, index, point, a, b, hue):
        tracker = self.trackers[point]
        self.e[key] = always_redraw(lambda: self.touching(axes, index, tracker, a, b, hue))
        self.followers.append(key)

    def f_0(self, x, p):
        return math.pow(x, 2.0)

    def f_1(self, x, p):
        return x

    def f_2(self, x, p):
        return (2.0 * x)

    def value(self, index, x, p):
        if index == 0:
            return self.f_0(x, p)
        if index == 1:
            return self.f_1(x, p)
        return self.f_2(x, p)

    def build(self):
        self.e = {}
        self.ax = {}
        self.trackers = {}
        self.rings = []
        self.followers = []
        self.amount = ValueTracker(-2.0)
        self.make_axes('axes', [-3.0, 3.0, 1.0], [-2.0, 10.0, 2.0], [6.34, 3.73], [[-3.0, '-3'], [-2.0, '-2'], [-1.0, '-1'], [0.0, '0'], [1.0, '1'], [2.0, '2'], [3.0, '3']], [[0.0, '0'], [4.0, '4'], [8.0, '8']], [0.0, 0.0], None, None)
        number = DecimalNumber(-2.0, num_decimal_places=1, font_size=58, color=self.coral)
        number.add_updater(lambda m: m.set_value(self.value(1, self.trackers['p'].get_value(), self.amount.get_value())))
        self.followers.append('where/value')
        self.e['where/value'] = number
        title = self.shown([True, 'x'], 36, self.ink)
        equals = MathTex("=", font_size=52, color=self.ink)
        self.e['where'] = VGroup(title, equals, number).arrange(RIGHT, buff=0.2)
        number = DecimalNumber(-4.0, num_decimal_places=1, font_size=58, color=self.violet)
        number.add_updater(lambda m: m.set_value(self.value(2, self.trackers['p'].get_value(), self.amount.get_value())))
        self.followers.append('slope/value')
        self.e['slope/value'] = number
        title = self.shown([True, "f'(x)"], 36, self.ink)
        equals = MathTex("=", font_size=52, color=self.ink)
        self.e['slope'] = VGroup(title, equals, number).arrange(RIGHT, buff=0.2)
        self.put(['axes'], [-2.48, -0.209, 7.44, 4.481], 1)
        self.put(['where'], [2.48, 2.891, 7.44, 1.019], 1)
        self.fit(self.e['slope'], 7.44, 6.8)
        self.e['slope'].move_to(self.beside(['slope'], ['where'], 0))
        self.keep(self.e['slope'])
        self.make_curve('curve', self.ax['axes'], 0, -3.0, 3.0, self.blue, False, False)
        self.make_point('p', 'axes', 0, None, -3.0, 3.0, None, self.coral)
        self.make_tangent('tangent', self.ax['axes'], 0, 'p', -3.0, 3.0, self.violet)

    def step_0(self):
        self.build()
        self.play(LaggedStart(Create(self.e['axes/body']), FadeIn(self.e['axes/frame']), Create(self.e['curve']), FadeIn(self.e['p']), FadeIn(self.e['tangent']), FadeIn(self.e['where']), FadeIn(self.e['slope']), lag_ratio=0.12), run_time=1.74)
        self.post_message("step", 0)

    def step_1(self):
        self.play(self.trackers['p'].animate.set_value(0.0), run_time=1.6, rate_func=smooth)
        self.play(self.amount.animate.set_value(0.0), run_time=2.0, rate_func=smooth)
        self.post_message("step", 1)

    def step_2(self):
        self.play(self.trackers['p'].animate.set_value(2.0), run_time=1.6, rate_func=smooth)
        self.play(self.amount.animate.set_value(2.0), run_time=2.0, rate_func=smooth)
        self.post_message("step", 2)

    def blueprint(self):
        self.state = {"explored": False}
        knob = Slider(start=[-3.0, -3.05, 0], end=[3.0, -3.05, 0], value_range=(-3.0, 3.0), init_value=2.0, color=self.green)
        self.adle_controls = {'x_value': knob}
        title = self.shown([False, 'x_value'], 28, self.ink)
        title.next_to(knob, LEFT, buff=0.35)
        reading = DecimalNumber(2.0, num_decimal_places=2, font_size=42, color=self.ink)
        reading.next_to(knob, RIGHT, buff=0.35)
        
        def moved(control, previous, value):
            self.amount.set_value(value)
            reading.set_value(value)
            self.follow()
            if not self.state["explored"]:
                self.state["explored"] = True
                self.post_message("explored", True)
        
        knob.on_input(moved)
        self.add(knob, title, reading)
        self.post_message("step", 3)
