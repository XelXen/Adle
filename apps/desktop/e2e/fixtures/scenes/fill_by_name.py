from manim import *


class FillByName(Scene):
    """The same box with how solid it is given by name: it runs, and the box is left empty.

    A fixture, not an example. The static policy rejects this form.
    """

    def construct(self):
        box = Rectangle(width=4.0, height=2.0, color="#5B8DE6")
        box.set_fill("#5B8DE6", opacity=0.9)
        self.add(box)
        self.wait(0.4)
