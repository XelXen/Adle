from manim import *
import math


class TableFigure(Scene):
    """A table filled in, one row after another."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"
        self.sun = "#E9BE5A" if dark else "#F2C14E"
        self.violet = "#A694E3" if dark else "#9178D7"

    def cell(self, spec, hue, room):
        if spec[0]:
            made = MathTex(spec[1], font_size=34, color=hue)
        else:
            made = Text(spec[1], font_size=26, color=hue)
        if made.width > room:
            made.scale(room / made.width)
        return made

    def construct(self):
        holds = [3.8, 4.2, 3.4]
        xs = [-1.4, 0.0, 1.4]
        rooms = [1.1, 1.1, 1.1]
        ys = [2.6, 1.75, 0.9, 0.05]
        header = [[True, 'x'], [True, 'f(x)'], [True, 'F(x)']]
        rows = [[[False, '0'], [False, '0'], [False, '0']], [[False, '0.5'], [False, '1'], [False, '0.25']], [[False, '1'], [False, '2'], [False, '1']]]
        heading = VGroup()
        for index in range(len(header)):
            heading.add(self.cell(header[index], self.ink, rooms[index]).move_to([xs[index], ys[0], 0]))
        rule = Line([-2.1, ys[0] - 0.85 / 2, 0], [2.1, ys[0] - 0.85 / 2, 0], color=self.muted)
        self.play(FadeIn(heading), Create(rule), run_time=1.0)
        self.wait(holds[0])
        lines = []
        for row in range(len(rows)):
            line = VGroup()
            for index in range(len(header)):
                line.add(self.cell(rows[row][index], self.ink, rooms[index]).move_to([xs[index], ys[row + 1], 0]))
            lines.append(line)
        self.play(LaggedStart(*[FadeIn(line, shift=UP * 0.15) for line in lines], lag_ratio=0.2), run_time=1.2)
        self.wait(holds[1])
        picks = [2]
        step = 2
        for pick in picks:
            frame = SurroundingRectangle(lines[pick - 1], color=self.sun, buff=0.12)
            self.play(Create(frame), run_time=0.7)
            self.wait(holds[step])
            self.play(FadeOut(frame), run_time=0.3)
            step += 1
