from manim import *


class StopsHalfWay(Scene):
    """Passes the static policy, then fails while it is playing."""

    def construct(self):
        self.play(Create(Circle()), run_time=0.3)
        values = [1, 2, 3]
        self.add(Text(str(values[10].real)))
