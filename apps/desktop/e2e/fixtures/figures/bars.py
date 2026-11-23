from manim import *
import math


class BarsFigure(Scene):
    """Bars drawn and then changed."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"
        self.muted = "#9DB0A5" if dark else "#5F6E65"
        self.green = "#3DBE7F" if dark else "#269B62"
        self.blue = "#7BA4EE" if dark else "#5B8DE6"
        self.coral = "#F08F7D" if dark else "#EF806C"
        self.sun = "#E9BE5A" if dark else "#F2C14E"
        self.violet = "#A694E3" if dark else "#9178D7"

    def bar(self, x, height, hue):
        bar = Rectangle(width=1.4, height=max(0.02, abs(height)), color=hue, fill_opacity=0.6)
        bar.move_to([x, -2.3 + height / 2, 0])
        return bar

    def construct(self):
        holds = [2.4, 2.4, 2.4, 2.4]
        xs = [-2.4, 0.0, 2.4]
        heights = [1.75, 3.5, 1.75]
        values = ['0.25', '0.5', '0.25']
        names = ['0', '1', '2']
        baseline = Line([-6.0, -2.3, 0], [6.0, -2.3, 0], color=self.muted)
        labels = VGroup()
        for index in range(len(xs)):
            labels.add(
                Text(names[index], font_size=24, color=self.muted).move_to(
                    [xs[index], -2.3 - 0.45 if heights[index] >= 0 else -2.3 + 0.45, 0]
                )
            )
        unit = 'P(X = x)'
        extra = []
        if unit:
            extra.append(FadeIn(MathTex(unit, font_size=34, color=self.ink).to_edge(UP, buff=0.4)))
        self.play(Create(baseline), FadeIn(labels), *extra, run_time=1.2)
        self.wait(holds[0])
        bars = VGroup()
        numbers = VGroup()
        for index in range(len(xs)):
            hue = self.blue if heights[index] >= 0 else self.coral
            bar = self.bar(xs[index], heights[index], hue)
            bars.add(bar)
            numbers.add(
                Text(values[index], font_size=24, color=self.ink).next_to(
                    bar, UP if heights[index] >= 0 else DOWN, buff=0.15
                )
            )
        self.play(
            LaggedStart(*[FadeIn(bar, shift=UP * 0.4) for bar in bars], lag_ratio=0.15),
            FadeIn(numbers),
            run_time=1.4,
        )
        self.wait(holds[1])
        step = 2
        pick = 1
        if pick >= 0:
            self.play(Indicate(bars[pick]), Indicate(numbers[pick]), run_time=1.2)
            self.wait(holds[step])
            step += 1
        later = [0.7, 4.2, 2.1]
        if later:
            shown = ['0.1', '0.6', '0.3']
            moves = []
            for index in range(len(xs)):
                hue = self.blue if later[index] >= 0 else self.coral
                bar = self.bar(xs[index], later[index], hue)
                number = Text(shown[index], font_size=24, color=self.ink).next_to(
                    bar, UP if later[index] >= 0 else DOWN, buff=0.15
                )
                moves.append(Transform(bars[index], bar))
                moves.append(Transform(numbers[index], number))
            self.play(*moves, run_time=1.4)
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
