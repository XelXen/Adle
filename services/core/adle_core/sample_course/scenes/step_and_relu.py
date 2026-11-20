from manim import *


class StepAndRelu(Scene):
    """Animation-only scene: the step function and ReLU drawn side by side."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"

    def graph(self):
        return Axes(
            x_range=[-4, 4, 2],
            y_range=[0, 4, 1],
            x_length=5.0,
            y_length=3.2,
            axis_config={"color": self.muted, "include_tip": False},
        )

    def construct(self):
        title = Text("Two ways to respond to a sum", font_size=34, color=self.ink)
        title.to_edge(UP, buff=0.5)

        left = self.graph().shift(LEFT * 3.3).shift(DOWN * 0.3)
        right = self.graph().shift(RIGHT * 3.3).shift(DOWN * 0.3)

        step_name = Text("Step", font_size=30, color=self.ink).move_to([-3.3, 1.75, 0])
        step_low = Line(left.c2p(-4, 0), left.c2p(0, 0), color=self.blue)
        step_high = Line(left.c2p(0, 1), left.c2p(4, 1), color=self.blue)
        step_note = Text("off below zero, on from zero", font_size=24, color=self.muted)
        step_note.next_to(left, DOWN, buff=0.35)

        relu_name = Text("ReLU", font_size=30, color=self.ink).move_to([3.3, 1.75, 0])
        relu_flat = Line(right.c2p(-4, 0), right.c2p(0, 0), color=self.coral)
        relu_ramp = Line(right.c2p(0, 0), right.c2p(4, 4), color=self.coral)
        relu_note = Text("zero below zero, then z itself", font_size=24, color=self.muted)
        relu_note.next_to(right, DOWN, buff=0.35)

        self.play(Write(title), run_time=0.8)
        self.play(FadeIn(left), FadeIn(step_name), run_time=0.8)
        self.play(Create(step_low), run_time=0.7)
        self.play(Create(step_high), FadeIn(step_note), run_time=0.7)
        self.wait(4.0)
        self.play(FadeIn(right), FadeIn(relu_name), run_time=0.8)
        self.play(Create(relu_flat), run_time=0.7)
        self.play(Create(relu_ramp), FadeIn(relu_note), run_time=0.9)
        self.wait(0.6)
