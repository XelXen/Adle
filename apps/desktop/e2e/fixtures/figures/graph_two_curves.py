from manim import *
import math


class GraphFigure(Scene):
    """A graph drawn one part at a time."""

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
        return math.pow(x, 2.0)

    def curve_1(self, x, p):
        return (2.0 * x)

    def value(self, index, x, p):
        if index == 0:
            return self.curve_0(x, p)
        if index == 1:
            return self.curve_1(x, p)
        return self.curve_2(x, p)

    def build(self):
        axes = Axes(
            x_range=[-3.0, 3.0, 1.0],
            y_range=[-4.0, 12.0, 2.0],
            x_length=10.0,
            y_length=4.9,
            axis_config={"color": self.muted, "include_tip": False},
        ).move_to([0, -0.15, 0])
        numbers = VGroup()
        for tick in [[-3.0, '-3'], [-2.0, '-2'], [-1.0, '-1'], [0.0, '0'], [1.0, '1'], [2.0, '2'], [3.0, '3']]:
            numbers.add(
                MathTex(tick[1], font_size=32, color=self.muted).next_to(
                    axes.c2p(tick[0], -4.0), DOWN, buff=0.18
                )
            )
        for tick in [[-4.0, '-4'], [0.0, '0'], [4.0, '4'], [8.0, '8'], [12.0, '12']]:
            if tick[0] != -4.0:
                numbers.add(
                    MathTex(tick[1], font_size=32, color=self.muted).next_to(
                        axes.c2p(-3.0, tick[0]), LEFT, buff=0.18
                    )
                )
        names = VGroup()
        x_label = ''
        y_label = ''
        if x_label:
            names.add(
                MathTex(x_label, font_size=34, color=self.ink).next_to(
                    axes.c2p(3.0, 0.0), RIGHT, buff=0.25
                )
            )
        if y_label:
            names.add(
                MathTex(y_label, font_size=34, color=self.ink).next_to(
                    axes.c2p(0.0, 12.0), RIGHT, buff=0.25
                )
            )
        return axes, numbers, names

    def plot(self, axes, index, p, start, end):
        hues = [self.blue, self.green, self.violet]
        if [False, False][index]:
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
        labels = ['x^2', '2x']
        rows = [0, 0]
        lines = [VGroup(), VGroup()]
        counts = [0, 0]
        items = []
        for index in range(len(labels)):
            if not labels[index]:
                items.append(None)
                continue
            if index < 2:
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

    def construct(self):
        holds = [3.6, 4.0, 3.2]
        axes, numbers, names = self.build()
        spans = [[-3.0, 3.0], [-1.5, 3.0]]
        self.play(Create(axes), FadeIn(numbers), FadeIn(names), run_time=1.2)
        self.wait(holds[0])
        step = 1
        legend = self.legend()
        drawn = []
        for index in range(len(spans)):
            curve = self.plot(axes, index, 0, spans[index][0], spans[index][1])
            drawn.append(curve)
            if legend[index] is not None:
                self.play(Create(curve), FadeIn(legend[index]), run_time=1.2)
            else:
                self.play(Create(curve), run_time=1.2)
            self.wait(holds[step])
            step += 1
        shade = None
        if shade:
            area = self.area(axes, shade[0], 0, shade[1], shade[2])
            parts = [FadeIn(area)]
            if legend[len(spans)] is not None:
                parts.append(FadeIn(legend[len(spans)]))
            self.play(*parts, run_time=1.2)
            self.wait(holds[step])
            step += 1
        rises = []
        for number in range(len(rises)):
            self.play(FadeIn(self.rise(axes, rises[number], 0, number)), run_time=1.2)
            self.wait(holds[step])
            step += 1
        marks = []
        if marks:
            sides = [UP + LEFT, UP + RIGHT, UP, DOWN]
            dots = VGroup()
            for mark in marks:
                place = axes.c2p(mark[1], self.value(mark[0], mark[1], 0))
                dot = Dot(color=self.coral, radius=0.1).move_to(place)
                dots.add(dot)
                if mark[2]:
                    dots.add(MathTex(mark[2], font_size=34, color=self.ink).next_to(dot, sides[mark[3]], buff=0.15))
            self.play(LaggedStart(*[GrowFromCenter(item) for item in dots], lag_ratio=0.25), run_time=1.2)
            self.wait(holds[step])
            step += 1
        if False:
            where = ValueTracker(spans[0][0])
            runner = always_redraw(
                lambda: Dot(color=self.coral, radius=0.12).move_to(
                    axes.c2p(where.get_value(), self.value(0, where.get_value(), 0))
                )
            )
            self.add(runner)
            self.play(where.animate.set_value(spans[0][1]), run_time=2.4, rate_func=smooth)
            self.wait(holds[step])
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
        if isinstance(m, NumberLine):
            # An axis is drawn by the number line itself; its ticks are lines of their own.
            found.append(m)
        for part in m.submobjects:
            self.lines_of(part, found)
        return found

    def path_of(self, line):
        # A line as the straight pieces between its anchors, each as plain numbers, and the
        # box round them all: read once, it is cheap to look at again and again.
        points = line.get_anchors()
        pieces = []
        for i in range(len(points) - 1):
            pieces.append([points[i][0], points[i][1], points[i + 1][0], points[i + 1][1]])
        if len(pieces) == 0:
            return [[0.0, 0.0, 0.0, 0.0], []]
        box = [pieces[0][0], pieces[0][0], pieces[0][1], pieces[0][1]]
        for piece in pieces:
            box = [
                min(box[0], piece[0], piece[2]),
                max(box[1], piece[0], piece[2]),
                min(box[2], piece[1], piece[3]),
                max(box[3], piece[1], piece[3]),
            ]
        return [box, pieces]

    def through(self, piece, x0, x1, y0, y1):
        # Whether a straight piece enters the box (Liang and Barsky).
        if x0 >= x1 or y0 >= y1:
            return False
        dx = piece[2] - piece[0]
        dy = piece[3] - piece[1]
        low = 0.0
        high = 1.0
        edges = [[-dx, piece[0] - x0], [dx, x1 - piece[0]], [-dy, piece[1] - y0]]
        for edge in edges + [[dy, y1 - piece[1]]]:
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

    def struck(self, word, path):
        # Whether a line (its path) runs through the middle of a word.
        w = word.get_right()[0] - word.get_left()[0]
        h = word.get_top()[1] - word.get_bottom()[1]
        x0 = word.get_left()[0] + 0.2 * w
        x1 = word.get_right()[0] - 0.2 * w
        y0 = word.get_bottom()[1] + 0.25 * h
        y1 = word.get_top()[1] - 0.25 * h
        box = path[0]
        if box[1] < x0 or box[0] > x1 or box[3] < y0 or box[2] > y1:
            return False
        for piece in path[1]:
            if self.through(piece, x0, x1, y0, y1):
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
            for path in self.still_lines:
                if self.struck(m, path):
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
        # The first side of what it names, and how far from it, where a label lies over
        # nothing and inside the margin; where it was asked to go when there is none. It
        # says which, how far, and whether that place is clear.
        ways = [side, UP, DOWN, RIGHT, LEFT, UP + RIGHT, UP + LEFT, DOWN + RIGHT, DOWN + LEFT]
        for gap in [buff, buff + 0.3]:
            for way in ways:
                label.next_to(anchor, way, buff=gap)
                if not self.crowded(label, others):
                    return [way, gap, True]
        label.next_to(anchor, side, buff=buff)
        return [side, buff, False]

    def keep_clear(self, key, label, anchor, side, buff):
        # A label drawn again each frame beside something that moves: it keeps its place
        # while that is clear of the words and lines that stay put, steps to the first clear
        # place when it is not, and stays there: it does not flit from side to side. Where no
        # place was clear it looks again only once what it names has moved: a search on
        # every frame would cost the picture its frames.
        kept = self.sides.get(key)
        if kept is None:
            label.next_to(anchor, side, buff=buff)
        else:
            label.next_to(anchor, kept[0], buff=kept[1])
        if self.crowded(label, self.still):
            here = anchor.get_center()
            if kept is None or kept[2] or abs(here[0] - kept[3]) + abs(here[1] - kept[4]) > 0.2:
                way = side if kept is None else kept[0]
                found = self.placed(label, anchor, way, buff, self.still)
                self.sides[key] = [found[0], found[1], found[2], here[0], here[1]]
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
        paths = []
        for line in lines:
            paths.append(self.path_of(line))
        self.still_lines = paths
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
        paths = []
        for line in lines:
            paths.append(self.path_of(line))
        struck = 0
        for word in words:
            for path in paths:
                if self.struck(word, path):
                    struck += 1
                    break
        outside = 0
        for m in self.mobjects:
            if not self.within(m, 7.12, 4.02):
                outside += 1
        if overlapping > 0 or struck > 0 or outside > 0:
            said = str(overlapping) + " overlapping, " + str(struck) + " under a line, "
            self.post_message("layout", said + str(outside) + " past the edge")
