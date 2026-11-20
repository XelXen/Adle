from manim import *


class LossErrors(Scene):
    """Animation-only scene: errors as gaps between predictions and targets, then their MSE."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"

    def prediction(self, point):
        return Rectangle(width=0.3, height=0.3, color=self.coral).move_to(point)

    def construct(self):
        title = Text("How far is each prediction from its target?", font_size=30, color=self.ink)
        title.to_edge(UP, buff=0.45)

        axes = Axes(
            x_range=[0, 4, 1],
            y_range=[0, 4, 1],
            x_length=5.6,
            y_length=3.4,
            axis_config={"color": self.muted, "include_tip": False},
        ).shift(LEFT * 1.6).shift(UP * 0.35)

        # Targets are dots; predictions are open squares. The middle prediction is exact.
        targets = VGroup(
            Dot(color=self.blue, radius=0.11).move_to(axes.c2p(1, 2)),
            Dot(color=self.blue, radius=0.11).move_to(axes.c2p(2, 1)),
            Dot(color=self.blue, radius=0.11).move_to(axes.c2p(3, 3)),
        )
        predictions = VGroup(
            self.prediction(axes.c2p(1, 3)),
            self.prediction(axes.c2p(2, 1)),
            self.prediction(axes.c2p(3, 1)),
        )
        gaps = VGroup(
            Line(axes.c2p(1, 2), axes.c2p(1, 3), color=self.muted),
            Line(axes.c2p(3, 3), axes.c2p(3, 1), color=self.muted),
        )
        errors = VGroup(
            MathTex("+1", font_size=34, color=self.ink).move_to(axes.c2p(1.38, 2.5)),
            MathTex("0", font_size=34, color=self.ink).move_to(axes.c2p(2.38, 1)),
            MathTex("-2", font_size=34, color=self.ink).move_to(axes.c2p(3.38, 2)),
        )

        target_key = Dot(color=self.blue, radius=0.11).move_to([3.1, 1.5, 0])
        target_text = Text("target", font_size=26, color=self.ink).next_to(
            target_key, RIGHT, buff=0.3
        )
        prediction_key = self.prediction([3.1, 0.7, 0])
        prediction_text = Text("prediction", font_size=26, color=self.ink).next_to(
            prediction_key, RIGHT, buff=0.3
        )

        formula = MathTex(
            r"\text{MSE} = \dfrac{1^2 + 0^2 + (-2)^2}{3} = \dfrac{5}{3}",
            font_size=40,
            color=self.ink,
        )
        formula.to_edge(DOWN, buff=0.4)

        self.play(Write(title), run_time=0.8)
        self.play(FadeIn(axes), run_time=0.6)
        self.play(FadeIn(targets), FadeIn(target_key), FadeIn(target_text), run_time=0.8)
        self.play(
            FadeIn(predictions), FadeIn(prediction_key), FadeIn(prediction_text), run_time=0.8
        )
        self.wait(2.5)
        self.play(Create(gaps), run_time=0.8)
        self.play(FadeIn(errors), run_time=0.8)
        self.wait(4.0)
        self.play(Write(formula), run_time=1.4)
        self.wait(0.8)
