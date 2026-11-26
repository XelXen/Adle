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
  it; the end-to-end suite steps through every example with none allowed;
- ``shade``, as each step ends, gives each word on the stage that lies over a word drawn
  before it, or that a line runs through, a shadow like a mouse pointer's (ADR-069): soft,
  fading out, a little below and to the right of the word, in the stage's own color (dark
  on the dark screen, light on the light one), so that it hides what lies behind the word
  and nothing else. It is copies of the word, the first of its parts, moved so, each only a
  rim round every letter, each wider and fainter than the one before: laid over each
  other they are strongest under the letters and fade to nothing, and what lies behind
  still shows through a little. They lie under every letter of the word, and a color given
  to the word later is never theirs. A word with a line through it is drawn above the
  line. A label that follows something moving is shaded while it finds no clear place.

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

#: A word's shadow, as rims in the stage's color round each letter, each a stroke as wide
#: as its first number (half of it outside the letter) and as opaque as its second. Laid
#: over each other they are about three quarters opaque under the letters and fade out
#: over about twice a letter's stroke: what lies behind still shows through a little.
#: Every rim of a word is drawn before any of its letters, so a rim never eats into the
#: next letter.
SHADOW_RIMS = ((22, 0.15), (15, 0.22), (9, 0.32), (5, 0.5))

#: How far below the word its shadow falls, as a share of the word's height; it falls three
#: quarters as far to the right, as a pointer's does.
SHADOW_DROP = 0.08

#: The methods, as scene code: methods of the scene class, indented so. ``self.pins`` and
#: ``self.still`` are set where the scene begins to build (``LAYOUT_STATE``).
LAYOUT_METHODS = f"""\
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
        x0 = word.get_left()[0] + {LINE_MARGIN_ACROSS} * w
        x1 = word.get_right()[0] - {LINE_MARGIN_ACROSS} * w
        y0 = word.get_bottom()[1] + {LINE_MARGIN_UP} * h
        y1 = word.get_top()[1] - {LINE_MARGIN_UP} * h
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
        return across > {OVERLAP} and up > {OVERLAP}

    def shadow(self, word, above):
        # Once to a word, like a pointer's: copies of it, first of its parts, a little below
        # and to the right, each only a rim in the stage's color round every letter, wider and
        # fainter one after another, as clear as its letters are, with round corners: a wide
        # stroke's sharp corners would reach out in spikes. Above the lines when one runs
        # through it.
        if not self.shaded(word):
            letters = word.family_members_with_points()
            seen = letters[0].get_fill_opacity() if len(letters) > 0 else 1
            drop = word.height * {SHADOW_DROP}
            base = word.copy().shift(RIGHT * drop * 0.75 + DOWN * drop)
            for rim in {[list(rim) for rim in SHADOW_RIMS]}:
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
            if not self.within(m, {MARGIN_HALF_WIDTH}, {MARGIN_HALF_HEIGHT}):
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
            if not self.within(m, {SCREEN_HALF_WIDTH}, {SCREEN_HALF_HEIGHT}):
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
"""

#: What the methods need, set as the scene begins to build: the labels pinned so far, and
#: the words and lines that stay put, which a label that moves with something keeps clear of.
LAYOUT_STATE = ("self.pins = []", "self.still = []", "self.still_lines = []", "self.sides = {}")
