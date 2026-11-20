from manim import *


class DescentSteps(Scene):
    """Animation-only scene: a weight moves down a loss curve in steps that get shorter."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"

    def loss(self, w):
        return (w - 2) * (w - 2)

    def construct(self):
        title = Text("Each step moves the weight downhill", font_size=32, color=self.ink)
        title.to_edge(UP, buff=0.45)

        axes = Axes(
            x_range=[-2, 6, 2],
            y_range=[0, 10, 5],
            x_length=7.0,
            y_length=3.6,
            axis_config={"color": self.muted, "include_tip": False},
        ).shift(UP * 0.1)
        curve = axes.plot(lambda w: self.loss(w), x_range=[-1.1, 5.1], color=self.blue)
        loss_name = Text("loss", font_size=24, color=self.muted).move_to(axes.c2p(0.6, 10.4))
        weight_name = Text("weight", font_size=24, color=self.muted).move_to(axes.c2p(5.4, -1.5))
        lowest = Text("lowest loss", font_size=22, color=self.muted).move_to(axes.c2p(2, 1.9))

        weight = ValueTracker(-1)
        ball = always_redraw(
            lambda: Dot(color=self.coral, radius=0.14).move_to(
                axes.c2p(weight.get_value(), self.loss(weight.get_value()))
            )
        )
        note = Text("The steps shrink as the slope flattens.", font_size=26, color=self.ink)
        note.to_edge(DOWN, buff=0.4)

        self.play(Write(title), run_time=0.8)
        self.play(FadeIn(axes), FadeIn(loss_name), FadeIn(weight_name), run_time=0.7)
        self.play(Create(curve), FadeIn(lowest), run_time=1.0)
        self.add(ball)
        self.wait(2.5)
        # A learning rate of 0.2 on this curve: each step covers 40% of what is left.
        for target in [0.2, 0.92, 1.35, 1.61]:
            self.play(weight.animate.set_value(target), run_time=0.8)
            self.wait(1.2)
        self.play(FadeIn(note), run_time=0.7)
        self.wait(0.8)
