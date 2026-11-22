from manim import *
import math


class GraphFigure(Scene):
    """A graph drawn one part at a time."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"
        self.sun = "#E9BE5A" if dark else "#F2C14E"
        self.violet = "#A694E3" if dark else "#9178D7"

    def curve_0(self, x, p):
        return math.pow(x, 2.0)

    def curve_1(self, x, p):
        return (2.0 * x)

    def value(self, index, x, p):
        if index == 0:
            return self.curve_0(x, p)
        if index == 1:
            return self.curve_1(x, p)
        return self.curve_2(x, p)

    def build(self):
        axes = Axes(
            x_range=[-3.0, 3.0, 1.0],
            y_range=[-4.0, 12.0, 2.0],
            x_length=10.0,
            y_length=4.9,
            axis_config={"color": self.muted, "include_tip": False},
        ).move_to([0, -0.15, 0])
        numbers = VGroup()
        for tick in [[-3.0, '-3'], [-2.0, '-2'], [-1.0, '-1'], [0.0, '0'], [1.0, '1'], [2.0, '2'], [3.0, '3']]:
            numbers.add(
                MathTex(tick[1], font_size=32, color=self.muted).next_to(
                    axes.c2p(tick[0], -4.0), DOWN, buff=0.18
                )
            )
        for tick in [[-4.0, '-4'], [0.0, '0'], [4.0, '4'], [8.0, '8'], [12.0, '12']]:
            if tick[0] != -4.0:
                numbers.add(
                    MathTex(tick[1], font_size=32, color=self.muted).next_to(
                        axes.c2p(-3.0, tick[0]), LEFT, buff=0.18
                    )
                )
        names = VGroup()
        x_label = ''
        y_label = ''
        if x_label:
            names.add(
                MathTex(x_label, font_size=34, color=self.ink).next_to(
                    axes.c2p(3.0, 0.0), RIGHT, buff=0.25
                )
            )
        if y_label:
            names.add(
                MathTex(y_label, font_size=34, color=self.ink).next_to(
                    axes.c2p(0.0, 12.0), RIGHT, buff=0.25
                )
            )
        return axes, numbers, names

    def plot(self, axes, index, p, start, end):
        hues = [self.blue, self.green, self.violet]
        if [False, False][index]:
            # A curve in pieces is drawn in short straight steps: smoothed, it would ripple
            # where it jumps.
            return axes.plot(
                lambda x: self.value(index, x, p),
                x_range=[start, end, (end - start) / 400],
                color=hues[index],
                use_smoothing=False,
            )
        return axes.plot(
            lambda x: self.value(index, x, p),
            x_range=[start, end],
            color=hues[index],
        )

    def rise(self, axes, spec, p, number):
        # How much the curve rises from one place to the other: a dashed run along, and
        # an arrow up by the difference, named beside it. Each rise has a hue of its own.
        hue = [self.coral, self.violet, self.green][number]
        below = self.value(spec[0], spec[1], p)
        above = self.value(spec[0], spec[2], p)
        start = axes.c2p(spec[1], below)
        corner = axes.c2p(spec[2], below)
        end = axes.c2p(spec[2], above)
        drawn = VGroup(
            DashedLine(start, corner, color=self.muted),
            Dot(color=hue, radius=0.08).move_to(start),
            Dot(color=hue, radius=0.08).move_to(end),
        )
        if abs(end[1] - corner[1]) > 0.05:
            arrow = DoubleArrow(corner, end, buff=0, color=hue, max_tip_length_to_length_ratio=0.25, max_stroke_width_to_length_ratio=12)
            drawn.add(arrow)
            if spec[3]:
                drawn.add(MathTex(spec[3], font_size=34, color=self.ink).next_to(arrow, RIGHT, buff=0.15))
        return drawn

    def area(self, axes, index, p, low, high):
        points = [axes.c2p(low, 0)]
        for step in range(61):
            x = low + (high - low) * step / 60
            points.append(axes.c2p(x, self.value(index, x, p)))
        points.append(axes.c2p(high, 0))
        return Polygon(*points, color=self.sun, fill_opacity=0.4, stroke_width=0)

    def legend(self):
        hues = [self.blue, self.green, self.violet]
        labels = ['x^2', '2x']
        rows = [0, 0]
        lines = [VGroup(), VGroup()]
        counts = [0, 0]
        items = []
        for index in range(len(labels)):
            if not labels[index]:
                items.append(None)
                continue
            if index < 2:
                key = Line([0, 0, 0], [0.5, 0, 0], color=hues[index])
                key.set_stroke(width=6)
            else:
                key = Rectangle(width=0.5, height=0.3, color=self.sun, fill_opacity=0.4, stroke_width=0)
            text = MathTex(labels[index], font_size=34, color=self.ink).next_to(key, RIGHT, buff=0.2)
            item = VGroup(key, text)
            items.append(item)
            lines[rows[index]].add(item)
            counts[rows[index]] += 1
        for row in range(2):
            if counts[row] > 0:
                lines[row].arrange(RIGHT, buff=0.7)
                if lines[row].width > 12.4:
                    lines[row].scale(12.4 / lines[row].width)
                lines[row].move_to([0, 3.25 - 0.58 * row, 0])
        return items

    def construct(self):
        holds = [3.6, 4.0, 3.2]
        axes, numbers, names = self.build()
        spans = [[-3.0, 3.0], [-1.5, 3.0]]
        self.play(Create(axes), FadeIn(numbers), FadeIn(names), run_time=1.2)
        self.wait(holds[0])
        step = 1
        legend = self.legend()
        drawn = []
        for index in range(len(spans)):
            curve = self.plot(axes, index, 0, spans[index][0], spans[index][1])
            drawn.append(curve)
            if legend[index] is not None:
                self.play(Create(curve), FadeIn(legend[index]), run_time=1.2)
            else:
                self.play(Create(curve), run_time=1.2)
            self.wait(holds[step])
            step += 1
        shade = None
        if shade:
            area = self.area(axes, shade[0], 0, shade[1], shade[2])
            parts = [FadeIn(area)]
            if legend[len(spans)] is not None:
                parts.append(FadeIn(legend[len(spans)]))
            self.play(*parts, run_time=1.2)
            self.wait(holds[step])
            step += 1
        rises = []
        for number in range(len(rises)):
            self.play(FadeIn(self.rise(axes, rises[number], 0, number)), run_time=1.2)
            self.wait(holds[step])
            step += 1
        marks = []
        if marks:
            sides = [UP + LEFT, UP + RIGHT, UP, DOWN]
            dots = VGroup()
            for mark in marks:
                place = axes.c2p(mark[1], self.value(mark[0], mark[1], 0))
                dot = Dot(color=self.coral, radius=0.1).move_to(place)
                dots.add(dot)
                if mark[2]:
                    dots.add(MathTex(mark[2], font_size=34, color=self.ink).next_to(dot, sides[mark[3]], buff=0.15))
            self.play(LaggedStart(*[GrowFromCenter(item) for item in dots], lag_ratio=0.25), run_time=1.2)
            self.wait(holds[step])
            step += 1
        if False:
            where = ValueTracker(spans[0][0])
            runner = always_redraw(
                lambda: Dot(color=self.coral, radius=0.12).move_to(
                    axes.c2p(where.get_value(), self.value(0, where.get_value(), 0))
                )
            )
            self.add(runner)
            self.play(where.animate.set_value(spans[0][1]), run_time=2.4, rate_func=smooth)
            self.wait(holds[step])
