"""Setting the film engine up, at the learner's word (ADR-065).

Nothing of it comes with Adle. When the learner asks for it, the engine is put on this
computer: a standalone Python from its makers' release, kept only if its size and hash are
the ones pinned; then ManimGX and what it needs, installed into that Python by pip from the
lock for this system, every file by its hash, and nothing built from source. Then the
engine is tried: it draws a circle, here, with whatever this computer draws with, before it
is called set up.

It is all under one folder of Adle's own, which is the only thing removing it removes.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import tarfile
from importlib import resources
from pathlib import Path

import httpx2 as httpx

from adle_core import logs
from adle_core.errors import AdleError
from adle_core.film.catalog import ROOM_BYTES, EngineBuild, build_for
from adle_core.film.runtime import (
    SETUP_MARK,
    WHOLE_SECONDS,
    FilmEngine,
    FilmEngineError,
    FilmPaths,
    setup_mark,
)
from adle_core.voice.install import Cancelled, Report, _run_pip

logger = logging.getLogger(__name__)

_CHUNK = 1024 * 1024
#: What the engine draws to show that it can draw here.
_CHECK = """import manimgx as m


class Check(m.Scene):
    def construct(self):
        circle = m.Circle(radius=1, color=m.BLUE, fill_opacity=0.4).shift(m.LEFT * 3.5)
        square = m.Square(side_length=1.5, color=m.GREEN).shift(m.RIGHT * 3.5)
        arrow = m.Arrow([-2, 0, 0], [2, 0, 0], buff=0, color=m.YELLOW)
        words = m.Text("Adle", font_size=40).to_edge(m.UP, buff=0.5)
        formula = m.MathTex(r"a^2 + b^2 = c^2", font_size=40).to_edge(m.DOWN, buff=0.5)
        self.play(m.Create(circle), m.Create(square), m.GrowArrow(arrow))
        self.play(m.Write(words), m.Write(formula))
        self.play(m.FadeOut(m.VGroup(circle, square, arrow, words, formula)))
