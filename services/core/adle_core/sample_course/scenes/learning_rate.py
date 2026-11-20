from manim import *


class LearningRate(InteractiveScene):
    """Interactive scene: set the learning rate and see where one step lands on the curve."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"

    def loss(self, w):
        return (w - 2) * (w - 2)

    def blueprint(self):
        self.state = {"explored": False, "passed": False}

        title = Text("One step from the start, at different learning rates", font_size=28)
        title.set_color(self.ink)
        title.to_edge(UP, buff=0.4)

        axes = Axes(
            x_range=[-2, 7, 1],
            y_range=[0, 18, 6],
            x_length=7.6,
            y_length=3.3,
            axis_config={"color": self.muted, "include_tip": False},
        ).shift(UP * 0.55)
        curve = axes.plot(lambda w: self.loss(w), x_range=[-2.2, 6.2], color=self.blue)

        rate = Slider(
            start=[-4.6, -2.9, 0],
            end=[0.6, -2.9, 0],
            value_range=(0, 1.2),
            init_value=0.1,
            color=self.green,
        )
        # Named controls are mirrored to the Adle host for keyboard and screen-reader access.
        self.adle_controls = {"learning_rate": rate}
        rate_label = Text("learning rate", font_size=24, color=self.muted)
        rate_label.next_to(rate, UP, buff=0.25)

        # One step from w = -1, where the derivative is -6: the weight lands at -1 + 6 * rate.
        def landing_weight():
            return -1 + 6 * rate.get_value()

        start = Dot(color=self.muted, radius=0.12).move_to(axes.c2p(-1, 9))
        start_label = Text("start", font_size=22, color=self.muted).next_to(start, LEFT, buff=0.2)
        landing = Dot(color=self.coral, radius=0.14)
        landing.add_reaction(
            lambda m: m.move_to(axes.c2p(landing_weight(), self.loss(landing_weight())))
        )

        loss_label = Text("loss after the step", font_size=24, color=self.muted)
        loss_label.move_to([4.2, -2.4, 0])
        loss_value = DecimalNumber(5.76, num_decimal_places=2, font_size=44, color=self.ink)
        loss_value.move_to([4.2, -3.05, 0])
        loss_value.add_reaction(lambda m: m.set_value(self.loss(landing_weight())))

        def on_change(control, previous, next_value):
            if not self.state["explored"]:
                self.state["explored"] = True
                self.post_message("explored", True)
            # Landing at the bottom of the curve is the goal: a rate of one half.
            if abs(next_value - 0.5) <= 0.03 and not self.state["passed"]:
                self.state["passed"] = True
                self.post_message("passed", True)

        rate.on_input(on_change)
        self.add(
            title,
            axes,
            curve,
            start,
            start_label,
            landing,
            loss_label,
            loss_value,
            rate,
            rate_label,
        )
