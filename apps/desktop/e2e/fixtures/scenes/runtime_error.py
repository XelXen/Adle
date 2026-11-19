from manim import *

class Boom(Scene):
    def construct(self):
        self.play(Create(Circle()), run_time=0.3)
        values = [1, 2, 3]
        self.add(Text(str(values[10].real)))
        undefined_function_name(3)
