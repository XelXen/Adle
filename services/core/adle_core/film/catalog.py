"""What the film engine is made of, pinned and checkable (ADR-065).

A film of a course is made by ManimGX, an animation engine with Manim's API on a core
written in Rust that draws with the graphics card (or, where there is none, with a drawing
program of its own on the processor). It needs Python 3.13 or later, which is not the
core's own, so it comes with a Python of its own: a standalone build, fetched from its
makers' release and kept only if its size and hash are the ones here. ManimGX and what it
needs are installed into that Python from the lock for this system (``film/data``), every
file by its hash. Nothing is fetched that is not listed here or in a lock. All of it is
downloaded only at the learner's word.
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass

ENGINE = "ManimGX"
ENGINE_VERSION = "0.1.1"
PYTHON_VERSION = "3.13.18"
#: The release of python-build-standalone the Python is taken from: a month old when it
#: was pinned (2026-11-24), its sizes and digests read from the release's own list of files.
PYTHON_RELEASE = "20261026"

_RELEASES = "https://github.com/astral-sh/python-build-standalone/releases/download"

#: About what the engine takes on the disk once it is set up (its Python and its programs,
#: measured on Windows on 2026-11-24), and the room a setup needs while it works: that,
#: with the downloads beside it until they are unpacked.
INSTALLED_BYTES = 300_000_000
ROOM_BYTES = 500_000_000


@dataclass(frozen=True, slots=True)
class PythonBuild:
    #: Which build it is, as its makers name the system it is for.
    triple: str
    size: int
    sha256: str

    @property
    def url(self) -> str:
        name = (
            f"cpython-{PYTHON_VERSION}%2B{PYTHON_RELEASE}-{self.triple}-"
            "install_only_stripped.tar.gz"
        )
        return f"{_RELEASES}/{PYTHON_RELEASE}/{name}"


@dataclass(frozen=True, slots=True)
class EngineBuild:
    """What setting the engine up takes on one kind of computer."""

    python: PythonBuild
    #: The lock of ManimGX and what it needs, in ``film/data``.
    lock: str
    #: About what the locked programs come to, downloaded: the wheel pip takes of each
    #: package for this system, added up from the Python Package Index on 2026-11-24.
    program_bytes: int

    @property
    def download_bytes(self) -> int:
        return self.python.size + self.program_bytes


#: By ``sys.platform`` and the machine, as ``platform.machine()`` names it in lower case.
BUILDS: dict[tuple[str, str], EngineBuild] = {
    ("win32", "amd64"): EngineBuild(
        PythonBuild(
            "x86_64-pc-windows-msvc",
            22_023_022,
            "7369f7a35f261222a6ac8b3a87c1c88eeebee8af945d85346202591a64038dd3",
        ),
        "manimgx-windows.txt",
        87_500_000,
    ),
    ("linux", "x86_64"): EngineBuild(
        PythonBuild(
            "x86_64-unknown-linux-gnu",
            35_395_906,
            "df15fe60d3ff55bf9dcf25824b5572756bb8816ff93865a273d3301d7066a8b7",
        ),
        "manimgx-linux.txt",
        111_000_000,
    ),
    ("linux", "aarch64"): EngineBuild(
        PythonBuild(
            "aarch64-unknown-linux-gnu",
            29_492_455,
            "578d9da1983463ffb0c8c98ab0da2f18177f44069328eb0af847860c1eb05c3e",
        ),
        "manimgx-linux-arm.txt",
        106_900_000,
    ),
    ("darwin", "arm64"): EngineBuild(
        PythonBuild(
            "aarch64-apple-darwin",
            25_265_774,
            "8392b6ea51d94391befb2c31ebe75463f045d0b69dfcf5e1bb3234e1f5fa3405",
        ),
        "manimgx-macos.txt",
        72_000_000,
    ),
    ("darwin", "x86_64"): EngineBuild(
        PythonBuild(
            "x86_64-apple-darwin",
            25_055_263,
            "7412c19d896c99431b74a18a5643e110449a7f9590fbab179c3e5ab27b9aa9e3",
        ),
        "manimgx-macos-intel.txt",
        78_000_000,
    ),
}

#: Where setting it up downloads from, as a person would name each place.
SOURCES = ("GitHub", "the Python Package Index")


def build_for(system: str | None = None, machine: str | None = None) -> EngineBuild | None:
    """What the engine takes on this kind of computer, or nothing where it does not run."""
    return BUILDS.get(
        (
            system if system is not None else sys.platform,
            (machine if machine is not None else platform.machine()).lower(),
        )
    )
