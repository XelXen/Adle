from manim import *


class PointedAt(Scene):
    """Circumscribe given a colour stops a scene in the pinned runtime: the name is taken for its
    shape."""

    def construct(self):
        label = MathTex("z = 0.5", font_size=48)
        self.play(Write(label), run_time=0.4)
        self.play(Circumscribe(label, color="#E9BE5A"), run_time=0.4)
        self.wait(0.2)
