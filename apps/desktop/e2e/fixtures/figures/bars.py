from manim import *
import math


class BarsFigure(Scene):
    """Bars drawn and then changed."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"
        self.sun = "#E9BE5A" if dark else "#F2C14E"
        self.violet = "#A694E3" if dark else "#9178D7"

    def bar(self, x, height, hue):
        bar = Rectangle(width=1.4, height=max(0.02, abs(height)), color=hue, fill_opacity=0.6)
        bar.move_to([x, -2.3 + height / 2, 0])
        return bar

    def construct(self):
        holds = [2.4, 2.4, 2.4, 2.4]
        xs = [-2.4, 0.0, 2.4]
        heights = [1.75, 3.5, 1.75]
        values = ['0.25', '0.5', '0.25']
        names = ['0', '1', '2']
        baseline = Line([-6.0, -2.3, 0], [6.0, -2.3, 0], color=self.muted)
        labels = VGroup()
        for index in range(len(xs)):
            labels.add(
                Text(names[index], font_size=24, color=self.muted).move_to(
                    [xs[index], -2.3 - 0.45 if heights[index] >= 0 else -2.3 + 0.45, 0]
                )
            )
        unit = 'P(X = x)'
        extra = []
        if unit:
            extra.append(FadeIn(MathTex(unit, font_size=34, color=self.ink).to_edge(UP, buff=0.4)))
        self.play(Create(baseline), FadeIn(labels), *extra, run_time=1.2)
        self.wait(holds[0])
        bars = VGroup()
        numbers = VGroup()
        for index in range(len(xs)):
            hue = self.blue if heights[index] >= 0 else self.coral
            bar = self.bar(xs[index], heights[index], hue)
            bars.add(bar)
            numbers.add(
                Text(values[index], font_size=24, color=self.ink).next_to(
                    bar, UP if heights[index] >= 0 else DOWN, buff=0.15
                )
            )
        self.play(
            LaggedStart(*[FadeIn(bar, shift=UP * 0.4) for bar in bars], lag_ratio=0.15),
            FadeIn(numbers),
            run_time=1.4,
        )
        self.wait(holds[1])
        step = 2
        pick = 1
        if pick >= 0:
            self.play(Indicate(bars[pick]), Indicate(numbers[pick]), run_time=1.2)
            self.wait(holds[step])
            step += 1
        later = [0.7, 4.2, 2.1]
        if later:
            shown = ['0.1', '0.6', '0.3']
            moves = []
            for index in range(len(xs)):
                hue = self.blue if later[index] >= 0 else self.coral
                bar = self.bar(xs[index], later[index], hue)
                number = Text(shown[index], font_size=24, color=self.ink).next_to(
                    bar, UP if later[index] >= 0 else DOWN, buff=0.15
                )
                moves.append(Transform(bars[index], bar))
                moves.append(Transform(numbers[index], number))
            self.play(*moves, run_time=1.4)
            self.wait(holds[step])
