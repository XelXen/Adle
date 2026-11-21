from manim import *


class SmallMinusSigns(Scene):
    """Two columns of small minus signs: the thinnest stroke a formula has.

    Each sign sits exactly on a row of pixels of the 1280-wide drawing, a different row
    for each, which is where shrinking that drawing to the size of a lesson's picture
    loses some of them. Whether every one is still there is what the end-to-end suite
    looks at.
    """

    def construct(self):
        for column, first, step in ((-2.0, 90, 46), (2.0, 93, 47)):
            for index in range(13):
                row = first + step * index
                sign = MathTex(r"-", font_size=28, color="#17251E")
                sign.move_to([column, (360 - row - 0.5) / 90, 0])
                self.add(sign)
        self.wait(0.4)
