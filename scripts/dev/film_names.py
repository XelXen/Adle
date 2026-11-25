"""Write down every name a chapter of a film may use of the engine (ADR-065).

Run by hand with the engine's own Python (3.13 or later), after its version changes:

    <engine python> -I scripts/dev/film_names.py services/core/adle_core/film/data/names.json

It needs nothing of Adle's: it looks at the ManimGX that is installed beside it. What it
writes is read by ``adle_core/film/policy.py``, which refuses every name that is not in it.
The lists of what is left out are here, to be read by a person: each is a way to a file, to
sound from elsewhere, to the engine's own machinery, or to three dimensions (where the
engine does not check a layout).
"""

from __future__ import annotations

import ast
import inspect
import json
import re
import sys
import textwrap
from importlib.metadata import version
from pathlib import Path

import manimgx as m

#: Names on the package a scene may not use.
DENIED_API = {
    # files, and sound that is not Adle's
    "ImageMobject", "ImageMobjectFromCamera", "SVGMobject", "VMobjectFromSVGPath", "Sound",
    "Speech", "Typst", "MathTypst", "Film", "Window", "Camera", "config",
    # machinery
    "assert_is_mobject_method", "override_animate", "override_animation", "RESAMPLING_ALGORITHMS",
    # other kinds of scene: a chapter is a plain one
    "ThreeDScene", "MovingCameraScene", "ZoomedScene", "LinearTransformationScene", "VectorScene",
    # three dimensions: the engine checks no layout there
    "ThreeDAxes", "ThreeDVMobject", "Surface", "Sphere", "Cube", "Prism", "Cone", "Cylinder",
    "Torus", "Dot3D", "Line3D", "Arrow3D", "Tetrahedron", "Octahedron", "Icosahedron",
    "Dodecahedron", "Polyhedron", "ConvexHull3D", "MeshMobject", "Material", "AmbientLight",
    "EnvironmentLight", "PointLight", "SpotLight", "SunLight", "Light",
}  # fmt: skip

#: Names of methods and attributes a scene may not use, whatever they are found on.
DENIED_MEMBERS = {
    # sound, the voice, and what the film is made into
    "add_sound", "add_subcaption", "voice", "speech", "speaks", "soundtrack", "subtitles",
    "captions", "record", "render", "renderer", "compositor", "display_list", "picture",
    "played", "take", "tween", "scenes", "section", "abort", "close", "open", "cut",
    "gain", "loop", "trim", "samples", "duck",
    # files and pictures
    "pixel_array", "set_resampling_algorithm", "get_file_path", "init_svg_mobject",
    "modify_xml_tree", "path_to_mobject", "rect_to_mobject", "ellipse_to_mobject",
    "line_to_mobject", "polygon_to_mobject", "polyline_to_mobject", "text_to_mobject",
    "get_mob_from_shape_element", "get_mobjects_from", "handle_transform",
    "generate_config_style_dict", "parse", "from_networkx",
    # what changes the engine for everything after it
    "set_default", "defaults", "add_animation_override", "animation_override_for",
    "animation_overrides",
    # the film being made and its clock: Adle's, not a chapter's
    "film", "clock",
    # text made from a pattern, or turned into bytes
    "format", "format_map", "encode", "maketrans", "translate",
    # the camera of another kind of scene
    "set_camera_orientation", "move_camera", "begin_ambient_camera_rotation",
    "stop_ambient_camera_rotation", "begin_3dillusion_camera_rotation",
    "stop_3dillusion_camera_rotation", "activate_zooming", "add_fixed_in_frame_mobjects",
    "fixed_in_frame_mobjects",
}  # fmt: skip


#: And any member whose name says it is one of these: what a typesetter is given as its
#: own code is among them, since text is only ever given to it escaped.
WAY_OUT = re.compile(
    r"(?i)file|font_path|package_path|preamble|svg|sound|voice|video|window|cache|typst"
)


def public(name: str) -> bool:
    return not name.startswith("_")


def api() -> tuple[list[str], list[type]]:
    names: list[str] = []
    classes: list[type] = []
    for name in dir(m):
        if not public(name) or name in DENIED_API:
            continue
        value = getattr(m, name)
        if inspect.ismodule(value):
            continue
        names.append(name)
        if inspect.isclass(value):
            classes.append(value)
    return sorted(names), classes


def members(classes: list[type]) -> set[str]:
    """What the classes a scene may use have: what each says of itself, and what each (and
    each class it is made from, in the engine) sets on itself as it is made."""
    found: set[str] = set()
    seen: set[type] = set()
    for each in classes:
        found.update(name for name in dir(each) if public(name))
        for base in each.__mro__:
            if base in seen or not getattr(base, "__module__", "").startswith("manimgx"):
                continue
            seen.add(base)
            try:
                tree = ast.parse(textwrap.dedent(inspect.getsource(base)))
            except (OSError, TypeError, SyntaxError):
                continue
            for node in ast.walk(tree):
                targets: list[ast.expr] = []
                if isinstance(node, ast.Assign):
                    targets = list(node.targets)
                elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                    targets = [node.target]
                for target in targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                        and public(target.attr)
                    ):
                        found.add(target.attr)
    return found


def allowed(name: str) -> bool:
    return name not in DENIED_MEMBERS and not WAY_OUT.search(name)


def main() -> None:
    names, classes = api()
    found = members(classes)
    # What the things a chapter may not use have, too: none of it is a name a chapter may
    # keep something of its own under.
    every = [getattr(m, name) for name in dir(m) if public(name)]
    beyond = members([each for each in every if inspect.isclass(each)])
    written = {
        "engine": "manimgx",
        "version": version("manimgx"),
        "api": names,
        "members": sorted(name for name in found if allowed(name)),
        "refused": sorted(name for name in found | beyond if not allowed(name)),
        "scene": sorted(name for name in dir(m.Scene) if public(name)),
    }
    text = json.dumps(written, indent=0) + "\n"
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
