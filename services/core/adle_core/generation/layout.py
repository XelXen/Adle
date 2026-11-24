"""What a picture Adle writes does about its own words (ADR-055).

A slide or a figure is drawn by a scene the core writes from a lesson's data. Its words go
where the layout puts them, and its labels beside what they name; how large each is drawn
only the player knows, and there a label can lie over another word, or past the edge of
the screen. These methods, written into every such scene, look at the picture as drawn:

- ``pin`` puts a label beside what it names and remembers where it was asked to go;
- ``tidy``, at the end of ``build``, moves each pinned label that lies over other words or
  past the edge to the first side of what it names where it does neither. That is before
  anything is shown, so nothing is seen to move;
- ``audit``, as each step ends, says how many words lie over other words and how many
  things lie past the edge (``post_message("layout", ...)``). Nothing in the app acts on
  it; the end-to-end suite steps through every example with none allowed.

Words are held apart from words, and from the lines drawn through them: a line, an arrow,
an axis or a curve that runs through the middle of a word. A drawing over a drawing is
usually meant (a point on its curve, a ring round a term, a shaded area), as is a label
touching what it names or a line that only grazes a word; two pieces of text over each
other, or a line struck through one, never are: they cannot be read.
"""

from __future__ import annotations

#: Half the width and the height of what the player shows, in scene units, with a hair to
#: spare for rounding: past these, part of the picture is cut off.
SCREEN_HALF_WIDTH = 7.12
SCREEN_HALF_HEIGHT = 4.02

#: How far into the screen a moved label is kept: the margin the slides' own ``keep`` keeps.
MARGIN_HALF_WIDTH = 6.2
MARGIN_HALF_HEIGHT = 3.4

#: How much two words may share, across and up, before they are said to overlap. Letters
#: set side by side touch at their edges; a word over another shares far more.
OVERLAP = 0.06

#: The middle of a word that a line may not run through, as what is left of its box when
#: this much of its width is taken off each side, and of its height off top and bottom. A
#: line beside a word, or one that grazes the tops of its letters, does not count.
LINE_MARGIN_ACROSS = 0.2
LINE_MARGIN_UP = 0.25

#: The methods, as scene code: methods of the scene class, indented so. ``self.pins`` and
#: ``self.still`` are set where the scene begins to build (``LAYOUT_STATE``).
LAYOUT_METHODS = f"""\
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
        x0 = word.get_left()[0] + {LINE_MARGIN_ACROSS} * w
        x1 = word.get_right()[0] - {LINE_MARGIN_ACROSS} * w
        y0 = word.get_bottom()[1] + {LINE_MARGIN_UP} * h
        y1 = word.get_top()[1] - {LINE_MARGIN_UP} * h
        points = line.get_anchors()
        for i in range(len(points) - 1):
            if self.through(points[i], points[i + 1], x0, x1, y0, y1):
                return True
        return False

    def meet(self, a, b):
        across = min(a.get_right()[0], b.get_right()[0]) - max(a.get_left()[0], b.get_left()[0])
        up = min(a.get_top()[1], b.get_top()[1]) - max(a.get_bottom()[1], b.get_bottom()[1])
        return across > {OVERLAP} and up > {OVERLAP}

    def within(self, m, x, y):
        across = m.get_left()[0] >= -x and m.get_right()[0] <= x
        return across and m.get_bottom()[1] >= -y and m.get_top()[1] <= y

    def crowded(self, label, others):
        # A label lies past the margin, over a word that is not its own, or under a line
        # that stays put.
        mine = self.words_of(label, [])
        for m in mine:
            if not self.within(m, {MARGIN_HALF_WIDTH}, {MARGIN_HALF_HEIGHT}):
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
            if not self.within(m, {SCREEN_HALF_WIDTH}, {SCREEN_HALF_HEIGHT}):
                outside += 1
        if overlapping > 0 or struck > 0 or outside > 0:
            said = str(overlapping) + " overlapping, " + str(struck) + " under a line, "
            self.post_message("layout", said + str(outside) + " past the edge")
"""

#: What the methods need, set as the scene begins to build: the labels pinned so far, and
#: the words and lines that stay put, which a label that moves with something keeps clear of.
LAYOUT_STATE = ("self.pins = []", "self.still = []", "self.still_lines = []", "self.sides = {}")
