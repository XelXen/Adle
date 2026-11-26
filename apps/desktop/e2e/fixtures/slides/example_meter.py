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
        self.set_storyboard([[None, self.step_0], [None, self.step_1], [None, self.step_2]])

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

    def covered(self, a, b):
        across = min(a.get_right()[0], b.get_right()[0]) - max(a.get_left()[0], b.get_left()[0])
        up = min(a.get_top()[1], b.get_top()[1]) - max(a.get_bottom()[1], b.get_bottom()[1])
        if across <= 0 or up <= 0:
            return 0
        return across * up

    def stand_beside(self, key, anchor, ways, avoid=None):
        # Beside what it was put beside: on the side asked for, or, where that would take it
        # past the edge (under what already stands at the foot of the stage), on the next
        # side there is to try; and never onto what is on the stage with it: the first
        # place inside the stage that covers none of it, any side round, else the one that
        # covers least.
        mine = self.e[key]
        others = [self.e[k] for k in (avoid or [])]
        sides = list(ways)
        if len(others) > 0:
            sides = sides + [w for w in [3, 2, 0, 1] if w not in ways]
        best = None
        for way in sides:
            mine.move_to(self.beside([key], [anchor], way))
            if not self.within(mine, 6.2, 3.4):
                continue
            over = 0
            for other in others:
                over = over + self.covered(mine, other)
            if over == 0:
                return
            if best is None or over < best[0]:
                best = [over, way]
        if best is not None:
            mine.move_to(self.beside([key], [anchor], best[1]))
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

    def landing(self, keys, anchor, side, avoid=None):
        # Where what moves beside another lands: on the side asked for, or, past the edge or
        # onto what shares the stage with it, the first side round that is clear, else the
        # one that covers least; with no side inside, the one asked for, moved in.
        mine = self.group(keys)
        w = mine.width / 2
        h = mine.height / 2
        others = [self.e[k] for k in (avoid or [])]
        sides = [side, [1, 0, 3, 2][side]]
        if len(others) > 0:
            sides = sides + [s for s in [3, 2, 0, 1] if s not in sides]
        best = None
        for way in sides:
            p = self.beside(keys, anchor, way)
            if p[0] - w < -6.2 or p[0] + w > 6.2 or p[1] - h < -3.4 or p[1] + h > 3.4:
                continue
            over = 0
            for other in others:
                across = min(p[0] + w, other.get_right()[0]) - max(p[0] - w, other.get_left()[0])
                up = min(p[1] + h, other.get_top()[1]) - max(p[1] - h, other.get_bottom()[1])
                if across > 0 and up > 0:
                    over = over + across * up
            if over == 0:
                return p
            if best is None or over < best[0]:
                best = [over, p]
        if best is not None:
            return best[1]
        p = self.beside(keys, anchor, side)
        return [min(max(p[0], -6.2 + w), 6.2 - w), min(max(p[1], -3.4 + h), 3.4 - h), 0]

    def shift_to(self, keys, point):
        mine = self.group(keys)
        dx = point[0] - mine.get_center()[0]
        dy = point[1] - mine.get_center()[1]
        return [self.e[key].animate.shift(RIGHT * dx + UP * dy) for key in keys]

    def follow(self):
        for key in self.followers:
            self.e[key].update(0)

    # A picture's elements by the names its script gave them: a slide's, set as it builds;
    # none for a figure (ADR-073).
    e = None

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

    def shadow(self, word, above):
        # Once to a word, like a pointer's: copies of it, first of its parts, a little below
        # and to the right, each only a rim in the stage's color round every letter, wider and
        # fainter one after another, as clear as its letters are, with round corners: a wide
        # stroke's sharp corners would reach out in spikes. Above the lines when one runs
        # through it.
        if not self.shaded(word):
            letters = word.family_members_with_points()
            seen = letters[0].get_fill_opacity() if len(letters) > 0 else 1
            drop = word.height * 0.08
            base = word.copy().shift(RIGHT * drop * 0.75 + DOWN * drop)
            for rim in [[22, 0.15], [15, 0.22], [9, 0.32], [5, 0.5]]:
                under = base.copy()
                under.set_fill(None, 0)
                under.set_stroke(self.camera.background_color, rim[0], rim[1] * seen, True)
                for part in under.family_members_with_points():
                    part.joint_type = "ROUND"
                word.add_to_back(under)
        if above:
            word.set_z_index(1)

    def shaded(self, word):
        # Whether a word has a shadow that can be seen: its first part a rim, not clear.
        parts = word.submobjects
        if len(parts) == 0:
            return False
        return parts[0].get_stroke_width(True) > 0 and parts[0].get_stroke_opacity(True) > 0

    def shade(self, words, paths):
        # Each word over one drawn before it, or with a line through it, given a shadow; the
        # words in the order they are drawn. How many pairs of words meet, how many words a
        # line runs through, and how many of the words given a shadow have none after all.
        # Which are in whose way, the first few: [the word, the one under it or -1, the
        # line through it or -1].
        found = [0, 0, 0, []]
        for j in range(len(words)):
            over = 0
            for i in range(j):
                if self.meet(words[i], words[j]):
                    over += 1
                    if len(found[3]) < 4:
                        found[3].append([j, i, -1])
            struck = 0
            for k in range(len(paths)):
                if struck == 0 and self.struck(words[j], paths[k]):
                    struck = 1
                    if len(found[3]) < 4:
                        found[3].append([j, -1, k])
            if over + struck > 0:
                self.shadow(words[j], struck > 0)
                if not self.shaded(words[j]):
                    found[2] += 1
            found[0] += over
            found[1] += struck
        return found

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
            if not self.sides[key][2]:
                # No place clear of what stays put: a shadow under it, above the lines.
                self.shadow(label, True)
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
        # past the edge of the screen. A word over one drawn before it, or with a line through
        # it, is given a shadow now if it has none.
        words = []
        lines = []
        for m in self.mobjects:
            self.words_of(m, words)
            self.lines_of(m, lines)
        paths = []
        for line in lines:
            paths.append(self.path_of(line))
        found = self.shade(words, paths)
        outside = 0
        for m in self.mobjects:
            # A value that a step has moved is among them, and is no drawing: it stands at
            # its own number, wherever that is (a point's place at 20 on a line of meters).
            if isinstance(m, ValueTracker):
                continue
            if not self.within(m, 7.12, 4.02):
                outside += 1
        if found[0] > 0 or found[1] > 0 or outside > 0:
            said = str(found[0]) + " overlapping, " + str(found[1]) + " under a line, "
            said = said + str(outside) + " past the edge, " + str(found[2]) + " without a shadow"
            # And, on a slide, which of its elements are in whose way (ADR-073).
            for item in found[3]:
                word = self.name_of(words[item[0]])
                other = self.name_of(words[item[1]]) if item[1] >= 0 else ""
                line = self.name_of(lines[item[2]]) if item[2] >= 0 else ""
                if word != "" and other != "":
                    said = said + "; " + word + " over " + other
                if word != "" and line != "":
                    said = said + "; " + word + " under " + line
            self.post_message("layout", said[:200])

    def name_of(self, m):
        # The element of a slide something is part of, by the name its script gave it: the
        # one with the fewest parts that holds it. Nothing on a picture with no names.
        best = ""
        least = 0
        if not self.e:
            return best
        for key in self.e:
            family = self.e[key].get_family()
            held = False
            for part in family:
                if part is m:
                    held = True
            if held and (best == "" or len(family) < least):
                best = key
                least = len(family)
        return best

    def make_grid(self, key, keys, specs, rows, cols, side, row_names, col_names, name, hue):
        cells = VGroup()
        for index in range(len(keys)):
            square = Square(side_length=side, color=self.muted)
            square.set_fill(hue, 0.08)
            token = self.shown(specs[index], 28, self.ink)
            self.fit(token, side - 0.16, side - 0.16)
            token.move_to(square.get_center())
            cell = VGroup(square, token)
            self.e[keys[index]] = cell
            cells.add(cell)
        cells.arrange_in_grid(rows=rows, cols=cols, buff=0)
        marks = VGroup()
        for index in range(len(row_names)):
            marks.add(self.shown(row_names[index], 26, self.muted).next_to(self.e[keys[index * cols]], LEFT, buff=0.2))
        for index in range(len(col_names)):
            marks.add(self.shown(col_names[index], 26, self.muted).next_to(self.e[keys[index]], UP, buff=0.2))
        if name:
            lift = 0.25
            if len(col_names) > 0:
                lift = 0.75
            marks.add(self.pin(self.shown(name, 30, hue), cells, UP, lift))
        self.e[key + "/frame"] = marks
        self.e[key] = VGroup(marks, cells)

    def recell(self, key, spec, side):
        # What a cell holds becomes something else, as large as its neighbors' is.
        cell = self.e[key]
        fresh = self.shown(spec, 28, self.ink)
        self.fit(fresh, side - 0.16, side - 0.16)
        fresh.scale(cell[0].width / side)
        fresh.move_to(cell[0].get_center())
        return Transform(cell[1], fresh)

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
        self.make_grid('beats', ['beats.1.1', 'beats.1.2', 'beats.1.3', 'beats.1.4', 'beats.1.5', 'beats.1.6'], [[True, '1'], [True, '2'], [True, '3'], [True, '1'], [True, '2'], [True, '3']], 1, 6, 0.72, [], [], [False, 'claps'], self.blue)
        inner = self.lines([[False, 'Triple meter: beats in threes, the'], [False, 'first one strong.']], 34, self.ink)
        frame = SurroundingRectangle(inner, color=self.violet, buff=0.3, corner_radius=0.18)
        frame.set_fill(self.violet, 0.14)
        self.e['name'] = VGroup(frame, inner)
        self.put(['beats'], [0.0, 2.163, 12.4, 2.475], 1)
        self.put(['name'], [0.0, -1.412, 12.4, 3.975], 1)
        self.e['group'] = Brace(self.group(['beats.1.1', 'beats.1.2', 'beats.1.3']), DOWN, color=self.orange)
        self.e['group/name'] = self.pin(self.shown([False, 'one group'], 28, self.ink), self.e['group'], DOWN, 0.12)
        self.keep(self.e['group/name'])
        self.tidy()

    def step_0(self):
        self.build()
        self.play(LaggedStart(FadeIn(self.e['beats/frame']), FadeIn(self.e['beats.1.1'], shift=UP * 0.15), FadeIn(self.e['beats.1.2'], shift=UP * 0.15), FadeIn(self.e['beats.1.3'], shift=UP * 0.15), FadeIn(self.e['beats.1.4'], shift=UP * 0.15), FadeIn(self.e['beats.1.5'], shift=UP * 0.15), FadeIn(self.e['beats.1.6'], shift=UP * 0.15), lag_ratio=0.12), run_time=1.74)
        self.audit()
        self.post_message("step", 0)

    def step_1(self):
        self.play(self.tint(self.e['beats.1.1'][0], self.orange, 0.45), self.tint(self.e['beats.1.4'][0], self.orange, 0.45), run_time=0.7)
        self.play(LaggedStart(GrowFromCenter(self.e['group']), FadeIn(self.e['group/name']), lag_ratio=0.3), run_time=1.14)
        self.audit()
        self.post_message("step", 1)

    def step_2(self):
        self.play(FadeIn(self.e['name'], shift=UP * 0.15), run_time=1.02)
        self.audit()
        self.post_message("step", 2)

