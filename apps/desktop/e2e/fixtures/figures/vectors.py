from manim import *
import math


class VectorsFigure(Scene):
    """Vectors drawn from the origin, and their sum."""

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
        axes = Axes(
            x_range=[-7.0, 7.0, 1.0],
            y_range=[-4.0, 4.0, 1.0],
            x_length=10.675,
            y_length=6.1,
            axis_config={"color": self.muted, "include_tip": False},
        ).move_to([0, -0.2, 0])
        self.add(axes)
        sides = [RIGHT, UP + RIGHT, UP, UP + LEFT, LEFT, DOWN + LEFT, DOWN, DOWN + RIGHT]
        hues = [self.blue, self.green, self.violet]
        vectors = [[2.0, 1.0, '\\vec a', 7], [1.0, 2.0, '\\vec b', 3]]
        arrows = []
        for index in range(len(vectors)):
            vector = vectors[index]
            arrow = Arrow(axes.c2p(0, 0), axes.c2p(vector[0], vector[1]), buff=0, color=hues[index], max_tip_length_to_length_ratio=0.35, max_stroke_width_to_length_ratio=12)
            arrows.append(arrow)
            parts = [GrowArrow(arrow)]
            if vector[2]:
                name = MathTex(vector[2], font_size=36, color=self.ink)
                name.next_to(axes.c2p(vector[0] / 2, vector[1] / 2), sides[vector[3]], buff=0.15)
                parts.append(FadeIn(name))
            self.play(*parts, run_time=1.0)
            self.wait(holds[index])
        if True:
            tip = [vectors[0][0], vectors[0][1]]
            moved = []
            for index in range(1, len(vectors)):
                vector = vectors[index]
                copy = Arrow(axes.c2p(tip[0], tip[1]), axes.c2p(tip[0] + vector[0], tip[1] + vector[1]), buff=0, color=hues[index], max_tip_length_to_length_ratio=0.35, max_stroke_width_to_length_ratio=12)
                moved.append(TransformFromCopy(arrows[index], copy))
                tip = [tip[0] + vector[0], tip[1] + vector[1]]
            self.play(*moved, run_time=1.2)
            total = [3.0, 3.0, '\\vec a + \\vec b', 1]
            if True:
                result = Arrow(axes.c2p(0, 0), axes.c2p(total[0], total[1]), buff=0, color=self.coral, max_tip_length_to_length_ratio=0.35, max_stroke_width_to_length_ratio=12)
                parts = [GrowArrow(result)]
                if total[2]:
                    name = MathTex(total[2], font_size=36, color=self.ink)
                    name.next_to(axes.c2p(total[0], total[1]), sides[total[3]], buff=0.15)
                    parts.append(FadeIn(name))
                self.play(*parts, run_time=1.0)
            self.wait(holds[len(holds) - 1])
