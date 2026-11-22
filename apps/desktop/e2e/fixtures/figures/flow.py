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
        holds = [2.6, 2.6, 2.6, 2.6]
        places = [[-3.667, 0.0], [0.0, 0.0], [3.667, 0.0]]
        names = [['Collect the', 'data'], ['Fit the model'], ['Check the fit']]
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
        if True:
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
