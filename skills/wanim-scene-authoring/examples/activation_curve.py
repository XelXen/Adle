from manim import *


class ActivationCurve(InteractiveScene):
    """Interactive graph: slide the input z and read the sigmoid output off the curve."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"

    def sigmoid(self, z):
        return 1 / (1 + np.exp(-z))

    def blueprint(self):
        self.state = {"explored": False}

        axes = Axes(
            x_range=[-6, 6, 2],
            y_range=[0, 1, 0.5],
            x_length=8,
            y_length=3.2,
            axis_config={"color": self.muted, "include_tip": False},
        ).shift(UP * 0.5)
        curve = axes.plot(lambda z: self.sigmoid(z), x_range=[-6, 6], color=self.blue)
        title = Text("Sigmoid squashes any input into 0 to 1", font_size=30, color=self.ink)
        title.to_edge(UP, buff=0.45)
        formula = MathTex(r"\sigma(z) = \frac{1}{1 + e^{-z}}", font_size=34, color=self.ink)
        formula.move_to(axes.c2p(-3.6, 0.82))

        z_input = Slider(
            start=[-4, -2.9, 0],
            end=[4, -2.9, 0],
            value_range=(-6, 6),
            init_value=0,
            color=self.green,
        )
        self.adle_controls = {"z": z_input}
        z_label = Text("input z", font_size=24, color=self.muted).next_to(z_input, UP, buff=0.25)

        dot = Dot(color=self.coral, radius=0.1)
        dot.add_reaction(lambda m: m.move_to(axes.c2p(z_input.get_value(), self.sigmoid(z_input.get_value()))))
        readout = DecimalNumber(0.5, num_decimal_places=2, font_size=40, color=self.ink)
        readout.move_to(axes.c2p(4.4, 0.25))
        readout.add_reaction(lambda m: m.set_value(self.sigmoid(z_input.get_value())))
        readout_label = Text("output", font_size=22, color=self.muted).next_to(readout, UP, buff=0.2)

        def on_change(control, previous, next_value):
            if not self.state["explored"]:
                self.state["explored"] = True
                self.post_message("explored", True)

        z_input.on_input(on_change)
        self.add(axes, curve, title, formula, dot, readout, readout_label, z_input, z_label)

    def construct(self):
        tracker = ValueTracker(-6)
        axes = Axes(
            x_range=[-6, 6, 2],
            y_range=[0, 1, 0.5],
            x_length=8,
            y_length=3.2,
            axis_config={"color": self.muted, "include_tip": False},
        ).shift(UP * 0.5)
        sweep = always_redraw(
            lambda: Dot(color=self.green, radius=0.12).move_to(
                axes.c2p(tracker.get_value(), self.sigmoid(tracker.get_value()))
            )
        )
        note = Text("Large negative inputs give 0; large positive inputs give 1.", font_size=26, color=self.ink)
        note.to_edge(DOWN, buff=0.5)
        self.add(sweep)
        self.play(FadeIn(note), run_time=0.6)
        self.play(tracker.animate.set_value(6), run_time=2.0, rate_func=smooth)
        self.wait(0.4)
