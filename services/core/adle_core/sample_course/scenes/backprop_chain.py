from manim import *


class BackpropChain(Scene):
    """Animation-only scene: values move forward through a chain, rates of change move back."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"

    def box(self, x):
        return Rectangle(width=2.6, height=1.1, color=self.green, fill_opacity=0.15).move_to(
            [x, 1.1, 0]
        )

    def construct(self):
        title = Text("Forward for values, backward for rates", font_size=32, color=self.ink)
        title.to_edge(UP, buff=0.45)

        boxes = VGroup(self.box(-4.8), self.box(-1.6), self.box(1.6), self.box(4.8))
        names = VGroup(
            MathTex("x", font_size=34, color=self.ink).move_to([-4.8, 1.1, 0]),
            MathTex("h = w_1 x", font_size=34, color=self.ink).move_to([-1.6, 1.1, 0]),
            MathTex("y = w_2 h", font_size=34, color=self.ink).move_to([1.6, 1.1, 0]),
            MathTex("L = (y - t)^2", font_size=34, color=self.ink).move_to([4.8, 1.1, 0]),
        )
        links = VGroup(
            Line([-3.5, 1.1, 0], [-2.9, 1.1, 0], color=self.muted),
            Line([-0.3, 1.1, 0], [0.3, 1.1, 0], color=self.muted),
            Line([2.9, 1.1, 0], [3.5, 1.1, 0], color=self.muted),
        )

        # The forward pass, with w1 = 2, w2 = 3 and a target of 5.
        value_x = MathTex("1", font_size=40, color=self.ink).move_to([-4.8, 0.0, 0])
        value_h = MathTex("2", font_size=40, color=self.ink).move_to([-1.6, 0.0, 0])
        value_y = MathTex("6", font_size=40, color=self.ink).move_to([1.6, 0.0, 0])
        value_loss = MathTex("1", font_size=40, color=self.ink).move_to([4.8, 0.0, 0])
        forward_mark = Line([-5.9, -0.45, 0], [5.9, -0.45, 0], color=self.blue)
        forward_note = Text("Forward: the values, left to right.", font_size=26, color=self.ink)
        forward_note.move_to([0, -2.55, 0])

        # The backward pass: how fast the loss changes with each value.
        rate_y = MathTex(r"\dfrac{dL}{dy} = 2", font_size=36, color=self.ink)
        rate_y.move_to([1.6, -1.3, 0])
        rate_h = MathTex(r"\dfrac{dL}{dh} = 6", font_size=36, color=self.ink)
        rate_h.move_to([-1.6, -1.3, 0])
        backward_mark = Line([-2.9, -1.95, 0], [2.9, -1.95, 0], color=self.coral)
        backward_note = Text(
            "Backward: the rates of change, right to left.", font_size=26, color=self.ink
        )
        backward_note.move_to([0, -3.2, 0])

        self.play(Write(title), run_time=0.8)
        self.play(FadeIn(boxes), FadeIn(names), Create(links), run_time=1.0)
        self.wait(2.5)
        self.play(FadeIn(forward_note), Create(forward_mark), run_time=0.6)
        self.play(FadeIn(value_x), run_time=0.45)
        self.play(FadeIn(value_h), run_time=0.45)
        self.play(FadeIn(value_y), run_time=0.45)
        self.play(FadeIn(value_loss), run_time=0.45)
        self.wait(3.0)
        self.play(FadeIn(backward_note), Create(backward_mark), run_time=0.6)
        self.play(FadeIn(rate_y), run_time=0.7)
        self.play(FadeIn(rate_h), run_time=0.7)
        self.wait(0.8)
