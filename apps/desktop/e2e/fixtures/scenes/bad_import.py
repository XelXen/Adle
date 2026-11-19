import os
from manim import *

class UsesOs(Scene):
    def construct(self):
        self.add(Text(os.getcwd()))
