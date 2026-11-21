# Scene fixtures for end-to-end tests

Deliberately broken or hostile scene files, and one pair that shows a mistake beside its
remedy. They exist to prove that the isolated player fails safely, and that what the scene
guide says about Wanim is true. **They are test fixtures, not examples to copy.**

| File | What it exercises |
|---|---|
| `syntax_error.py` | Compile failure with a line/column message |
| `bad_import.py` | Import of a Python module Wanim does not provide |
| `runtime_error.py` | Exception raised while the scene is playing |
| `stops_half_way.py` | Passes the static policy, then fails while playing: what a lesson sees when a stored scene breaks |
| `no_scene.py` | A file with no `Scene` subclass |
| `busy_loop.py` | A scene that never yields (liveness watchdog, process isolation) |
| `verbatim_js.py` | RapydScript's raw-JavaScript literal (rejected by the static policy; contained by the sandbox) |
| `hostile_probe.py` | Attempts to reach the bridge, the parent window, storage, and the network |
| `curve_opacity.py` | A plotted curve shown with `set_opacity(1)`: the path is filled, and draws as a solid shape. The first interactive scene a real model wrote did this (2026-11-20) |
| `curve_stroke.py` | The same curve shown with `set_stroke(opacity=1)`: a line, as meant |
| `fill_in_order.py` | A shape filled with `set_fill(colour, 0.9)`: filled, as meant |
| `fill_by_name.py` | The same with `set_fill(colour, opacity=0.9)`: it runs, and the shape has no fill |
| `fill_without_colour.py` | `set_fill(opacity=0.9)`: the scene stops with an error. A lesson a real model wrote lost its interactive picture this way (2026-11-21) |
| `circumscribe.py` | `Circumscribe(..., color=...)`: the name is taken for its shape and the scene stops with "shape should be either Rectangle or Circle". Found while writing the style example (2026-11-21); the static policy refuses it |
| `small_minus_signs.py` | Two columns of small minus signs, each exactly on a row of pixels of the 1280-wide drawing. Shown at the size of a lesson's picture on a display with one pixel to the point, some are lost if the scene is drawn 1280 wide and none if it is drawn 854 wide: why the player asks for a drawing to suit its frame (2026-11-21) |

Known-good scenes live in `skills/wanim-scene-authoring/examples/`.
