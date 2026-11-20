from manim import *


class CurveByStroke(Scene):
    """A plotted curve made visible the right way: by its stroke.

    The straight line from the curve's first point to its last encloses an area with it.
    Whether that area is painted is what the end-to-end suite looks at.
    """

    def construct(self):
        axes = Axes(
            x_range=[-10, 10, 5],
            y_range=[0, 1, 0.5],
            x_length=8.0,
            y_length=4.0,
            axis_config={"color": "#5F6E65", "include_tip": False},
        )
        curve = axes.plot(lambda z: 1 / (1 + np.exp(-z)), x_range=[-10, 10], color="#5B8DE6")
        curve.set_stroke(opacity=1)
        self.add(axes, curve)
        self.wait(0.4)
