from manim import *


class SumToOutput(Scene):
    """Animation-only scene: a neuron's inputs become one number, step by step with the
    narration; each symbol keeps the colour of the thing it stands for."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"
        self.sun = "#E9BE5A" if dark else "#F2C14E"

    def construct(self):
        # 1. The picture: two inputs, two connections, one neuron.
        neuron = Circle(radius=0.55, color=self.ink).move_to([1.6, 1.0, 0])
        tops = [[-3.6, 2.0, 0], [-3.6, 0.0, 0]]
        inputs = VGroup(*[Dot(color=self.blue, radius=0.14).move_to(point) for point in tops])
        input_labels = VGroup(
            MathTex("x_1 = 2", font_size=36, color=self.ink).next_to(inputs[0], LEFT, buff=0.3),
            MathTex("x_2 = 1", font_size=36, color=self.ink).next_to(inputs[1], LEFT, buff=0.3),
        )
        links = VGroup(
            *[
                Arrow(dot.get_center(), neuron.get_left(), buff=0.18, color=self.green)
                for dot in inputs
            ]
        )
        weight_labels = VGroup(
            MathTex("w_1 = 0.5", font_size=34, color=self.ink).next_to(links[0], UP, buff=0.1),
            MathTex("w_2 = -1", font_size=34, color=self.ink).next_to(links[1], DOWN, buff=0.1),
        )
        self.play(
            LaggedStart(*[GrowFromCenter(dot) for dot in inputs], lag_ratio=0.3), run_time=1.0
        )
        self.play(FadeIn(input_labels, shift=RIGHT * 0.2), run_time=0.8)
        self.wait(1.2)
        self.play(LaggedStart(*[GrowArrow(link) for link in links], lag_ratio=0.3), run_time=1.0)
        self.play(FadeIn(weight_labels), Create(neuron), run_time=0.9)
        self.wait(1.5)

        # 2. The rule, each symbol in the colour of what it stands for.
        rule = MathTex("z", "=", "w_1", "x_1", "+", "w_2", "x_2", "+", "b", font_size=44)
        rule.move_to([0, -1.7, 0])
        rule.set_color(self.ink)
        for index in (2, 5):
            rule[index].set_color(self.green)
        for index in (3, 6):
            rule[index].set_color(self.blue)
        rule[8].set_color(self.coral)
        self.play(Write(rule), run_time=1.4)
        self.wait(1.0)
        # Each product, pointed out where it is in the picture.
        self.play(Indicate(rule[2]), Indicate(links[0]), run_time=0.9)
        self.play(Indicate(rule[3]), Indicate(inputs[0]), run_time=0.9)
        self.wait(1.0)

        # 3. The same rule with the numbers in it, and then what it comes to.
        numbers = MathTex("z", "=", "(0.5)", "(2)", "+", "(-1)", "(1)", "+", "0.5", font_size=44)
        numbers.move_to(rule)
        numbers.set_color(self.ink)
        for index in (2, 5):
            numbers[index].set_color(self.green)
        for index in (3, 6):
            numbers[index].set_color(self.blue)
        numbers[8].set_color(self.coral)
        self.play(TransformMatchingTex(rule, numbers), run_time=1.4)
        self.wait(1.2)
        result = MathTex("z", "=", "0.5", font_size=52, color=self.ink).move_to(numbers)
        self.play(TransformMatchingTex(numbers, result), run_time=1.2)
        frame = SurroundingRectangle(result, color=self.sun, buff=0.18)
        self.play(Create(frame), run_time=0.7)
        self.play(FadeOut(frame), run_time=0.5)
        self.wait(1.0)

        # 4. Turn one weight up and watch the sum follow it.
        weight = ValueTracker(0.5)
        live = always_redraw(
            lambda: DecimalNumber(
                weight.get_value() * 2 - 1 + 0.5,
                num_decimal_places=1,
                font_size=52,
                color=self.ink,
            ).next_to(result[1], RIGHT, buff=0.25)
        )
        label = always_redraw(
            lambda: MathTex(
                "w_1 = " + f"{weight.get_value():.1f}", font_size=34, color=self.ink
            ).next_to(links[0], UP, buff=0.1)
        )
        self.play(FadeOut(result[2]), FadeOut(weight_labels[0]), run_time=0.4)
        self.add(live, label)
        glow = always_redraw(
            lambda: Circle(
                radius=0.55 + 0.12 * weight.get_value(), color=self.sun, stroke_width=3
            ).move_to(neuron)
        )
        self.add(glow)
        self.play(weight.animate.set_value(2.0), run_time=2.5)
        self.wait(0.8)
        self.play(weight.animate.set_value(0.5), run_time=1.5)
        self.wait(1.0)
