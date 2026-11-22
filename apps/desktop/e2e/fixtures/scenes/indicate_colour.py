from manim import *


class PointedAt(Scene):
    """Indicate given a colour stops a scene in the pinned runtime: it makes a point that is
    not a number."""

    def construct(self):
        bar = Rectangle(width=1.0, height=2.0, fill_opacity=0.6)
        self.play(FadeIn(bar), run_time=0.4)
        self.play(Indicate(bar, color="#E9BE5A"), run_time=0.4)
        self.wait(0.2)
