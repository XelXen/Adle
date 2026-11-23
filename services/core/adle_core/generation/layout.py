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

Only words are held apart, and only from words. A drawing over a drawing is usually meant
(a point on its curve, a ring round a term, a shaded area), as is a label touching what it
names; two pieces of text over each other never are: neither can be read.
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

    def meet(self, a, b):
        across = min(a.get_right()[0], b.get_right()[0]) - max(a.get_left()[0], b.get_left()[0])
        up = min(a.get_top()[1], b.get_top()[1]) - max(a.get_bottom()[1], b.get_bottom()[1])
        return across > {OVERLAP} and up > {OVERLAP}

    def within(self, m, x, y):
        across = m.get_left()[0] >= -x and m.get_right()[0] <= x
        return across and m.get_bottom()[1] >= -y and m.get_top()[1] <= y

    def crowded(self, label, others):
        # A label lies past the margin, or over a word that is not its own.
        mine = self.words_of(label, [])
        for m in mine:
            if not self.within(m, {MARGIN_HALF_WIDTH}, {MARGIN_HALF_HEIGHT}):
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
        for key in self.e:
            if key not in self.followers:
                self.words_of(self.e[key], words)
        self.still = words
        for pin in self.pins:
            if self.crowded(pin[0], words):
                self.placed(pin[0], pin[1], pin[2], pin[3], words)

    def audit(self):
        # As a step ends: words over other words, and anything past the edge of the screen.
        words = []
        for m in self.mobjects:
            self.words_of(m, words)
        overlapping = 0
        for i in range(len(words)):
            for j in range(i + 1, len(words)):
                if self.meet(words[i], words[j]):
                    overlapping += 1
        outside = 0
        for m in self.mobjects:
            if not self.within(m, {SCREEN_HALF_WIDTH}, {SCREEN_HALF_HEIGHT}):
                outside += 1
        if overlapping > 0 or outside > 0:
            said = str(overlapping) + " overlapping, " + str(outside) + " past the edge"
            self.post_message("layout", said)
"""

#: What the methods need, set as the scene begins to build: the labels pinned so far, and
#: the words that stay put, which a label that moves with something keeps clear of.
LAYOUT_STATE = ("self.pins = []", "self.still = []", "self.sides = {}")
