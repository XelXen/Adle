from manim import *


class FillInOrder(Scene):
    """A shape filled the way that works in this runtime: the colour, then how solid.

    Whether the middle of the box is painted is what the end-to-end suite looks at.
    """

    def construct(self):
        box = Rectangle(width=4.0, height=2.0, color="#5B8DE6")
        box.set_fill("#5B8DE6", 0.9)
        self.add(box)
        self.wait(0.4)
