"""Where the film engine lives, and running it (ADR-065).

The engine is a program of its own, on a Python of its own: the core never imports it. It
is started for one scene at a time, in the folder Adle made for that film, with nothing of
this computer's in its environment (no setting for Python, no proxy but one that leads
nowhere, no profile: its home, its temporary files and its caches are a folder of the film
maker's own, ``FilmPaths.home``), for a bounded time, and what it prints is read up to a
bound.

That home is kept from one run to the next, as a program's user folders are, and goes
when the film maker is removed. In a home that had never been used, the engine's first run
was seen never to end (not in ten minutes, on Windows with an NVIDIA card, 2026-11-25),
and every run after it, once it had been ended, took seconds: what the first run sets up
for the graphics driver is kept in the home whether it ends or not. So the home is readied
before the film maker is tried and before each film (``FilmEngine.prime``).

What it runs is a chapter a model wrote. A chapter is run only after ``film.policy`` has
passed it, and only inside the files Adle writes around it (``film.script``), which give it
Adle's voice and refuse the network; this module starts nothing else.

For development, ``ADLE_FILM_PYTHON`` points at a Python that has the engine installed
elsewhere, and ``ADLE_FILM_ENGINE`` at another engine program (the tests use one that draws
nothing: ``tests/support/fake_film_engine.py``).
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from adle_core.errors import AdleError
from adle_core.film.catalog import ENGINE_VERSION, PYTHON_RELEASE, PYTHON_VERSION, build_for
from adle_core.film.report import Report, read_report
from adle_core.film.storyboard import clear_sheets

PYTHON_ENV = "ADLE_FILM_PYTHON"
ENGINE_ENV = "ADLE_FILM_ENGINE"
#: Written beside the engine once it is whole: what was set up, so that another version of
#: Adle sets it up again.
SETUP_MARK = "adle-film-engine.json"

#: The longest one chapter may take to be looked at.
INSPECT_SECONDS = 300.0
#: The least time a film is given to be looked at whole, or made into a video; a long film
#: is given more, by its length (``seconds_for``).
WHOLE_SECONDS = 900.0
#: The most of what the engine prints that is read.
MAX_OUTPUT_BYTES = 400_000
#: How long the run that readies the engine's home is let go on before it is ended
#: (``FilmEngine.prime``).
PRIME_SECONDS = 20.0
#: What that run draws: a little of what every chapter draws.
_PRIMER = """import manimgx as m


class Prime(m.Scene):
    def construct(self):
        self.play(m.Create(m.Circle(fill_opacity=0.5)), m.Write(m.Text("Adle")))
