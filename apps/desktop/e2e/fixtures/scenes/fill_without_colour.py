from manim import *


class FillWithoutColour(Scene):
    """A fill given by name alone: the names are taken for the colour and the scene stops.

    A fixture, not an example. The static policy rejects this form. A lesson a real model
    wrote lost its interactive picture to this line (2026-11-21).
    """

    def construct(self):
        box = Rectangle(width=4.0, height=2.0, color="#5B8DE6")
        box.set_fill(opacity=0.9)
        self.add(box)
        self.wait(0.4)