"""


class FilmSetupError(AdleError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="film_setup_failed")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(_CHUNK):
            digest.update(block)
    return digest.hexdigest()


def _free_bytes(folder: Path) -> int | None:
    """How much room there is on the disk a folder is on, or nothing if it cannot be told."""
    probe = folder
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        return shutil.disk_usage(probe).free
    except OSError:
        return None


class FilmInstaller:
    def __init__(
        self,
        paths: FilmPaths,
        client: httpx.Client | None = None,
        build: EngineBuild | None = None,
    ) -> None:
        self._paths = paths
        self._client = client
        self._build = build

    def install(self, report: Report, cancelled: Cancelled) -> None:
        """Put the engine on this computer, whole, or leave nothing of it."""
        if self._paths.borrowed:
            raise FilmSetupError("The film maker here was set up by hand, and is used as it is.")
        build = self._build or build_for()
        if build is None:
            raise FilmSetupError("The film maker doesn’t run on this kind of computer.")
        if self._paths.ready():
            return
        free = _free_bytes(self._paths.root)
        if free is not None and free < ROOM_BYTES:
            raise FilmSetupError(
                f"There isn’t room on this computer’s disk: setting the film maker up needs "
                f"about {ROOM_BYTES // 1_000_000} MB free."
            )
        root = self._paths.root
        shutil.rmtree(root, ignore_errors=True)
        try:
            root.mkdir(parents=True, exist_ok=True)
            self._python(build, report, cancelled)
            self._programs(build, report, cancelled)
            report("Trying the film maker", 0, 0)
            self.verify()
            (root / SETUP_MARK).write_text(json.dumps(setup_mark()), encoding="utf-8")
        except BaseException:
            shutil.rmtree(root, ignore_errors=True)
            raise

    def remove(self) -> None:
        """Take the engine off this computer. Films already made are kept."""
        if self._paths.borrowed:
            raise FilmSetupError("The film maker here was set up by hand, and is used as it is.")
        shutil.rmtree(self._paths.root, ignore_errors=True)

    # -- its Python ------------------------------------------------------------------------

    def _python(self, build: EngineBuild, report: Report, cancelled: Cancelled) -> None:
        archive = self._paths.root / "python.tar.gz"
        total = build.download_bytes
        self._download(build.python.url, archive, build.python.size, report, cancelled, total)
        if archive.stat().st_size != build.python.size or _sha256(archive) != build.python.sha256:
            archive.unlink(missing_ok=True)
            raise FilmSetupError("A file of the film maker didn’t arrive whole. Try again.")
        report("Unpacking the film maker", build.python.size, total)
        try:
            # Its hash was the one pinned; and nothing in it is let out of this folder.
            with tarfile.open(archive, "r:gz") as packed:
                packed.extractall(self._paths.root, filter="data")
        except (tarfile.TarError, OSError) as error:
            logger.info("film.not_unpacked %s", logs.where(error))
            raise FilmSetupError("Couldn’t unpack the film maker. Try again.") from error
        finally:
            archive.unlink(missing_ok=True)
        if not self._paths.python.is_file():
            raise FilmSetupError("Couldn’t unpack the film maker. Try again.")

    def _download(
        self,
        url: str,
        target: Path,
        size: int,
        report: Report,
        cancelled: Cancelled,
        total: int,
    ) -> None:
        partial = target.with_name(target.name + ".part")
        client = self._client or httpx.Client(
            follow_redirects=True, trust_env=True, timeout=httpx.Timeout(60.0)
        )
        failed = "Couldn’t download the film maker. Check the connection and try again."
        try:
            with client.stream("GET", url) as answer:
                if answer.status_code != 200:
                    raise FilmSetupError(failed)
                received = 0
                last = -1
                with partial.open("wb") as handle:
                    for chunk in answer.iter_bytes(_CHUNK):
                        if cancelled():
                            raise FilmSetupError("Stopped.")
                        handle.write(chunk)
                        received += len(chunk)
                        if received > size:
                            raise FilmSetupError(
                                "A file of the film maker didn’t arrive whole. Try again."
                            )
                        step = received * 100 // max(1, total)
                        if step != last:
                            last = step
                            report("Downloading the film maker", received, total)
            os.replace(partial, target)
        except httpx.HTTPError as error:
            raise FilmSetupError(failed) from error
        finally:
            partial.unlink(missing_ok=True)
            if self._client is None:
                client.close()

    # -- its programs ------------------------------------------------------------------------

    def _programs(self, build: EngineBuild, report: Report, cancelled: Cancelled) -> None:
        lock = resources.files("adle_core.film.data").joinpath(build.lock).read_text("utf-8")
        locked = self._paths.root / "adle-requirements.txt"
        locked.write_text(lock, encoding="utf-8")
        packages = len(re.findall(r"^[A-Za-z0-9]", lock, flags=re.MULTILINE))
        total = build.download_bytes
        seen = [0]

        def heard(event: str) -> None:
            if event == "installing":
                report("Installing the film maker", 0, 0)
                return
            seen[0] = min(packages, seen[0] + 1)
            # pip does not say how much of each file has come: by the count of them.
            done = build.python.size + build.program_bytes * seen[0] // max(1, packages)
            report("Downloading the film maker", done, total)

        code = _run_pip(
            [
                str(self._paths.python),
                "-I",
                "-m",
                "pip",
                "install",
                "--require-hashes",
                "--no-deps",
                "--only-binary=:all:",
                "--no-cache-dir",
                "--disable-pip-version-check",
                "--no-input",
                "--no-warn-script-location",
                "--progress-bar",
                "off",
                "--index-url",
                "https://pypi.org/simple",
                "-r",
                str(locked),
            ],
            cancelled,
            heard,
        )
        if cancelled():
            raise FilmSetupError("Stopped.")
        if code != 0:
            raise FilmSetupError(
                "Couldn’t download the film maker’s programs. Check the connection and try again."
            )

    # -- that it draws, here ---------------------------------------------------------------

    def verify(self) -> None:
        """The engine draws on this computer, or it is not set up: shapes, a fill, a line,
        an arrow, words and a formula, which is also what a chapter draws. Its home is
        readied first (``FilmEngine.prime``), and kept: so is everything this run sets up
        for the graphics driver, which the films after it find there."""
        folder = self._paths.root / "check"
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "check.py").write_text(_CHECK, encoding="utf-8")
        try:
            engine = FilmEngine(self._paths)
            # Its home is readied first: a first run in an empty one was seen never to end.
            engine.prime(lambda: False)
            report = engine.inspect(
                folder, "check.py", "Check", lambda: False, seconds=WHOLE_SECONDS
            )
        except FilmEngineError as error:
            raise FilmSetupError(
                "The film maker was set up, but didn’t start on this computer."
            ) from error
        finally:
            shutil.rmtree(folder, ignore_errors=True)
        if not report.clean:
            raise FilmSetupError("The film maker was set up, but couldn’t draw on this computer.")
