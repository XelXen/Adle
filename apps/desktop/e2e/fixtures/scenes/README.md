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

Known-good scenes live in `skills/wanim-scene-authoring/examples/`.