"""
#: Where the engine's proxy leads: a port nothing listens on, on this computer.
NOWHERE = "http://127.0.0.1:9"

_INSIDE = Path("python.exe") if sys.platform == "win32" else Path("bin") / "python3"


class FilmEngineError(AdleError):
    """The engine could not be run at all, or did not end in time."""

    status_code = 503
    code = "film_engine_failed"

    def __init__(self, message: str = "The film maker stopped. Try again.") -> None:
        super().__init__(message)


class FilmEngineStoppedError(FilmEngineError):
    """Stopped because the learner stopped the film."""


class FilmEngineTimeoutError(FilmEngineError):
    """A scene ran for longer than it was given: something in it never ends."""

    def __init__(self) -> None:
        super().__init__("The film maker took too long over one part. Try again.")


def setup_mark() -> dict[str, str]:
    return {"engine": ENGINE_VERSION, "python": PYTHON_VERSION, "release": PYTHON_RELEASE}


def seconds_for(film_seconds: float | None) -> float:
    """How long a whole film may take to be looked at or made into a video: drawing a
    frame takes a part of the time it is shown for, and a film may be long."""
    return max(WHOLE_SECONDS, 3.0 * (film_seconds or 0.0))


@dataclass(frozen=True, slots=True)
class FilmPaths:
    #: Where the engine is installed by Adle. Only this is ever removed.
    root: Path
    #: The Python the engine runs on: its own, or one a developer pointed at.
    python: Path
    #: Another engine program, run instead of ManimGX itself: for tests.
    engine: Path | None
    #: Set by a developer: used as it is, never set up or removed.
    borrowed: bool
    #: Where a film is worked on, a folder a film.
    work: Path
    #: Where finished films are kept, a folder a film.
    films: Path

    @classmethod
    def under(cls, data_dir: Path, environ: Mapping[str, str] = os.environ) -> FilmPaths:
        root = data_dir / "film-engine"
        given = environ.get(PYTHON_ENV, "").strip()
        engine = environ.get(ENGINE_ENV, "").strip()
        return cls(
            root=root,
            python=Path(given) if given else root / "python" / _INSIDE,
            engine=Path(engine) if engine else None,
            borrowed=bool(given),
            work=data_dir / "film-work",
            films=data_dir / "films",
        )

    def ready(self) -> bool:
        """Whether the engine is here, whole, and the one this Adle pins."""
        if not self.python.is_file():
            return False
        if self.borrowed:
            return True
        try:
            mark = json.loads((self.root / SETUP_MARK).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return bool(mark == setup_mark())

    def fits(self) -> bool:
        """Whether the engine runs on this kind of computer."""
        return self.borrowed or build_for() is not None

    @property
    def home(self) -> Path:
        """The engine's own home: what it, and the graphics driver for it, keep between
        runs. Inside the film maker's folder, so that it goes when the film maker does."""
        return self.root / "home"


def bare_environment(home: Path) -> dict[str, str]:
    """What the engine runs with: where the system is, and folders of its own for
    everything a program keeps. None of this computer's settings, nothing of the learner's
    profile, and a proxy that leads nowhere, so that nothing it tries to fetch is fetched."""
    for name in ("home", "tmp", "cache"):
        (home / name).mkdir(parents=True, exist_ok=True)
    environment = {
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "NO_COLOR": "1",
        "HOME": str(home / "home"),
        "TMP": str(home / "tmp"),
        "TEMP": str(home / "tmp"),
        "TMPDIR": str(home / "tmp"),
    }
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        environment[name] = NOWHERE
        environment[name.lower()] = NOWHERE
    if sys.platform == "win32":
        root = os.environ.get("SYSTEMROOT") or r"C:\Windows"
        # A graphics driver looks for these two, and waits for ever if they are not there.
        for name in ("roaming", "local"):
            (home / name).mkdir(parents=True, exist_ok=True)
        environment.update(
            {
                "SystemRoot": root,
                "windir": root,
                "SystemDrive": os.environ.get("SYSTEMDRIVE") or "C:",
                "PATH": os.pathsep.join([str(Path(root) / "System32"), root]),
                "USERPROFILE": str(home / "home"),
                "APPDATA": str(home / "roaming"),
                "LOCALAPPDATA": str(home / "local"),
            }
        )
    else:
        environment.update(
            {
                "PATH": "/usr/bin:/bin",
                "LANG": "C.UTF-8",
                "XDG_CACHE_HOME": str(home / "cache"),
                "XDG_CONFIG_HOME": str(home / "home"),
                "XDG_DATA_HOME": str(home / "home"),
            }
        )
    return environment


