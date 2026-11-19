from manim import *


class NeuronWeight(InteractiveScene):
    """Interactive scene: the learner changes one weight and toggles the bias."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"

    def blueprint(self):
        self.state = {"explored": False, "passed": False}

        weight = Slider(
            start=[-5, -2.7, 0],
            end=[0.5, -2.7, 0],
            value_range=(-2, 2),
            init_value=0.5,
            color=self.green,
        )
        bias_on = Switch(False).move_to([3.2, -2.7, 0])
        # Named controls are mirrored to the Adle host for keyboard/screen-reader access.
        self.adle_controls = {"weight": weight, "bias_on": bias_on}

        weight_label = Text("weight w", font_size=26, color=self.muted).next_to(weight, UP, buff=0.3)
        bias_label = Text("add bias 0.5", font_size=26, color=self.muted).next_to(bias_on, UP, buff=0.3)

        title = Text("Output z = w * x + b   (x = 1)", font_size=32, color=self.ink).to_edge(UP, buff=0.6)
        readout = DecimalNumber(0.5, num_decimal_places=2, font_size=56, color=self.ink)
        readout.move_to([3.2, 0.6, 0])

        baseline = Line([-4, -1.2, 0], [0, -1.2, 0], color=self.muted)
        bar = Rectangle(width=1.2, height=1.0, color=self.blue, fill_opacity=0.55)

        def output():
            return weight.get_value() + (0.5 if bias_on.get_value() else 0.0)

        def draw_bar(m):
            z = output()
            m.stretch_to_fit_height(max(0.04, abs(z)))
            m.set_color(self.blue if z >= 0 else self.coral)
            m.move_to([-2, -1.2 + z / 2, 0])

        bar.add_reaction(draw_bar)
        readout.add_reaction(lambda m: m.set_value(output()))

        def on_change(control, previous, next_value):
            if not self.state["explored"]:
                self.state["explored"] = True
                self.post_message("explored", True)
            if output() >= 2.0 and not self.state["passed"]:
                self.state["passed"] = True
                self.post_message("passed", True)

        weight.on_input(on_change)
        bias_on.on_input(on_change)

        self.add(title, baseline, bar, readout, weight, bias_on, weight_label, bias_label)

    def construct(self):
        note = Text("A larger weight makes this input matter more.", font_size=30, color=self.ink)
        note.to_edge(DOWN, buff=0.4)
        self.play(FadeIn(note), run_time=0.8)
        self.wait(0.6)
