import manimgx as m

SIDE = m.BLUE
AREA = m.YELLOW


def label(text, color=m.WHITE, size=30):
    return m.Text(text, font_size=size, color=color)


class Chapter(m.Scene):
    def construct(self):
        title = m.Text("The area of a rectangle", font_size=44).to_edge(m.UP, buff=0.5)
        self.say("How much floor does a rug cover? [Let us count it.]", m.Write(title))

        squares = m.VGroup(
            *[m.Square(side_length=1, color=SIDE, stroke_width=3) for index in range(8)]
        ).arrange_in_grid(rows=2, cols=4, buff=0)
        squares.move_to([-3, -0.3, 0])
        wide = label("4 wide", SIDE).next_to(squares, m.DOWN, buff=0.3)
        tall = label("2 tall", SIDE).next_to(squares, m.LEFT, buff=0.3)
        self.say(
            "Here is a rug, [four squares wide] and [two squares tall].",
            m.LaggedStart(*[m.Create(square) for square in squares], lag_ratio=0.1),
            m.AnimationGroup(m.FadeIn(wide), m.FadeIn(tall)),
        )
        counted = m.VGroup()
        for index, square in enumerate(squares):
            counted.add(m.Text(str(index + 1), font_size=28, color=AREA).move_to(square))
        self.say(
            "Count the squares one by one: [there are eight of them].",
            m.LaggedStart(*[m.FadeIn(number) for number in counted], lag_ratio=0.15),
        )
        self.say("Each square is one square unit, so the rug covers eight square units.")

        rows = m.MathTex(r"4 + 4 = 8", font_size=48).move_to([3.3, 1.0, 0])
        times = m.MathTex(r"4 \times 2 = 8", font_size=48).move_to([3.3, 1.0, 0])
        self.say("Two rows of four make [four plus four], which is eight.", m.Write(rows))
        self.say(
            "Adding the same number again and again is multiplying: [four times two].",
            m.ReplacementTransform(rows, times),
        )
        rule = m.MathTex(
            r"\text{area} = \text{width} \times \text{height}", font_size=44, color=AREA
        ).move_to([3.3, -1.2, 0])
        self.say("So the area of any rectangle is [its width times its height].", m.Write(rule))
        self.play(m.Circumscribe(rule, color=AREA))
        self.play(m.FadeOut(m.VGroup(*self.mobjects)))

        heading = m.Text("A second rug", font_size=44).to_edge(m.UP, buff=0.5)
        self.say("Now try it on [a rug three wide and three tall].", m.Write(heading))
        grid = m.VGroup(
            *[m.Square(side_length=0.9, color=m.GREEN, stroke_width=3) for index in range(9)]
        ).arrange_in_grid(rows=3, cols=3, buff=0)
        grid.move_to([-3, -0.4, 0])
        self.say("Three rows of three squares: [here they are].", m.Create(grid))
        nine = m.MathTex(r"3 \times 3 = 9", font_size=48).move_to([3.3, 0, 0])
        self.say("Width times height is [three times three], which is nine.", m.Write(nine))
        self.say("Counting the squares one by one gives nine as well.", m.Indicate(grid))
        self.say("A square is a rectangle whose width and height are the same.")
        self.say("So its area is its side times itself.")
        self.say("Whatever the shape of the rectangle, width times height counts its squares.")
        self.play(m.FadeOut(m.VGroup(*self.mobjects)))