class FilmEngine:
    """Runs the engine on one scene at a time."""

    def __init__(self, paths: FilmPaths) -> None:
        self._paths = paths

    def _command(self, *arguments: str) -> list[str]:
        # As isolated as the core: no PYTHON* variables, no user packages, nothing from the
        # current folder but the scene the engine is given.
        # `-B` as well: `-I` ignores PYTHONDONTWRITEBYTECODE, and a chapter written again in
        # the same second at the same size would otherwise be read from what was compiled of
        # the one before.
        head = [str(self._paths.python), "-I", "-B", "-X", "utf8"]
        if self._paths.engine is not None:
            return [*head, str(self._paths.engine), *arguments]
        return [*head, "-m", "manimgx", *arguments]

    def inspect(
        self,
        folder: Path,
        file: str,
        scene: str,
        cancelled: Callable[[], bool],
        *,
        seconds: float = INSPECT_SECONDS,
    ) -> Report:
        """Run a scene without making a video: its plays, and what is wrong with it. Its
        storyboard is drawn beside it (``film.storyboard``); what an earlier run drew there
        is removed first, so that every sheet there afterwards is this run's."""
        clear_sheets(folder, scene)
        _, out, err = self._run(self._command("inspect", file, scene), folder, seconds, cancelled)
        return read_report(out, err)

    def prime(self, cancelled: Callable[[], bool]) -> None:
        """Ready the engine's home: run a small scene, and end it if it takes long.

        In a home that has never been used, the first run of the engine was seen never to
        end (on Windows with an NVIDIA card, 2026-11-25: not in ten minutes), and every run
        after it, once it had been ended, to take two seconds: whatever the first run sets
        up for the graphics driver is kept in the home whether it ends or not. Done before
        the film maker is tried at setup and before each film; in a home that is ready it
        takes two seconds.
        """
        folder = self._paths.root / "prime"
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "prime.py").write_text(_PRIMER, encoding="utf-8")
        try:
            self._run(
                self._command("inspect", "prime.py", "Prime"), folder, PRIME_SECONDS, cancelled
            )
        except FilmEngineTimeoutError:
            # Ended: what it set up is kept, which is what it was for.
            pass
        finally:
            _removed(folder)

    def render(
        self,
        folder: Path,
        file: str,
        scene: str,
        video: Path,
        cancelled: Callable[[], bool],
        *,
        seconds: float = WHOLE_SECONDS,
    ) -> Report:
        """Make the video of a scene, at 1920 by 1080 and 30 frames a second, with its sound
        and with its subtitles beside it. A video that was made is made, whatever the engine
        found to say of its layout; one that was not, with nothing said of why, is an error."""
        _, out, err = self._run(
            self._command(
                "render", file, scene, "-o", str(video), "-r", "1920x1080", "--fps", "30"
            ),
            folder,
            seconds,
            cancelled,
        )
        report = read_report(out, err)
        made = video.is_file() and video.stat().st_size > 0
        if not made and report.failure is None:
            raise FilmEngineError("The film maker couldn’t make the video. Try again.")
        return report

    def _run(
        self, command: list[str], folder: Path, seconds: float, cancelled: Callable[[], bool]
    ) -> tuple[int, str, str]:
        home = self._paths.home
        out_path, err_path = folder / "engine-out.txt", folder / "engine-err.txt"
        try:
            with out_path.open("wb") as out, err_path.open("wb") as err:
                process = subprocess.Popen(  # noqa: S603 - the engine's own Python, Adle's paths
                    command,
                    cwd=folder,
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    env=bare_environment(home),
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                deadline = time.monotonic() + seconds
                while True:
                    try:
                        code = process.wait(timeout=0.25)
                        break
                    except subprocess.TimeoutExpired:
                        if cancelled():
                            _end(process)
                            raise FilmEngineStoppedError("Stopped.") from None
                        if time.monotonic() > deadline:
                            _end(process)
                            raise FilmEngineTimeoutError from None
        except OSError as error:
            raise FilmEngineError() from error
        return code, _read(out_path), _read(err_path)


def _removed(folder: Path) -> None:
    """A folder of the engine's taken away. On Windows a file that a process just ended had
    open, or one being scanned as it is made, can refuse to go for a moment: it is tried
    again, for a few seconds at most."""
    for _ in range(25):
        shutil.rmtree(folder, ignore_errors=True)
        if not folder.exists():
            return
        time.sleep(0.2)


def _end(process: subprocess.Popen[bytes]) -> None:
    process.kill()
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=10)


def _read(path: Path) -> str:
    try:
        with path.open("rb") as handle:
            return handle.read(MAX_OUTPUT_BYTES).decode("utf-8", errors="replace")
    except OSError:
        return ""
