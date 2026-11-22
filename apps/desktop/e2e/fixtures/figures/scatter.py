from manim import *
import math


class ScatterFigure(Scene):
    """Points, and a line through them."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"
        self.sun = "#E9BE5A" if dark else "#F2C14E"
        self.violet = "#A694E3" if dark else "#9178D7"

    def construct(self):
        holds = [2.4, 2.4, 2.4, 2.4]
        axes = Axes(
            x_range=[0.5, 5.5, 0.5],
            y_range=[0.0, 12.0, 2.0],
            x_length=10.0,
            y_length=4.9,
            axis_config={"color": self.muted, "include_tip": False},
        ).move_to([0, -0.15, 0])
        numbers = VGroup()
        for tick in [[1.0, '1'], [2.0, '2'], [3.0, '3'], [4.0, '4'], [5.0, '5']]:
            numbers.add(MathTex(tick[1], font_size=32, color=self.muted).next_to(axes.c2p(tick[0], 0.0), DOWN, buff=0.18))
        for tick in [[0.0, '0'], [4.0, '4'], [8.0, '8'], [12.0, '12']]:
            if tick[0] != 0.0:
                numbers.add(MathTex(tick[1], font_size=32, color=self.muted).next_to(axes.c2p(0.5, tick[0]), LEFT, buff=0.18))
        names = VGroup()
        if 'x':
            names.add(MathTex('x', font_size=34, color=self.ink).next_to(axes.c2p(5.5, 0.0), RIGHT, buff=0.25))
        if 'y':
            names.add(MathTex('y', font_size=34, color=self.ink).next_to(axes.c2p(0.5, 12.0), RIGHT, buff=0.25))
        self.play(Create(axes), FadeIn(numbers), FadeIn(names), run_time=1.2)
        self.wait(holds[0])
        points = [[1.0, 2.1], [2.0, 3.9], [3.0, 6.2], [4.0, 7.8], [5.0, 10.1]]
        dots = VGroup()
        for point in points:
            dots.add(Dot(color=self.blue, radius=0.08).move_to(axes.c2p(point[0], point[1])))
        self.play(LaggedStart(*[GrowFromCenter(dot) for dot in dots], lag_ratio=0.05), run_time=1.2)
        self.wait(holds[1])
        fit = [2.0, 0.0, '\\hat y = 2x', 0]
        if fit:
            low = 1.0
            high = 5.0
            trend = axes.plot(lambda x: fit[0] * x + fit[1], x_range=[low, high], color=self.green)
            parts = [Create(trend)]
            if fit[2]:
                words = MathTex(fit[2], font_size=34, color=self.ink)
                if fit[3] == 0:
                    words.next_to(axes.c2p(high, fit[0] * high + fit[1]), UP + LEFT, buff=0.2)
                else:
                    words.next_to(axes.c2p(low, fit[0] * low + fit[1]), UP + RIGHT, buff=0.2)
                parts.append(Write(words))
            self.play(*parts, run_time=1.2)
            self.wait(holds[2])
            if True:
                gaps = VGroup()
                for point in points:
                    gaps.add(Line(axes.c2p(point[0], point[1]), axes.c2p(point[0], fit[0] * point[0] + fit[1]), color=self.coral))
                self.play(Create(gaps), run_time=1.2)
                self.wait(holds[3])
