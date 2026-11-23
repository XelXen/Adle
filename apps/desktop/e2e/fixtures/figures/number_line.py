from manim import *
import math


class NumberLineFigure(Scene):
    """A number line with marks and a moving point."""

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
        holds = [2.4, 2.4, 2.4, 2.4]
        line = Line([-6.0, -0.4, 0], [6.0, -0.4, 0], color=self.muted)
        ticks = VGroup()
        for tick in [[-5.8, '-3'], [-3.867, '-2'], [-1.933, '-1'], [0.0, '0'], [1.933, '1'], [3.867, '2'], [5.8, '3']]:
            ticks.add(Line([tick[0], -0.55, 0], [tick[0], -0.25, 0], color=self.muted))
            ticks.add(MathTex(tick[1], font_size=32, color=self.muted).move_to([tick[0], -1.0, 0]))
        self.play(Create(line), FadeIn(ticks), run_time=1.2)
        self.wait(holds[0])
        step = 1
        marks = [[-3.789, '-1.96'], [3.789, '1.96']]
        if marks:
            dots = VGroup()
            for mark in marks:
                # Over the interval drawn later, which would hide half of it.
                dot = Dot(color=self.coral, radius=0.11).move_to([mark[0], -0.4, 0]).set_z_index(2)
                dots.add(dot)
                if mark[1]:
                    dots.add(MathTex(mark[1], font_size=34, color=self.ink).next_to(dot, UP, buff=0.3))
            self.play(LaggedStart(*[FadeIn(item, shift=DOWN * 0.2) for item in dots], lag_ratio=0.2), run_time=1.2)
            self.wait(holds[step])
            step += 1
        interval = [-3.789, 3.789, '95\\%']
        if interval:
            band = Line([interval[0], -0.4, 0], [interval[1], -0.4, 0], color=self.green)
            band.set_stroke(width=12)
            parts = [Create(band)]
            if interval[2]:
                words = MathTex(interval[2], font_size=34, color=self.ink)
                words.move_to([(interval[0] + interval[1]) / 2, 0.75, 0])
                parts.append(Write(words))
            self.play(*parts, run_time=1.2)
            self.wait(holds[step])
            step += 1
        move = [0.0, 2.9, '']
        if move:
            where = ValueTracker(move[0])
            runner = always_redraw(lambda: Dot(color=self.blue, radius=0.14).move_to([where.get_value(), -0.4, 0]).set_z_index(3))
            self.add(runner)
            self.play(where.animate.set_value(move[1]), run_time=2.0, rate_func=smooth)
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
