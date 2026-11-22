from manim import *
import math


class NumberLineFigure(Scene):
    """A number line with marks and a moving point."""

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
        line = Line([-6.0, -0.4, 0], [6.0, -0.4, 0], color=self.muted)
        ticks = VGroup()
        for tick in [[-5.8, '-3'], [-3.867, '-2'], [-1.933, '-1'], [0.0, '0'], [1.933, '1'], [3.867, '2'], [5.8, '3']]:
            ticks.add(Line([tick[0], -0.55, 0], [tick[0], -0.25, 0], color=self.muted))
            ticks.add(MathTex(tick[1], font_size=32, color=self.muted).move_to([tick[0], -1.0, 0]))
        self.play(Create(line), FadeIn(ticks), run_time=1.2)
        self.wait(holds[0])
        step = 1
        marks = [[-3.789, '-1.96'], [3.789, '1.96']]
        if marks:
            dots = VGroup()
            for mark in marks:
                # Over the interval drawn later, which would hide half of it.
                dot = Dot(color=self.coral, radius=0.11).move_to([mark[0], -0.4, 0]).set_z_index(2)
                dots.add(dot)
                if mark[1]:
                    dots.add(MathTex(mark[1], font_size=34, color=self.ink).next_to(dot, UP, buff=0.3))
            self.play(LaggedStart(*[FadeIn(item, shift=DOWN * 0.2) for item in dots], lag_ratio=0.2), run_time=1.2)
            self.wait(holds[step])
            step += 1
        interval = [-3.789, 3.789, '95\\%']
        if interval:
            band = Line([interval[0], -0.4, 0], [interval[1], -0.4, 0], color=self.green)
            band.set_stroke(width=12)
            parts = [Create(band)]
            if interval[2]:
                words = MathTex(interval[2], font_size=34, color=self.ink)
                words.move_to([(interval[0] + interval[1]) / 2, 0.75, 0])
                parts.append(Write(words))
            self.play(*parts, run_time=1.2)
            self.wait(holds[step])
            step += 1
        move = [0.0, 2.9, '']
        if move:
            where = ValueTracker(move[0])
            runner = always_redraw(lambda: Dot(color=self.blue, radius=0.14).move_to([where.get_value(), -0.4, 0]).set_z_index(3))
            self.add(runner)
            self.play(where.animate.set_value(move[1]), run_time=2.0, rate_func=smooth)
            self.wait(holds[step])
