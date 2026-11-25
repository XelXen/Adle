from manim import *
import math


class Slide(InteractiveScene):
    """A picture drawn a step at a time, as the narration reaches each."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"
        self.sun = "#E9BE5A" if dark else "#F2C14E"
        self.violet = "#A694E3" if dark else "#9178D7"
        self.teal = "#4FC3C9" if dark else "#2B9EA5"
        self.orange = "#F0A45D" if dark else "#E8893A"
        self.e = {}
        self.set_storyboard([[None, self.step_0], [None, self.step_1], [None, self.step_2], [None, self.step_3], [None, self.step_4]])

    def fit(self, m, w, h):
        if m.width > w:
            m.scale_to_fit_width(w)
        if m.height > h:
            m.scale_to_fit_height(h)
        return m

    def put(self, keys, box, cols):
        group = VGroup(*[self.e[key] for key in keys])
        if cols > 1:
            group.arrange_in_grid(rows=(len(keys) + cols - 1) // cols, cols=cols, buff=0.45)
        elif len(keys) > 1:
            group.arrange(DOWN, buff=0.45)
        self.fit(group, box[2], box[3])
        grow = min(1.35, 0.75 * box[2] / max(group.width, 0.01), 0.75 * box[3] / max(group.height, 0.01))
        if grow > 1:
            group.scale(grow)
        group.move_to([box[0], box[1], 0])

    def keep(self, m):
        # Inside the stage: smaller if it is larger, moved in where it sticks out.
        self.fit(m, 12.4, 6.8)
        dx = 0
        dy = 0
        if m.get_right()[0] > 6.2:
            dx = 6.2 - m.get_right()[0]
        if m.get_left()[0] < -6.2:
            dx = -6.2 - m.get_left()[0]
        if m.get_top()[1] > 3.4:
            dy = 3.4 - m.get_top()[1]
        if m.get_bottom()[1] < -3.4:
            dy = -3.4 - m.get_bottom()[1]
        m.shift(RIGHT * dx + UP * dy)

    def group(self, keys):
        return VGroup(*[self.e[key] for key in keys])

    def beside(self, keys, anchor, side):
        # Where a group goes beside another: 0 below it, 1 above, 2 left of it, 3 right.
        mine = self.group(keys)
        other = self.group(anchor)
        if side == 0:
            return [other.get_center()[0], other.get_bottom()[1] - 0.55 - mine.height / 2, 0]
        if side == 1:
            return [other.get_center()[0], other.get_top()[1] + 0.55 + mine.height / 2, 0]
        if side == 2:
            return [other.get_left()[0] - 0.55 - mine.width / 2, other.get_center()[1], 0]
        return [other.get_right()[0] + 0.55 + mine.width / 2, other.get_center()[1], 0]

    def stand_beside(self, key, anchor, ways):
        # Beside what it was put beside: on the side asked for, or, where that would take it
        # past the edge (under what already stands at the foot of the stage), on the next
        # side there is to try.
        mine = self.e[key]
        for way in ways:
            mine.move_to(self.beside([key], [anchor], way))
            if self.within(mine, 6.2, 3.4):
                return
        mine.move_to(self.beside([key], [anchor], ways[0]))
        self.keep(mine)

    def shown(self, spec, size, hue):
        if spec[0]:
            return MathTex(spec[1], font_size=round(size * 1.45), color=hue)
        return Text(spec[1], font_size=size, color=hue)

    def lines(self, specs, size, hue):
        made = VGroup(*[self.shown(spec, size, hue) for spec in specs])
        if len(specs) > 1:
            made.arrange(DOWN, buff=0.14)
        return made

    def unmark(self):
        if len(self.rings) > 0:
            self.play(*[FadeOut(ring) for ring in self.rings], run_time=0.3)
        self.rings = []

    def ring(self, keys, hue):
        ring = SurroundingRectangle(self.group(keys), color=hue, buff=0.12, corner_radius=0.12)
        self.rings.append(ring)
        return Create(ring)

    def tint(self, m, hue, fill):
        look = m.copy()
        look.set_color(hue)
        if fill > 0:
            look.set_fill(hue, fill)
        return Transform(m, look)

    def shift_to(self, keys, point):
        mine = self.group(keys)
        dx = point[0] - mine.get_center()[0]
        dy = point[1] - mine.get_center()[1]
        return [self.e[key].animate.shift(RIGHT * dx + UP * dy) for key in keys]

    def follow(self):
        for key in self.followers:
            self.e[key].update(0)

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
            # A value that a step has moved is among them, and is no drawing: it stands at
            # its own number, wherever that is (a point's place at 20 on a line of meters).
            if isinstance(m, ValueTracker):
                continue
            if not self.within(m, 7.12, 4.02):
                outside += 1
        if overlapping > 0 or struck > 0 or outside > 0:
            said = str(overlapping) + " overlapping, " + str(struck) + " under a line, "
            self.post_message("layout", said + str(outside) + " past the edge")

    def plot(self, axes, index, a, b, hue, pieces):
        p = self.amount.get_value()
        if pieces:
            return axes.plot(lambda x: self.value(index, x, p), x_range=[a, b, (b - a) / 400], color=hue, use_smoothing=False)
        return axes.plot(lambda x: self.value(index, x, p), x_range=[a, b], color=hue)

    def make_curve(self, key, axes, index, a, b, hue, pieces, follows):
        if follows:
            self.e[key] = always_redraw(lambda: self.plot(axes, index, a, b, hue, pieces))
            self.followers.append(key)
        else:
            self.e[key] = self.plot(axes, index, a, b, hue, pieces)

    def spot(self, on, index, x, a, b):
        if index < 0:
            return self.e[on].n2p(x)
        if x < a:
            x = a
        if x > b:
            x = b
        return self.ax[on].c2p(x, self.value(index, x, self.amount.get_value()))

    def marker(self, key, on, index, tracker, a, b, name, hue):
        dot = Dot(color=hue, radius=0.1).move_to(self.spot(on, index, tracker.get_value(), a, b))
        if name:
            label = self.keep_clear(key, self.shown(name, 26, self.ink), dot, UP + RIGHT, 0.1)
            return VGroup(dot, label)
        return VGroup(dot)

    def make_point(self, key, on, index, x, a, b, name, hue):
        tracker = self.amount
        if x is not None:
            tracker = ValueTracker(x)
        self.trackers[key] = tracker
        self.e[key] = always_redraw(lambda: self.marker(key, on, index, tracker, a, b, name, hue))
        self.followers.append(key)

    def make_number_line(self, key, xr, length, ticks, name):
        line = NumberLine(x_range=xr, length=length, include_numbers=False, color=self.muted)
        marks = VGroup()
        for tick in ticks:
            marks.add(MathTex(tick[1], font_size=36, color=self.muted).next_to(line.n2p(tick[0]), DOWN, buff=0.2))
        if name:
            marks.add(self.pin(self.shown(name, 28, self.ink), line, RIGHT, 0.3))
        self.e[key + "/body"] = line
        self.e[key + "/frame"] = marks
        self.e[key] = VGroup(line, marks)

    def build(self):
        self.e = {}
        self.ax = {}
        self.trackers = {}
        self.rings = []
        self.followers = []
        self.pins = []
        self.still = []
        self.still_lines = []
        self.sides = {}
        self.amount = ValueTracker(0.0)
        self.make_number_line('drop', [0.0, 20.0, 5.0], 9.5, [[0.0, '0'], [5.0, '5'], [10.0, '10'], [15.0, '15'], [20.0, '20']], [False, 'meters fallen'])
        number = DecimalNumber(0.0, num_decimal_places=0, font_size=58, color=self.blue)
        self.e['t/value'] = number
        title = self.shown([False, 'seconds'], 36, self.ink)
        equals = MathTex("=", font_size=52, color=self.ink)
        self.e['t'] = VGroup(title, equals, number).arrange(RIGHT, buff=0.2)
        number = DecimalNumber(0.0, num_decimal_places=0, font_size=58, color=self.orange)
        self.e['d/value'] = number
        title = self.shown([False, 'meters'], 36, self.ink)
        equals = MathTex("=", font_size=52, color=self.ink)
        self.e['d'] = VGroup(title, equals, number).arrange(RIGHT, buff=0.2)
        self.e['case'] = MathTex(*['\\color{#F0A45D}{20}', '= 5 \\times', '\\color{#7BA4EE}{2}', '^2'], font_size=52, color=self.ink)
        self.e['case.1'] = self.e['case'][0]
        self.e['case.2'] = self.e['case'][2]
        self.e['law'] = MathTex(*['\\color{#F0A45D}{d}', '= 5 \\times', '\\color{#7BA4EE}{t}', '^2'], font_size=52, color=self.ink)
        self.e['law.1'] = self.e['law'][0]
        self.e['law.2'] = self.e['law'][2]
        self.put(['drop'], [0.0, 2.212, 12.4, 2.376], 1)
        self.put(['t', 'd'], [-4.328, -1.363, 3.745, 4.074], 1)
        self.put(['case'], [2.122, -1.363, 8.155, 4.074], 1)
        self.fit(self.e['law'], 8.155, 4.074)
        self.e['law'].move_to(self.e['case'].get_center())
        self.make_point('ball', 'drop/body', -1, 0.0, 0.0, 20.0, None, self.orange)
        self.tidy()

    def step_0(self):
        self.build()
        self.play(LaggedStart(Create(self.e['drop/body']), FadeIn(self.e['drop/frame']), FadeIn(self.e['ball']), FadeIn(self.e['t'], shift=UP * 0.15), FadeIn(self.e['d'], shift=UP * 0.15), lag_ratio=0.3), run_time=1.5)
        self.audit()
        self.post_message("step", 0)

    def step_1(self):
        self.play(self.trackers['ball'].animate.set_value(5.0), run_time=1.6, rate_func=smooth)
        self.play(ChangeDecimalToValue(self.e['t/value'], 1.0), run_time=1.2)
        self.play(ChangeDecimalToValue(self.e['d/value'], 5.0), run_time=1.2)
        self.audit()
        self.post_message("step", 1)

    def step_2(self):
        self.play(self.trackers['ball'].animate.set_value(20.0), run_time=1.6, rate_func=smooth)
        self.play(ChangeDecimalToValue(self.e['t/value'], 2.0), run_time=1.2)
        self.play(ChangeDecimalToValue(self.e['d/value'], 20.0), run_time=1.2)
        self.audit()
        self.post_message("step", 2)

    def step_3(self):
        self.play(self.ring(['d'], self.orange), self.ring(['t'], self.blue), TransformFromCopy(self.e['d'], self.e['case'][0]), TransformFromCopy(self.e['t'], self.e['case'][2]), FadeIn(self.e['case'][1]), FadeIn(self.e['case'][3]), run_time=1.5)
        self.remove(*self.e['case'].submobjects)
        self.add(self.e['case'])
        self.audit()
        self.post_message("step", 3)

    def step_4(self):
        self.unmark()
        self.play(TransformMatchingTex(self.e['case'], self.e['law']), run_time=1.4)
        self.audit()
        self.post_message("step", 4)

# adle-slide-script: eyJlbGVtZW50cyI6W3siaWQiOiJkcm9wIiwia2luZCI6Im51bWJlcl9saW5lIiwieCI6WzAsMjBdLCJwbGFjZSI6InRvcCIsImxhYmVsIjoibWV0ZXJzIGZhbGxlbiJ9LHsiaWQiOiJiYWxsIiwia2luZCI6InBvaW50Iiwib24iOiJkcm9wIiwieCI6MCwiY29sb3IiOiJvcmFuZ2UifSx7ImlkIjoidCIsImtpbmQiOiJudW1iZXIiLCJ2YWx1ZSI6MCwiZGVjaW1hbHMiOjAsImxhYmVsIjoic2Vjb25kcyIsInBsYWNlIjoibGVmdCIsImNvbG9yIjoiYmx1ZSJ9LHsiaWQiOiJkIiwia2luZCI6Im51bWJlciIsInZhbHVlIjowLCJkZWNpbWFscyI6MCwibGFiZWwiOiJtZXRlcnMiLCJwbGFjZSI6ImxlZnQiLCJjb2xvciI6Im9yYW5nZSJ9LHsiaWQiOiJjYXNlIiwia2luZCI6Im1hdGgiLCJwbGFjZSI6InJpZ2h0IiwidGV4Ijoie3tcXGNvbG9ye29yYW5nZX17MjB9fX0gPSA1IFxcdGltZXMge3tcXGNvbG9ye2JsdWV9ezJ9fX0gXjIifSx7ImlkIjoibGF3Iiwia2luZCI6Im1hdGgiLCJwbGFjZSI6InJpZ2h0IiwidGV4Ijoie3tcXGNvbG9ye29yYW5nZX17ZH19fSA9IDUgXFx0aW1lcyB7e1xcY29sb3J7Ymx1ZX17dH19fSBeMiJ9XSwic3RlcHMiOltbeyJzaG93IjpbImRyb3AiLCJiYWxsIiwidCIsImQiXX1dLFt7InNldCI6ImJhbGwiLCJ0byI6NX0seyJzZXQiOiJ0IiwidG8iOjF9LHsic2V0IjoiZCIsInRvIjo1fV0sW3sic2V0IjoiYmFsbCIsInRvIjoyMH0seyJzZXQiOiJ0IiwidG8iOjJ9LHsic2V0IjoiZCIsInRvIjoyMH1dLFt7InNob3ciOiJjYXNlIiwiZnJvbSI6WyJkIiwidCJdfV0sW3sidHJhbnNmb3JtIjoiY2FzZSIsImludG8iOiJsYXcifV1dLCJkZXNjcmlwdGlvbiI6IkEgYmFsbCBvbiBhIGxpbmUgb2YgbWV0ZXJzIGZhbGxlbjogYXQgMCwgYXQgNSBhZnRlciBvbmUgc2Vjb25kLCBhdCAyMCBhZnRlciB0d28uIFRoZW4gJDIwID0gNSBcXHRpbWVzIDJeMiQsIHRoZW4gJGQgPSA1IFxcdGltZXMgdF4yJC4ifQ==
