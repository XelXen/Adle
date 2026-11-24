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
        return (math.exp(((-math.pow((x - p), 2.0)) / 2.0)) / math.sqrt((2.0 * math.pi)))

    def value(self, index, x, p):
        if index == 0:
            return self.curve_0(x, p)
        if index == 1:
            return self.curve_1(x, p)
        return self.curve_2(x, p)

    def build(self):
        axes = Axes(
            x_range=[-4.0, 4.0, 2.0],
            y_range=[0.0, 0.5, 0.25],
            x_length=10.0,
            y_length=4.2,
            axis_config={"color": self.muted, "include_tip": False},
        ).move_to([0, 0.55, 0])
        numbers = VGroup()
        for tick in [[-4.0, '-4'], [-2.0, '-2'], [0.0, '0'], [2.0, '2'], [4.0, '4']]:
            numbers.add(
                MathTex(tick[1], font_size=32, color=self.muted).next_to(
                    axes.c2p(tick[0], 0.0), DOWN, buff=0.18
                )
            )
        for tick in [[0.0, '0'], [0.25, '0.25'], [0.5, '0.5']]:
            if tick[0] != 0.0:
                numbers.add(
                    MathTex(tick[1], font_size=32, color=self.muted).next_to(
                        axes.c2p(-4.0, tick[0]), LEFT, buff=0.18
                    )
                )
        names = VGroup()
        x_label = 'x'
        y_label = ''
        if x_label:
            names.add(
                MathTex(x_label, font_size=34, color=self.ink).next_to(
                    axes.c2p(4.0, 0.0), RIGHT, buff=0.25
                )
            )
        if y_label:
            names.add(
                MathTex(y_label, font_size=34, color=self.ink).next_to(
                    axes.c2p(0.0, 0.5), RIGHT, buff=0.25
                )
            )
        return axes, numbers, names

    def plot(self, axes, index, p, start, end):
        hues = [self.blue, self.green, self.violet]
        if [False][index]:
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

    def rise(self, axes, spec, p, number):
        # How much the curve rises from one place to the other: a dashed run along, and
        # an arrow up by the difference, named beside it. Each rise has a hue of its own.
        hue = [self.coral, self.violet, self.green][number]
        below = self.value(spec[0], spec[1], p)
        above = self.value(spec[0], spec[2], p)
        start = axes.c2p(spec[1], below)
        corner = axes.c2p(spec[2], below)
        end = axes.c2p(spec[2], above)
        drawn = VGroup(
            DashedLine(start, corner, color=self.muted),
            Dot(color=hue, radius=0.08).move_to(start),
            Dot(color=hue, radius=0.08).move_to(end),
        )
        if abs(end[1] - corner[1]) > 0.05:
            arrow = DoubleArrow(corner, end, buff=0, color=hue, max_tip_length_to_length_ratio=0.25, max_stroke_width_to_length_ratio=12)
            drawn.add(arrow)
            if spec[3]:
                drawn.add(MathTex(spec[3], font_size=34, color=self.ink).next_to(arrow, RIGHT, buff=0.15))
        return drawn

    def area(self, axes, index, p, low, high):
        points = [axes.c2p(low, 0)]
        for step in range(61):
            x = low + (high - low) * step / 60
            points.append(axes.c2p(x, self.value(index, x, p)))
        points.append(axes.c2p(high, 0))
        return Polygon(*points, color=self.sun, fill_opacity=0.4, stroke_width=0)

    def legend(self):
        hues = [self.blue, self.green, self.violet]
        labels = ['f(x)', '']
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
        spans = [[-4.0, 4.0]]
        knob = Slider(
            start=[-3.2, -2.95, 0],
            end=[3.2, -2.95, 0],
            value_range=(-2.0, 2.0),
            init_value=0.0,
            color=self.green,
        )
        self.adle_controls = {'mu': knob}
        name = MathTex('\\mu', font_size=34, color=self.ink)
        name.next_to(knob, LEFT, buff=0.4)
        reading = DecimalNumber(0.0, num_decimal_places=2, font_size=34, color=self.ink)
        reading.next_to(knob, RIGHT, buff=0.4)
        held = {"curves": [], "area": None, "rises": []}
        shade = [0, -1.0, 1.0, '', -4.0, 4.0]
        rises = []

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
            for old in held["rises"]:
                self.remove(old)
            held["rises"] = []
            for number in range(len(rises)):
                drawn = self.rise(axes, rises[number], p, number)
                held["rises"].append(drawn)
                self.add(drawn)
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
        self.audit()

    def words_of(self, m, found):
        # Each piece of text, formula or number as one word, not its letters.
        word = isinstance(m, Text) or isinstance(m, DecimalNumber)
        if word or isinstance(m, SingleStringMathTex):
            for seen in found:
                if seen is m:
                    return found
            found.append(m)
            return found
        for part in m.submobjects:
            self.words_of(part, found)
        return found

    def lines_of(self, m, found):
        # What is drawn as a line: a line, an arrow, an axis, a curve; never a word's letters.
        word = isinstance(m, Text) or isinstance(m, DecimalNumber)
        if word or isinstance(m, SingleStringMathTex):
            return found
        if isinstance(m, Line) or isinstance(m, ParametricFunction):
            found.append(m)
            return found
        for part in m.submobjects:
            self.lines_of(part, found)
        return found

    def through(self, a, z, x0, x1, y0, y1):
        # Whether the straight piece from a to z enters the box (Liang and Barsky).
        if x0 >= x1 or y0 >= y1:
            return False
        dx = z[0] - a[0]
        dy = z[1] - a[1]
        low = 0.0
        high = 1.0
        edges = [[-dx, a[0] - x0], [dx, x1 - a[0]], [-dy, a[1] - y0]]
        for edge in edges + [[dy, y1 - a[1]]]:
            p = edge[0]
            q = edge[1]
            if p == 0:
                if q < 0:
                    return False
            else:
                u = q / p
                if p < 0:
                    if u > high:
                        return False
                    if u > low:
                        low = u
                else:
                    if u < low:
                        return False
                    if u < high:
                        high = u
        return True

    def struck(self, word, line):
        # Whether a line runs through the middle of a word.
        w = word.get_right()[0] - word.get_left()[0]
        h = word.get_top()[1] - word.get_bottom()[1]
        x0 = word.get_left()[0] + 0.2 * w
        x1 = word.get_right()[0] - 0.2 * w
        y0 = word.get_bottom()[1] + 0.25 * h
        y1 = word.get_top()[1] - 0.25 * h
        points = line.get_anchors()
        for i in range(len(points) - 1):
            if self.through(points[i], points[i + 1], x0, x1, y0, y1):
                return True
        return False

    def meet(self, a, b):
        across = min(a.get_right()[0], b.get_right()[0]) - max(a.get_left()[0], b.get_left()[0])
        up = min(a.get_top()[1], b.get_top()[1]) - max(a.get_bottom()[1], b.get_bottom()[1])
        return across > 0.06 and up > 0.06

    def within(self, m, x, y):
        across = m.get_left()[0] >= -x and m.get_right()[0] <= x
        return across and m.get_bottom()[1] >= -y and m.get_top()[1] <= y

    def crowded(self, label, others):
        # A label lies past the margin, over a word that is not its own, or under a line
        # that stays put.
        mine = self.words_of(label, [])
        for m in mine:
            if not self.within(m, 6.2, 3.4):
                return True
            for line in self.still_lines:
                if self.struck(m, line):
                    return True
            for other in others:
                ours = False
                for word in mine:
                    if word is other:
                        ours = True
                if not ours and self.meet(m, other):
                    return True
        return False

    def pin(self, label, anchor, side, buff):
        # Beside what it names, where it was asked to go; tidy may move it to another side.
        label.next_to(anchor, side, buff=buff)
        self.pins.append([label, anchor, side, buff])
        return label

    def placed(self, label, anchor, side, buff, others):
        # The first side of what it names where a label lies over nothing and inside the
        # margin; where it was asked to go when there is none.
        ways = [side, UP, DOWN, RIGHT, LEFT, UP + RIGHT, UP + LEFT, DOWN + RIGHT, DOWN + LEFT]
        for gap in [buff, buff + 0.3]:
            for way in ways:
                label.next_to(anchor, way, buff=gap)
                if not self.crowded(label, others):
                    return way
        label.next_to(anchor, side, buff=buff)
        return side

    def keep_clear(self, key, label, anchor, side, buff):
        # A label drawn again each frame beside something that moves: it keeps its side
        # while that is clear of the words that stay put, steps to the first clear side
        # when it is not, and stays there: it does not flit from side to side.
        way = self.sides.get(key, side)
        label.next_to(anchor, way, buff=buff)
        if self.crowded(label, self.still):
            self.sides[key] = self.placed(label, anchor, way, buff, self.still)
        return label

    def tidy(self):
        # Before anything is shown: every word the slide will show is in place, so each label
        # that lies over one, or past the margin, goes where it lies over none.
        words = []
        lines = []
        for key in self.e:
            if key not in self.followers:
                self.words_of(self.e[key], words)
                self.lines_of(self.e[key], lines)
        self.still = words
        self.still_lines = lines
        for pin in self.pins:
            if self.crowded(pin[0], words):
                self.placed(pin[0], pin[1], pin[2], pin[3], words)

    def audit(self):
        # As a step ends: words over other words, words a line runs through, and anything
        # past the edge of the screen.
        words = []
        lines = []
        for m in self.mobjects:
            self.words_of(m, words)
            self.lines_of(m, lines)
        overlapping = 0
        for i in range(len(words)):
            for j in range(i + 1, len(words)):
                if self.meet(words[i], words[j]):
                    overlapping += 1
        struck = 0
        for word in words:
            for line in lines:
                if self.struck(word, line):
                    struck += 1
                    break
        outside = 0
        for m in self.mobjects:
            if not self.within(m, 7.12, 4.02):
                outside += 1
        if overlapping > 0 or struck > 0 or outside > 0:
            said = str(overlapping) + " overlapping, " + str(struck) + " under a line, "
            self.post_message("layout", said + str(outside) + " past the edge")
