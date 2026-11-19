from manim import *

class Busy(Scene):
    def construct(self):
        self.play(Create(Circle()), run_time=0.3)
        n = 0
        while True:
            n += 1
