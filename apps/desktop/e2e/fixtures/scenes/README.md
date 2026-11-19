# Scene fixtures for end-to-end tests

Deliberately broken or hostile scene files. They exist to prove that the isolated
player fails safely. **They are test fixtures, not examples to copy.**

| File | What it exercises |
|---|---|
| `syntax_error.py` | Compile failure with a line/column message |
| `bad_import.py` | Import of a Python module Wanim does not provide |
| `runtime_error.py` | Exception raised while the scene is playing |
| `no_scene.py` | A file with no `Scene` subclass |
| `busy_loop.py` | A scene that never yields (liveness watchdog, process isolation) |
| `verbatim_js.py` | RapydScript's raw-JavaScript literal (rejected by the static policy; contained by the sandbox) |
| `hostile_probe.py` | Attempts to reach the bridge, the parent window, storage, and the network |

Known-good scenes live in `skills/wanim-scene-authoring/examples/`.
