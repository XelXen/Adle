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

    def bar(self, x, height, width, shown, label, hue):
        rect = Rectangle(width=width, height=max(0.04, abs(height)), color=hue)
        rect.set_fill(hue, 0.6)
        rect.move_to([x, height / 2, 0])
        number = Text(shown, font_size=26, color=self.ink)
        if height >= 0:
            number.next_to(rect, UP, buff=0.12)
        else:
            number.next_to(rect, DOWN, buff=0.12)
        name = self.shown(label, 24, self.muted)
        self.fit(name, width + 0.5, 0.6)
        if height >= 0:
            name.move_to([x, -0.35, 0])
        else:
            name.move_to([x, 0.35, 0])
        return VGroup(rect, number, name)

    def bars(self, xs, heights, width, shown, labels, hue):
        made = VGroup(Line([xs[0] - width, 0, 0], [xs[len(xs) - 1] + width, 0, 0], color=self.muted))
        for index in range(len(xs)):
            made.add(self.bar(xs[index], heights[index], width, shown[index], labels[index], hue))
        return made

    def make_bars(self, key, keys, xs, heights, width, shown, labels, name, tallest, hue):
        made = self.bars(xs, heights, width, shown, labels, hue)
        self.e[key + "/base"] = made[0]
        for index in range(len(keys)):
            self.e[keys[index]] = made[index + 1]
        marks = VGroup(made[0])
        if name:
            title = self.shown(name, 30, hue)
            title.move_to([0, tallest + 0.75 + title.height / 2, 0])
            marks.add(title)
        self.e[key + "/frame"] = marks
        self.e[key] = VGroup(marks, *[self.e[item] for item in keys])

    def rebar(self, key, keys, xs, heights, width, shown, labels, hue):
        fresh = self.bars(xs, heights, width, shown, labels, hue)
        base = self.e[key + "/base"]
        fresh.scale(base.width / fresh[0].width)
        fresh.shift(RIGHT * (base.get_center()[0] - fresh[0].get_center()[0]) + UP * (base.get_center()[1] - fresh[0].get_center()[1]))
        return [Transform(self.e[keys[index]], fresh[index + 1]) for index in range(len(keys))]

    def build(self):
        self.e = {}
        self.ax = {}
        self.trackers = {}
        self.rings = []
        self.followers = []
        self.pins = []
        self.still = []
        self.sides = {}
        self.amount = ValueTracker(0.0)
        self.make_bars('counts', ['counts.1', 'counts.2', 'counts.3', 'counts.4', 'counts.5', 'counts.6'], [-4.0, -2.4, -0.8, 0.8, 2.4, 4.0], [0.25, 0.25, 0.25, 0.25, 0.25, 0.25], 0.8, ['1', '1', '1', '1', '1', '1'], [[True, '1'], [True, '2'], [True, '3'], [True, '4'], [True, '5'], [True, '6']], [False, 'rolls of a die'], 3.0, self.blue)
        self.put(['counts'], [0.0, 0.0, 12.4, 6.8], 1)
        self.tidy()

    def step_0(self):
        self.build()
        self.play(LaggedStart(FadeIn(self.e['counts/frame']), FadeIn(self.e['counts.1'], shift=UP * 0.15), FadeIn(self.e['counts.2'], shift=UP * 0.15), FadeIn(self.e['counts.3'], shift=UP * 0.15), FadeIn(self.e['counts.4'], shift=UP * 0.15), FadeIn(self.e['counts.5'], shift=UP * 0.15), FadeIn(self.e['counts.6'], shift=UP * 0.15), lag_ratio=0.12), run_time=1.74)
        self.audit()
        self.post_message("step", 0)

    def step_1(self):
        self.play(*self.rebar('counts', ['counts.1', 'counts.2', 'counts.3', 'counts.4', 'counts.5', 'counts.6'], [-4.0, -2.4, -0.8, 0.8, 2.4, 4.0], [2.0, 3.0, 2.25, 2.75, 2.5, 2.5], 0.8, ['8', '12', '9', '11', '10', '10'], [[True, '1'], [True, '2'], [True, '3'], [True, '4'], [True, '5'], [True, '6']], self.blue), run_time=1.4)
        self.audit()
        self.post_message("step", 1)

    def step_2(self):
        self.play(self.ring(['counts.2'], self.sun), self.e['counts.2'].animate.scale(1.12), run_time=0.45)
        self.play(self.e['counts.2'].animate.scale(1 / 1.12), run_time=0.25)
        self.audit()
        self.post_message("step", 2)
