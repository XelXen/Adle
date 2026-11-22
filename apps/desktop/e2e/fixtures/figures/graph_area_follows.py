from manim import *
import math


class GraphFigure(InteractiveScene):
    """A graph the learner changes with a slider."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"
        self.sun = "#E9BE5A" if dark else "#F2C14E"
        self.violet = "#A694E3" if dark else "#9178D7"

    def curve_0(self, x, p):
        return ((1.0 if (x >= 0.0) else 0.0) * math.exp((-x)))

    def value(self, index, x, p):
        if index == 0:
            return self.curve_0(x, p)
        if index == 1:
            return self.curve_1(x, p)
        return self.curve_2(x, p)

    def build(self):
        axes = Axes(
            x_range=[-1.0, 5.0, 1.0],
            y_range=[0.0, 1.2, 0.2],
            x_length=10.0,
            y_length=4.2,
            axis_config={"color": self.muted, "include_tip": False},
        ).move_to([0, 0.55, 0])
        numbers = VGroup()
        for tick in [[-1.0, '-1'], [0.0, '0'], [1.0, '1'], [2.0, '2'], [3.0, '3'], [4.0, '4'], [5.0, '5']]:
            numbers.add(
                MathTex(tick[1], font_size=32, color=self.muted).next_to(
                    axes.c2p(tick[0], 0.0), DOWN, buff=0.18
                )
            )
        for tick in [[0.0, '0'], [0.4, '0.4'], [0.8, '0.8'], [1.2, '1.2']]:
            if tick[0] != 0.0:
                numbers.add(
                    MathTex(tick[1], font_size=32, color=self.muted).next_to(
                        axes.c2p(-1.0, tick[0]), LEFT, buff=0.18
                    )
                )
        names = VGroup()
        x_label = 'x'
        y_label = ''
        if x_label:
            names.add(
                MathTex(x_label, font_size=34, color=self.ink).next_to(
                    axes.c2p(5.0, 0.0), RIGHT, buff=0.25
                )
            )
        if y_label:
            names.add(
                MathTex(y_label, font_size=34, color=self.ink).next_to(
                    axes.c2p(0.0, 1.2), RIGHT, buff=0.25
                )
            )
        return axes, numbers, names

    def plot(self, axes, index, p, start, end):
        hues = [self.blue, self.green, self.violet]
        if [True][index]:
            # A curve in pieces is drawn in short straight steps: smoothed, it would ripple
            # where it jumps.
            return axes.plot(
                lambda x: self.value(index, x, p),
                x_range=[start, end, (end - start) / 400],
                color=hues[index],
                use_smoothing=False,
            )
        return axes.plot(
            lambda x: self.value(index, x, p),
            x_range=[start, end],
            color=hues[index],
        )

    def area(self, axes, index, p, low, high):
        points = [axes.c2p(low, 0)]
        for step in range(61):
            x = low + (high - low) * step / 60
            points.append(axes.c2p(x, self.value(index, x, p)))
        points.append(axes.c2p(high, 0))
        return Polygon(*points, color=self.sun, fill_opacity=0.4, stroke_width=0)

    def legend(self):
        hues = [self.blue, self.green, self.violet]
        labels = ['f(x)', 'F(a)']
        rows = [0, 0]
        lines = [VGroup(), VGroup()]
        counts = [0, 0]
        items = []
        for index in range(len(labels)):
            if not labels[index]:
                items.append(None)
                continue
            if index < 1:
                key = Line([0, 0, 0], [0.5, 0, 0], color=hues[index])
                key.set_stroke(width=6)
            else:
                key = Rectangle(width=0.5, height=0.3, color=self.sun, fill_opacity=0.4, stroke_width=0)
            text = MathTex(labels[index], font_size=34, color=self.ink).next_to(key, RIGHT, buff=0.2)
            item = VGroup(key, text)
            items.append(item)
            lines[rows[index]].add(item)
            counts[rows[index]] += 1
        for row in range(2):
            if counts[row] > 0:
                lines[row].arrange(RIGHT, buff=0.7)
                if lines[row].width > 12.4:
                    lines[row].scale(12.4 / lines[row].width)
                lines[row].move_to([0, 3.25 - 0.58 * row, 0])
        return items

    def blueprint(self):
        self.state = {"explored": False}
        axes, numbers, names = self.build()
        spans = [[-1.0, 5.0]]
        knob = Slider(
            start=[-3.2, -2.95, 0],
            end=[3.2, -2.95, 0],
            value_range=(0.0, 4.0),
            init_value=1.0,
            color=self.green,
        )
        self.adle_controls = {'a': knob}
        name = MathTex('a', font_size=34, color=self.ink)
        name.next_to(knob, LEFT, buff=0.4)
        reading = DecimalNumber(1.0, num_decimal_places=2, font_size=34, color=self.ink)
        reading.next_to(knob, RIGHT, buff=0.4)
        held = {"curves": [], "area": None}
        shade = [0, 0.0, None, 'F(a)', -1.0, 5.0]

        def draw():
            p = knob.get_value()
            for old in held["curves"]:
                self.remove(old)
            held["curves"] = []
            if held["area"] is not None:
                self.remove(held["area"])
                held["area"] = None
            if shade:
                # An end that is None follows the slider.
                low = p if shade[1] is None else shade[1]
                high = p if shade[2] is None else shade[2]
                ends = [low, high] if low <= high else [high, low]
                ends[0] = ends[0] if ends[0] >= shade[4] else shade[4]
                ends[1] = ends[1] if ends[1] <= shade[5] else shade[5]
                if ends[1] - ends[0] > 0.001:
                    held["area"] = self.area(axes, shade[0], p, ends[0], ends[1])
                    self.add(held["area"])
            for index in range(len(spans)):
                curve = self.plot(axes, index, p, spans[index][0], spans[index][1])
                held["curves"].append(curve)
                self.add(curve)
            reading.set_value(p)

        def moved(control, previous, value):
            draw()
            if not self.state["explored"]:
                self.state["explored"] = True
                self.post_message("explored", True)

        knob.on_input(moved)
        self.add(axes, numbers, names, knob, name, reading)
        for item in self.legend():
            if item is not None:
                self.add(item)
        draw()
