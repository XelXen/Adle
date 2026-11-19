from manim import *

class Verbatim(Scene):
    def construct(self):
        value = v'(function(){ return typeof window.parent; })()'
        self.post_message("explored", "verbatim=" + str(value))
        self.wait(0.2)
