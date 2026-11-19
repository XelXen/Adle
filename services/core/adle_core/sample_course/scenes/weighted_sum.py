from manim import *


class WeightedSum(Scene):
    """Animation-only scene: introduces the weighted sum a neuron computes."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"

    def construct(self):
        title = Text("A neuron adds up weighted inputs", font_size=36, color=self.ink)
        title.to_edge(UP, buff=0.7)

        inputs = VGroup(
            Circle(radius=0.35, color=self.blue, fill_opacity=0.25),
            Circle(radius=0.35, color=self.blue, fill_opacity=0.25),
        ).arrange(DOWN, buff=1.2).shift(LEFT * 4)
        neuron = Circle(radius=0.6, color=self.green, fill_opacity=0.25)
        wires = VGroup(*[Line(dot.get_right(), neuron.get_left(), color=self.muted) for dot in inputs])

        formula = MathTex(r"z = w_1 x_1 + w_2 x_2 + b", font_size=44, color=self.ink)
        formula.to_edge(DOWN, buff=0.9)

        self.play(Write(title), run_time=0.8)
        self.play(FadeIn(inputs), Create(wires), GrowFromCenter(neuron), run_time=1.0)
        self.play(Write(formula), run_time=1.0)
        self.wait(0.4)