# adle-slide-script: eyJlbGVtZW50cyI6W3siaWQiOiJiZWF0cyIsImtpbmQiOiJncmlkIiwicm93cyI6W1siMSIsIjIiLCIzIiwiMSIsIjIiLCIzIl1dLCJwbGFjZSI6ImNlbnRlciIsImxhYmVsIjoiY2xhcHMifSx7ImlkIjoiZ3JvdXAiLCJraW5kIjoiYnJhY2UiLCJzaWRlIjoiYmVsb3ciLCJsYWJlbCI6Im9uZSBncm91cCIsImNvbG9yIjoib3JhbmdlIiwib3ZlciI6WyJiZWF0cy4xLjEiLCJiZWF0cy4xLjIiLCJiZWF0cy4xLjMiXX0seyJpZCI6Im5hbWUiLCJraW5kIjoiYm94IiwicGxhY2UiOiJib3R0b20iLCJjb2xvciI6InZpb2xldCIsInRleHQiOiJUcmlwbGUgbWV0ZXI6IGJlYXRzIGluIHRocmVlcywgdGhlIGZpcnN0IG9uZSBzdHJvbmcuIn1dLCJzdGVwcyI6W1t7InNob3ciOiJiZWF0cyJ9XSxbeyJjb2xvciI6WyJiZWF0cy4xLjEiLCJiZWF0cy4xLjQiXSwidG8iOiJvcmFuZ2UifSx7InNob3ciOiJncm91cCJ9XSxbeyJzaG93IjoibmFtZSJ9XV0sImRlc2NyaXB0aW9uIjoiU2l4IGNsYXBzIGluIGEgcm93LCBjb3VudGVkIDEsIDIsIDMsIDEsIDIsIDMsIHRoZSBvbmVzIG1hcmtlZDsgYSBicmFjZSB1bmRlciB0aGUgZmlyc3QgdGhyZWU7IHRoZW4gdGhlIG5hbWU6IHRyaXBsZSBtZXRlci4ifQ==
