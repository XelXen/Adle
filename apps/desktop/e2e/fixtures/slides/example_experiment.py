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
        self.set_storyboard([[None, self.step_0], [None, self.step_1], [None, self.step_2], [None, self.step_3]])

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

    def liquid(self, points, hue, solid):
        return Polygon(*[[p[0], p[1], 0] for p in points], color=hue, fill_opacity=solid, stroke_width=0)

    def make_vessel(self, key, outline, liquid, hue, solid, grains, grain_hue, bubbles, flame, name):
        glass = VGroup()
        for index in range(len(outline) - 1):
            a = outline[index]
            b = outline[index + 1]
            glass.add(Line([a[0], a[1], 0], [b[0], b[1], 0], color=self.ink))
        self.e[key + "/body"] = glass
        self.e[key + "/liquid"] = self.liquid(liquid, hue, solid)
        whole = VGroup(self.e[key + "/liquid"], glass)
        if len(grains) > 0:
            settled = VGroup(*[Dot(color=grain_hue, radius=0.065).move_to([p[0], p[1], 0]) for p in grains])
            self.e[key + "/solid"] = settled
            whole.add(settled)
        if len(bubbles) > 0:
            gas = VGroup(*[Circle(radius=p[2], color=self.ink, stroke_width=2).move_to([p[0], p[1], 0]) for p in bubbles])
            self.e[key + "/bubbles"] = gas
            whole.add(gas)
        under = glass
        if len(flame) > 0:
            outer = Polygon(*[[p[0], p[1], 0] for p in flame], color=self.orange, fill_opacity=0.8, stroke_width=0)
            inner = Polygon(*[[p[0] * 0.5, p[1] * 0.5, 0] for p in flame], color=self.sun, fill_opacity=0.9, stroke_width=0)
            inner.move_to([outer.get_center()[0], outer.get_bottom()[1] + inner.height / 2 + 0.03, 0])
            fire = VGroup(outer, inner)
            self.e[key + "/flame"] = fire
            whole.add(fire)
            under = VGroup(glass, fire)
        if len(name) > 0:
            words = self.pin(self.lines(name, 26, self.ink), under, DOWN, 0.22)
            self.e[key + "/frame"] = words
            whole.add(words)
        self.e[key] = whole

    def refill(self, key, points, offset, tall, hue, solid):
        glass = self.e[key + "/body"]
        k = glass.height / tall
        fresh = self.liquid(points, hue, solid)
        fresh.scale(k)
        middle = glass.get_center()
        fresh.move_to([middle[0] + k * offset[0], middle[1] + k * offset[1], 0])
        return Transform(self.e[key + "/liquid"], fresh)

    def make_molecule(self, key, keys, specs, hues, places, bonds, name):
        atoms = VGroup()
        for index in range(len(keys)):
            ball = Circle(radius=0.36, color=hues[index])
            ball.set_fill(hues[index], 0.28)
            sign = self.shown(specs[index], 26, self.ink)
            self.fit(sign, 0.54, 0.44)
            ball.move_to([places[index][0], places[index][1], 0])
            sign.move_to(ball.get_center())
            atom = VGroup(ball, sign)
            self.e[keys[index]] = atom
            atoms.add(atom)
        links = VGroup()
        for bond in bonds:
            a = places[bond[1]]
            b = places[bond[2]]
            dx = b[0] - a[0]
            dy = b[1] - a[1]
            size = math.sqrt(dx * dx + dy * dy)
            if size < 0.001:
                size = 1
            ux = dx / size
            uy = dy / size
            strokes = VGroup()
            for gap in bond[3]:
                ox = -uy * gap
                oy = ux * gap
                strokes.add(Line([a[0] + ux * 0.4 + ox, a[1] + uy * 0.4 + oy, 0], [b[0] - ux * 0.4 + ox, b[1] - uy * 0.4 + oy, 0], color=self.muted))
            self.e[bond[0]] = strokes
            links.add(strokes)
        whole = VGroup(links, atoms)
        if name:
            words = self.pin(self.shown(name, 28, self.ink), atoms, DOWN, 0.28)
            self.e[key + "/frame"] = words
            whole.add(words)
        self.e[key] = whole

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
        self.make_vessel('glass', [[-0.72, 0.95], [-0.72, -0.95], [0.72, -0.95], [0.72, 0.95]], [[-0.67, 0.03], [-0.67, -0.9], [0.67, -0.9], [0.67, 0.03]], self.sun, 0.5, [[-0.58, -0.8], [-0.29, -0.8], [0.0, -0.8], [0.29, -0.8], [0.58, -0.8], [-0.58, -0.67], [-0.193, -0.67], [0.193, -0.67], [0.58, -0.67]], self.ink, [[-0.3, -0.714, 0.05], [0.21, -0.584, 0.07], [-0.06, -0.435, 0.06], [0.3, -0.286, 0.05], [-0.24, -0.137, 0.07], [0.06, -0.026, 0.05], [-0.259, 0.23, 0.06], [0.288, 0.39, 0.05]], [], [[False, 'vinegar and baking'], [False, 'soda']])
        self.make_molecule('gas', ['gas.1', 'gas.2', 'gas.3'], [[True, '\\mathrm{O}'], [True, '\\mathrm{C}'], [True, '\\mathrm{O}']], [self.teal, self.teal, self.teal], [[1.15, 0.0], [0.0, 0.0], [-1.15, 0.0]], [['gas.b1', 0, 1, [-0.075, 0.075]], ['gas.b2', 1, 2, [-0.075, 0.075]]], [False, 'carbon dioxide'])
        self.e['eq'] = MathTex(*['\\mathrm{NaHCO_3} + \\mathrm{CH_3COOH} \\rightarrow \\mathrm{CH_3COONa} + \\mathrm{H_2O} + {}', '\\color{#4FC3C9}{\\mathrm{CO_2}}'], font_size=42, color=self.ink)
        self.e['eq.1'] = self.e['eq'][1]
        self.put(['glass'], [-4.183, 1.198, 4.034, 4.405], 1)
        self.put(['gas'], [2.267, 1.198, 7.866, 4.405], 1)
        self.put(['eq'], [0.0, -2.377, 12.4, 2.045], 1)
        self.tidy()

    def step_0(self):
        self.build()
        self.play(LaggedStart(Create(self.e['glass/body']), FadeIn(self.e['glass/liquid']), FadeIn(self.e['glass/solid'], shift=DOWN * 0.3), FadeIn(self.e['glass/frame']), lag_ratio=0.3), run_time=1.38)
        self.audit()
        self.post_message("step", 0)

    def step_1(self):
        self.play(FadeIn(self.e['glass/bubbles'], shift=UP * 0.3), FadeOut(self.e['glass/solid']), run_time=1.2)
        self.audit()
        self.post_message("step", 1)

    def step_2(self):
        self.play(LaggedStart(FadeIn(self.e['gas/frame']), Create(self.e['gas.b1']), Create(self.e['gas.b2']), GrowFromCenter(self.e['gas.1']), GrowFromCenter(self.e['gas.2']), GrowFromCenter(self.e['gas.3']), lag_ratio=0.3), run_time=1.62)
        self.audit()
        self.post_message("step", 2)

    def step_3(self):
        self.play(self.ring(['gas/frame', 'gas.b1', 'gas.b2', 'gas.1', 'gas.2', 'gas.3'], self.teal), TransformFromCopy(self.group(['gas/frame', 'gas.b1', 'gas.b2', 'gas.1', 'gas.2', 'gas.3']), self.e['eq'][1]), FadeIn(self.e['eq'][0]), run_time=1.5)
        self.remove(*self.e['eq'].submobjects)
        self.add(self.e['eq'])
        self.audit()
        self.post_message("step", 3)
