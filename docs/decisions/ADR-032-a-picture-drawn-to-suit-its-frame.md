# ADR-032: A picture is drawn at a size that suits the frame it is shown in

- **Status:** Accepted
- **Date:** 2026-11-21

## Context

The Wanim runtime draws a scene at one of a few fixed sizes (854, 1280 or 1920 pixels wide)
and the browser scales the canvas to the frame. Adle always asked for 1280. A lesson shows
a picture about 565 pixels wide in a window of the usual size, so on a display with one
pixel to the point the browser shrank every picture by 2.27.

Shrunk by more than two, a stroke one pixel thick is not made thinner. Depending on the
row it falls on, it is dropped. A lesson Kimi K3.1 Pro wrote on 2026-11-21 had
`MathTex(r"L(w)=(w-2)^2", font_size=32)` in its picture, and the lesson showed "(w 2)".
The canvas itself had the minus sign; the frame did not.

Measured with 26 small minus signs, each on its own row of the 1280-wide drawing, shown 565
wide at one pixel to the point (how much darker than the stage each one is, of 255): drawn
1280 wide, two were not there at all and two more were under 16; drawn 854 wide, every one
was 31 or more. Formulas of every size from 24 to 48 kept all their strokes drawn 854 wide.

It had not been seen before because this computer's display has one and a half pixels to
the point: there the same picture is shrunk by 1.5 and nothing is lost. A picture of the
page taken by the test tool is taken at one pixel to the point, which is how it showed.

## Decisions

- **The adapter asks for the drawing size by how wide the frame is, in pixels of the
  display, when a scene is loaded** (`qualityForWidth`): under 640, the small drawing (854);
  over 1408, the large one (1920); otherwise the middle one (1280). For any frame 427 pixels
  wide or more the browser then shrinks a drawing by two at most, and never stretches one by
  more than a tenth.
- **The frame's canvas fills the frame at 16:9 whatever size was drawn**, and its box is the
  picture exactly, so a pointer on the canvas is still a pointer on the scene.
- **Nothing new crosses the protocol.** The `quality` of a `load` message was always there;
  only who chooses it has changed. A caller that names a size is still listened to.
- **The size is chosen when a scene is loaded and not changed under it.** A window made much
  larger or smaller while a picture is on screen shows that picture stretched or shrunk
  until the next one loads. Loading it again would start it again, which is worse.

## Consequences

- A small frame is drawn with fewer pixels, which is less work. A large frame on a dense
  display is now drawn 1920 wide, which is more work and sharper than the stretched 1280 it
  was.
- A journey that reads the window's own pixels and depends on how many there are fixes the
  display's scale (`launchApp(..., { displayScale: 1 })`). The window's pixels and a
  picture of the page are not the same thing: the first has the display's scale, the second
  is taken at one pixel to the point.
- Frames narrower than 427 pixels still shrink the smallest drawing by more than two. A
  lesson's stage is not that narrow at any window size the app allows a lesson to be read
  comfortably at; if it becomes so, the runtime needs a smaller size, not Adle.

## Not done, and why

- **Refusing small formulas in the scene policy.** The guide asks for 40 to 48 and the model
  wrote 24 to 32. Drawn to suit the frame, those keep their strokes, faintly. A refusal
  would cost a request and could cost the picture.
- **Smoothing the shrinking ourselves** (drawing the canvas into a second one with a better
  filter on every frame). It would put a copy between the scene and the pointer for a gain
  that choosing the right size already gives.
