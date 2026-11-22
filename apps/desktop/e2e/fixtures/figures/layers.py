from manim import *
import math


class LayersFigure(Scene):
    """Layers of nodes, joined, and a path through them."""

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
        columns = [[[-4.8, 0.6], [-4.8, -0.35], [-4.8, -1.3]], [[0.0, 1.075], [0.0, 0.125], [0.0, -0.825], [0.0, -1.775]], [[4.8, -0.35]]]
        names = ['inputs', 'hidden', 'output']
        nodes = []
        for index in range(len(columns)):
            column = VGroup()
            for place in columns[index]:
                column.add(Circle(radius=0.26, color=self.blue, fill_opacity=0.2).move_to([place[0], place[1], 0]))
            nodes.append(column)
        for index in range(len(columns)):
            title = Text(names[index], font_size=24, color=self.muted).move_to([columns[index][0][0], 2.95, 0])
            parts = [LaggedStart(*[GrowFromCenter(node) for node in nodes[index]], lag_ratio=0.1), FadeIn(title)]
            if index > 0:
                links = VGroup()
                for left in nodes[index - 1]:
                    for right in nodes[index]:
                        link = Line(left.get_right(), right.get_left(), color=self.muted)
                        link.set_stroke(width=1.5, opacity=0.55)
                        links.add(link)
                parts.append(Create(links))
            self.play(*parts, run_time=1.0)
            self.wait(holds[index])
        route = [0, 1, 0]
        if route:
            lit = []
            for index in range(len(route)):
                node = nodes[index][route[index]]
                lit.append(node.animate.set_fill(self.green, 0.7))
            pulse = Dot(color=self.coral, radius=0.12).move_to(nodes[0][route[0]].get_center())
            self.play(*lit, FadeIn(pulse), run_time=0.8)
            for index in range(1, len(route)):
                self.play(pulse.animate.move_to(nodes[index][route[index]].get_center()), run_time=0.6)
            self.play(FadeOut(pulse), run_time=0.4)
            self.wait(holds[len(holds) - 1])
