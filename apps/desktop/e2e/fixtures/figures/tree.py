from manim import *
import math


class TreeFigure(Scene):
    """A tree drawn one level at a time."""

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
        holds = [3.8, 4.2, 3.4]
        nodes = [[-5.4, 0.075, 'Start', -1, '', 0, 1], [0.0, -0.75, 'H', 0, '\\tfrac{1}{2}', 1, -1], [0.0, 0.9, 'T', 0, '\\tfrac{1}{2}', 1, 1], [5.4, -0.2, 'HH', 1, '\\tfrac{1}{2}', 2, 1], [5.4, -1.3, 'HT', 1, '\\tfrac{1}{2}', 2, -1]]
        shown = []
        for spec in nodes:
            text = Text(spec[2], font_size=26, color=self.ink).move_to([spec[0], spec[1], 0])
            frame = SurroundingRectangle(text, color=self.blue, buff=0.16)
            shown.append(VGroup(frame, text))
        for depth in range(3):
            parts = []
            for index in range(len(nodes)):
                spec = nodes[index]
                if spec[5] != depth:
                    continue
                parts.append(FadeIn(shown[index], shift=RIGHT * 0.2))
                if spec[3] >= 0:
                    origin = shown[spec[3]]
                    branch = Line(origin.get_right(), shown[index].get_left(), color=self.muted)
                    parts.append(Create(branch))
                    if spec[4]:
                        label = MathTex(spec[4], font_size=34, color=self.ink)
                        label.move_to(branch.get_center() + UP * (0.32 * spec[6]))
                        parts.append(FadeIn(label))
            self.play(*parts, run_time=1.0)
            self.wait(holds[depth])
