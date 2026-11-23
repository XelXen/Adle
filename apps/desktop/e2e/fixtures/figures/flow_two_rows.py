from manim import *
import math


class FlowFigure(Scene):
    """Steps that follow one another."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"
        self.sun = "#E9BE5A" if dark else "#F2C14E"
        self.violet = "#A694E3" if dark else "#9178D7"

    def construct(self):
        holds = [1.88, 1.88, 1.88, 1.88, 1.88]
        places = [[-3.667, 0.9], [0.0, 0.9], [3.667, 0.9], [3.667, -1.3], [0.0, -1.3]]
        names = [['Read'], ['Plan'], ['Write'], ['Check'], ['Revise']]
        boxes = []
        for index in range(len(names)):
            text = VGroup(*[Text(line, font_size=26, color=self.ink) for line in names[index]])
            text.arrange(DOWN, buff=0.12)
            text.move_to([places[index][0], places[index][1], 0])
            frame = SurroundingRectangle(text, color=self.muted, buff=0.3)
            boxes.append(VGroup(frame, text))
        for index in range(len(boxes)):
            parts = [FadeIn(boxes[index], shift=RIGHT * 0.2)]
            if index > 0:
                before = boxes[index - 1][0]
                here = boxes[index][0]
                if abs(places[index][1] - places[index - 1][1]) > 0.1:
                    ends = [before.get_bottom(), here.get_top()]
                elif places[index][0] > places[index - 1][0]:
                    ends = [before.get_right(), here.get_left()]
                else:
                    ends = [before.get_left(), here.get_right()]
                # As thick, and with as large a head, however short the gap is.
                arrow = Arrow(ends[0], ends[1], buff=0.1, color=self.green, max_tip_length_to_length_ratio=0.45, max_stroke_width_to_length_ratio=12)
                parts.append(GrowArrow(arrow))
                self.play(boxes[index - 1][0].animate.set_stroke(color=self.muted), run_time=0.3)
            self.play(*parts, run_time=1.0)
            self.play(boxes[index][0].animate.set_stroke(color=self.green), run_time=0.3)
            self.wait(holds[index])
        if False:
            first = boxes[0][0]
            last = boxes[len(boxes) - 1][0]
            # One level under both boxes, however tall each is.
            low = first.get_bottom()[1]
            if last.get_bottom()[1] < low:
                low = last.get_bottom()[1]
            low = low - 0.9
            corner = [last.get_bottom()[0], low, 0]
            turn = [first.get_bottom()[0], low, 0]
            path = VGroup(
                Line(last.get_bottom(), corner, color=self.green),
                Line(corner, turn, color=self.green),
            )
            path.set_stroke(width=6)
            back = Arrow(turn, first.get_bottom(), buff=0.05, color=self.green, max_tip_length_to_length_ratio=0.45, max_stroke_width_to_length_ratio=12)
            self.play(Create(path), GrowArrow(back), run_time=1.2)
            self.wait(holds[len(holds) - 1])
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

    def meet(self, a, b):
        across = min(a.get_right()[0], b.get_right()[0]) - max(a.get_left()[0], b.get_left()[0])
        up = min(a.get_top()[1], b.get_top()[1]) - max(a.get_bottom()[1], b.get_bottom()[1])
        return across > 0.06 and up > 0.06

    def within(self, m, x, y):
        across = m.get_left()[0] >= -x and m.get_right()[0] <= x
        return across and m.get_bottom()[1] >= -y and m.get_top()[1] <= y

    def crowded(self, label, others):
        # A label lies past the margin, or over a word that is not its own.
        mine = self.words_of(label, [])
        for m in mine:
            if not self.within(m, 6.2, 3.4):
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
            if not self.within(m, 7.12, 4.02):
                outside += 1
        if overlapping > 0 or outside > 0:
            said = str(overlapping) + " overlapping, " + str(outside) + " past the edge"
            self.post_message("layout", said)
