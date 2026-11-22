from manim import *
import math


class EquationFigure(Scene):
    """A formula rewritten one step at a time."""

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
        parts = [['\\displaystyle E[X]', '\\displaystyle =', '\\displaystyle \\int_0^1 x \\cdot 2x \\, dx'], ['\\displaystyle E[X]', '\\displaystyle =', '\\displaystyle \\int_0^1 2x^2 \\, dx'], ['\\displaystyle E[X]', '\\displaystyle =', '\\displaystyle \\dfrac{2}{3}']]
        holds = [3.4, 3.8, 3.0]
        steps = []
        for each in parts:
            step = MathTex(*each, font_size=48, color=self.ink)
            step.move_to([0, 0.2, 0])
            steps.append(step)
        self.play(Write(steps[0]), run_time=1.4)
        self.wait(holds[0])
        for index in range(1, len(steps)):
            self.play(TransformMatchingTex(steps[index - 1], steps[index]), run_time=1.4)
            self.wait(holds[index])
        frame = SurroundingRectangle(steps[len(steps) - 1], color=self.sun, buff=0.2)
        self.play(Create(frame), run_time=0.6)
        self.play(FadeOut(frame), run_time=0.5)
