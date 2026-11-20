from manim import *


class ForwardPass(Scene):
    """Animation-only scene: values move through a small network, layer by layer."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.violet = "#A694E3" if dark else "#9178D7"

    def construct(self):
        title = Text("Values flow from left to right", font_size=32, color=self.ink)
        title.to_edge(UP, buff=0.45)

        x1 = Circle(radius=0.42, color=self.blue, fill_opacity=0.25).move_to([-3.6, 1.0, 0])
        x2 = Circle(radius=0.42, color=self.blue, fill_opacity=0.25).move_to([-3.6, -1.3, 0])
        h1 = Circle(radius=0.5, color=self.green, fill_opacity=0.25).move_to([0, 1.0, 0])
        h2 = Circle(radius=0.5, color=self.green, fill_opacity=0.25).move_to([0, -1.3, 0])
        out = Circle(radius=0.55, color=self.violet, fill_opacity=0.25).move_to([3.6, -0.15, 0])

        wires_in = VGroup(
            Line(x1.get_right(), h1.get_left(), color=self.muted),
            Line(x1.get_right(), h2.get_left(), color=self.muted),
            Line(x2.get_right(), h1.get_left(), color=self.muted),
            Line(x2.get_right(), h2.get_left(), color=self.muted),
        )
        wires_out = VGroup(
            Line(h1.get_right(), out.get_left(), color=self.muted),
            Line(h2.get_right(), out.get_left(), color=self.muted),
        )

        x1_value = MathTex("x_1 = 1", font_size=34, color=self.ink).next_to(x1, LEFT, buff=0.25)
        x2_value = MathTex("x_2 = 2", font_size=34, color=self.ink).next_to(x2, LEFT, buff=0.25)
        h1_value = MathTex("h_1 = 3", font_size=34, color=self.ink).next_to(h1, UP, buff=0.2)
        h2_value = MathTex("h_2 = 0", font_size=34, color=self.ink).next_to(h2, DOWN, buff=0.2)
        out_value = MathTex("y = 5", font_size=38, color=self.ink).next_to(out, UP, buff=0.25)

        in_name = Text("inputs", font_size=24, color=self.muted).move_to([-3.6, -2.9, 0])
        hidden_name = Text("hidden layer", font_size=24, color=self.muted).move_to([0, -2.9, 0])
        out_name = Text("output", font_size=24, color=self.muted).move_to([3.6, -2.9, 0])

        self.play(Write(title), run_time=0.8)
        self.play(
            FadeIn(x1),
            FadeIn(x2),
            FadeIn(x1_value),
            FadeIn(x2_value),
            FadeIn(in_name),
            run_time=0.9,
        )
        self.wait(2.5)
        self.play(Create(wires_in), run_time=0.9)
        self.play(GrowFromCenter(h1), GrowFromCenter(h2), FadeIn(hidden_name), run_time=0.8)
        self.play(FadeIn(h1_value), FadeIn(h2_value), run_time=0.8)
        self.wait(3.5)
        self.play(Create(wires_out), run_time=0.8)
        self.play(GrowFromCenter(out), FadeIn(out_name), run_time=0.8)
        self.play(FadeIn(out_value), run_time=0.8)
        self.wait(0.8)
