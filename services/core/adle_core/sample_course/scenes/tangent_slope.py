from manim import *


class TangentSlope(Scene):
    """Animation-only scene: the tangent to a curve at two points; its slope is the derivative."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"

    def construct(self):
        title = Text("The derivative is the slope", font_size=34, color=self.ink)
        title.to_edge(UP, buff=0.45)

        axes = Axes(
            x_range=[0, 3, 1],
            y_range=[0, 6, 2],
            x_length=5.6,
            y_length=4.0,
            axis_config={"color": self.muted, "include_tip": False},
        ).shift(LEFT * 2.2).shift(DOWN * 0.35)
        curve = axes.plot(lambda x: x * x, x_range=[0, 2.4], color=self.blue)
        curve_name = MathTex("y = x^2", font_size=36, color=self.ink).move_to(axes.c2p(1.0, 4.6))

        # A short piece of the tangent at x: it passes through (x, x squared) with slope 2x.
        at = ValueTracker(1)
        half = 0.5
        tangent = always_redraw(
            lambda: Line(
                axes.c2p(
                    at.get_value() - half,
                    at.get_value() * at.get_value() - 2 * at.get_value() * half,
                ),
                axes.c2p(
                    at.get_value() + half,
                    at.get_value() * at.get_value() + 2 * at.get_value() * half,
                ),
                color=self.coral,
            )
        )
        point = always_redraw(
            lambda: Dot(color=self.coral, radius=0.11).move_to(
                axes.c2p(at.get_value(), at.get_value() * at.get_value())
            )
        )

        first = MathTex(r"\text{at } x = 1 \text{, slope } 2", font_size=36, color=self.ink)
        first.move_to([3.6, 1.1, 0])
        second = MathTex(r"\text{at } x = 2 \text{, slope } 4", font_size=36, color=self.ink)
        second.move_to([3.6, 0.2, 0])
        rule = MathTex(r"\text{slope} = 2x", font_size=44, color=self.ink).move_to([3.6, -1.2, 0])

        self.play(Write(title), run_time=0.8)
        self.play(FadeIn(axes), run_time=0.6)
        self.play(Create(curve), FadeIn(curve_name), run_time=1.0)
        self.wait(2.0)
        self.add(tangent, point)
        self.play(FadeIn(first), run_time=0.7)
        self.wait(4.0)
        self.play(at.animate.set_value(2), run_time=2.0)
        self.play(FadeIn(second), run_time=0.7)
        self.wait(1.0)
        self.play(Write(rule), run_time=0.9)
        self.wait(0.8)
