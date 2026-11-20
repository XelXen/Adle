from manim import *


class PerceptronBoundary(Scene):
    """Animation-only scene: a perceptron's decision boundary, and the bias sliding it."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"

    def construct(self):
        title = Text("One straight line between yes and no", font_size=32, color=self.ink)
        title.to_edge(UP, buff=0.45)

        axes = Axes(
            x_range=[0, 4.5, 1],
            y_range=[0, 4.5, 1],
            x_length=5.2,
            y_length=4.4,
            axis_config={"color": self.muted, "include_tip": False},
        ).shift(LEFT * 2.4).shift(DOWN * 0.45)
        x_name = MathTex("x_1", font_size=34, color=self.muted).move_to(axes.c2p(4.85, 0))
        y_name = MathTex("x_2", font_size=34, color=self.muted).move_to(axes.c2p(0, 4.85))

        # Yes and no differ in shape as well as colour.
        yes_marks = VGroup(
            Dot(color=self.blue, radius=0.13).move_to(axes.c2p(2.5, 2.5)),
            Dot(color=self.blue, radius=0.13).move_to(axes.c2p(2, 1.5)),
        )
        no_marks = VGroup(
            Rectangle(width=0.26, height=0.26, color=self.coral, fill_opacity=0.6).move_to(
                axes.c2p(1, 1)
            ),
            Rectangle(width=0.26, height=0.26, color=self.coral, fill_opacity=0.6).move_to(
                axes.c2p(0.5, 1.5)
            ),
        )

        yes_key = Dot(color=self.blue, radius=0.13).move_to([2.2, 1.3, 0])
        yes_text = Text("answers yes", font_size=26, color=self.ink).next_to(
            yes_key, RIGHT, buff=0.3
        )
        no_key = Rectangle(width=0.26, height=0.26, color=self.coral, fill_opacity=0.6)
        no_key.move_to([2.2, 0.5, 0])
        no_text = Text("answers no", font_size=26, color=self.ink).next_to(no_key, RIGHT, buff=0.3)
        line_key = Line([1.95, -0.3, 0], [2.45, -0.3, 0], color=self.green)
        line_text = Text("decision boundary", font_size=26, color=self.ink).next_to(
            line_key, RIGHT, buff=0.3
        )

        # The boundary is where x1 + x2 equals minus the bias.
        reach = ValueTracker(3)
        boundary = always_redraw(
            lambda: Line(
                axes.c2p(0, reach.get_value()), axes.c2p(reach.get_value(), 0), color=self.green
            )
        )
        note = Text("A more negative bias slides the line outwards.", font_size=26, color=self.ink)
        note.to_edge(DOWN, buff=0.3)

        self.play(Write(title), run_time=0.8)
        self.play(FadeIn(axes), FadeIn(x_name), FadeIn(y_name), run_time=0.8)
        self.play(
            FadeIn(yes_marks),
            FadeIn(no_marks),
            FadeIn(yes_key),
            FadeIn(yes_text),
            FadeIn(no_key),
            FadeIn(no_text),
            run_time=1.0,
        )
        self.wait(3.0)
        self.add(boundary)
        self.play(FadeIn(line_key), FadeIn(line_text), run_time=0.8)
        self.wait(4.0)
        self.play(reach.animate.set_value(4), FadeIn(note), run_time=1.6)
        self.wait(0.8)
