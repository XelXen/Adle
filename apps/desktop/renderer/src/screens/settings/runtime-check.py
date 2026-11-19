from manim import *


class RuntimeCheck(InteractiveScene):
    """Bundled check scene: proves that animation, text, maths and interaction all work."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"

    def blueprint(self):
        self.state = {"explored": False}

        size = Slider(
            start=[-3.5, -2.6, 0],
            end=[3.5, -2.6, 0],
            value_range=(0.5, 2.5),
            init_value=1.2,
            color=self.green,
        )
        self.adle_controls = {"size": size}

        title = Text("Drag the slider to resize the circle", font_size=32, color=self.ink)
        title.to_edge(UP, buff=0.7)
        formula = MathTex(r"A = \pi r^2", font_size=44, color=self.muted).move_to([4.2, 0.4, 0])

        circle = Circle(radius=1.2, color=self.blue, fill_opacity=0.3).move_to([-1.2, 0.2, 0])
        circle.add_reaction(lambda m: m.set_width(2 * size.get_value()))

        def on_change(control, previous, next_value):
            if not self.state["explored"]:
                self.state["explored"] = True
                self.post_message("explored", True)

        size.on_input(on_change)
        self.add(title, circle, formula, size)
