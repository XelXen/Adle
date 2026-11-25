"""Setting the film maker up, taking it away, and how its engine is started (ADR-065).

Nothing is downloaded: the Python comes from a stand-in for the network, the programs from
a stand-in for pip, and the engine is the stand-in (tests/support/fake_film_engine.py).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys
import tarfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

import httpx2 as httpx
import pytest

from adle_core.film import install as install_module
from adle_core.film import runtime as runtime_module
from adle_core.film.catalog import BUILDS, ENGINE_VERSION, EngineBuild, PythonBuild, build_for
from adle_core.film.install import FilmInstaller, FilmSetupError
from adle_core.film.runtime import (
    _INSIDE,
    NOWHERE,
    SETUP_MARK,
    FilmEngine,
    FilmEngineStoppedError,
    FilmEngineTimeoutError,
    FilmPaths,
    bare_environment,
    setup_mark,
)

FAKE_ENGINE = Path(__file__).resolve().parents[1] / "support" / "fake_film_engine.py"
DATA = Path(__file__).resolve().parents[2] / "adle_core" / "film" / "data"


def archive(*entries: tuple[str, bytes]) -> bytes:
    """A Python's archive as its makers pack it: everything under ``python/``."""
    packed = io.BytesIO()
    with tarfile.open(fileobj=packed, mode="w:gz") as tar:
        for name, data in entries:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return packed.getvalue()


PYTHON = archive((f"python/{_INSIDE.as_posix()}", b"not really python"), ("python/LICENSE", b"PSF"))


def a_build(data: bytes = PYTHON, *, size: int | None = None) -> EngineBuild:
    return EngineBuild(
        PythonBuild(
            "x86_64-pc-windows-msvc",
            len(data) if size is None else size,
            hashlib.sha256(data).hexdigest(),
        ),
        "manimgx-windows.txt",
        1_000,
    )


def paths_in(root: Path, *, borrowed: bool = False) -> FilmPaths:
    engine_root = root / "film-engine"
    return FilmPaths(
        root=engine_root,
        python=Path(sys.executable) if borrowed else engine_root / "python" / _INSIDE,
        engine=FAKE_ENGINE if borrowed else None,
        borrowed=borrowed,
        work=root / "film-work",
        films=root / "films",
    )


class Pip:
    """The stand-in for pip: records what it was asked, and succeeds or fails."""

    def __init__(self, code: int = 0) -> None:
        self.code = code
        self.commands: list[list[str]] = []

    def __call__(
        self, command: list[str], cancelled: Callable[[], bool], heard: Callable[[str], None]
    ) -> int:
        self.commands.append(command)
        heard("collecting")
        heard("installing")
        return self.code


@pytest.fixture
def pip(monkeypatch: pytest.MonkeyPatch) -> Pip:
    stand_in = Pip()
    monkeypatch.setattr(install_module, "_run_pip", stand_in)
    # The engine is tried after it is set up; here there is no engine to try.
    monkeypatch.setattr(FilmInstaller, "verify", lambda self: None)
    return stand_in


def network(data: bytes, status: int = 200) -> httpx.Client:
    def answer(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "github.com"
        return httpx.Response(status, content=data)

    return httpx.Client(transport=httpx.MockTransport(answer))


def nothing_said(message: str, done: int, total: int) -> None:
    return None


def test_a_setup_fetches_the_pinned_python_installs_the_locked_programs_and_marks_it(
    tmp_path: Path, pip: Pip
) -> None:
    paths = paths_in(tmp_path)
    said: list[str] = []
    FilmInstaller(paths, network(PYTHON), a_build()).install(
        lambda message, done, total: said.append(message), lambda: False
    )
    assert paths.python.read_bytes() == b"not really python"
    assert json.loads((paths.root / SETUP_MARK).read_text(encoding="utf-8")) == setup_mark()
    assert paths.ready()
    (command,) = pip.commands
    assert command[:5] == [str(paths.python), "-I", "-m", "pip", "install"]
    for flag in ("--require-hashes", "--no-deps", "--only-binary=:all:", "--no-cache-dir"):
        assert flag in command
    lock = Path(command[command.index("-r") + 1]).read_text(encoding="utf-8")
    assert lock == (DATA / "manimgx-windows.txt").read_text(encoding="utf-8")
    assert "Downloading the film maker" in said
    # Nothing of the download is left beside it.
    assert not list(paths.root.glob("*.tar.gz*"))


@pytest.mark.parametrize(
    ("data", "size"),
    [(b"a different file", None), (PYTHON + b"more", len(PYTHON))],
    ids=["another file", "longer than pinned"],
)
def test_a_python_that_arrives_different_is_not_kept(
    tmp_path: Path, pip: Pip, data: bytes, size: int | None
) -> None:
    paths = paths_in(tmp_path)
    build = a_build(size=size)
    with pytest.raises(FilmSetupError, match="didn’t arrive whole"):
        FilmInstaller(paths, network(data), build).install(nothing_said, lambda: False)
    assert not paths.root.exists()
    assert pip.commands == []


def test_nothing_in_the_archive_is_let_out_of_its_folder(tmp_path: Path, pip: Pip) -> None:
    hostile = archive((f"python/{_INSIDE.as_posix()}", b"x"), ("../escaped.txt", b"x"))
    paths = paths_in(tmp_path)
    with pytest.raises(FilmSetupError, match="Couldn’t unpack"):
        FilmInstaller(paths, network(hostile), a_build(hostile)).install(
            nothing_said, lambda: False
        )
    assert not (tmp_path / "escaped.txt").exists()
    assert not paths.root.exists()


def test_programs_that_could_not_be_installed_leave_nothing(tmp_path: Path, pip: Pip) -> None:
    pip.code = 1
    paths = paths_in(tmp_path)
    with pytest.raises(FilmSetupError, match="programs"):
        FilmInstaller(paths, network(PYTHON), a_build()).install(nothing_said, lambda: False)
    assert not paths.root.exists()


def test_a_download_that_cannot_be_had_or_is_stopped_leaves_nothing(
    tmp_path: Path, pip: Pip
) -> None:
    paths = paths_in(tmp_path)
    with pytest.raises(FilmSetupError, match="Check the connection"):
        FilmInstaller(paths, network(b"", status=404), a_build()).install(
            nothing_said, lambda: False
        )
    assert not paths.root.exists()
    with pytest.raises(FilmSetupError, match="Stopped"):
        FilmInstaller(paths, network(PYTHON), a_build()).install(nothing_said, lambda: True)
    assert not paths.root.exists()


def test_a_setup_that_would_not_fit_is_refused_before_anything_is_fetched(
    tmp_path: Path, pip: Pip, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(install_module, "_free_bytes", lambda folder: 10_000_000)

    def nothing_fetched(request: httpx.Request) -> httpx.Response:
        raise AssertionError("fetched")

    client = httpx.Client(transport=httpx.MockTransport(nothing_fetched))
    with pytest.raises(FilmSetupError, match="room"):
        FilmInstaller(paths_in(tmp_path), client, a_build()).install(nothing_said, lambda: False)


def test_a_film_maker_set_up_by_hand_is_used_as_it_is(tmp_path: Path) -> None:
    paths = paths_in(tmp_path, borrowed=True)
    assert paths.ready()
    with pytest.raises(FilmSetupError, match="by hand"):
        FilmInstaller(paths).install(nothing_said, lambda: False)
    with pytest.raises(FilmSetupError, match="by hand"):
        FilmInstaller(paths).remove()


def test_removing_it_takes_its_own_folder_and_nothing_else(tmp_path: Path, pip: Pip) -> None:
    paths = paths_in(tmp_path)
    FilmInstaller(paths, network(PYTHON), a_build()).install(nothing_said, lambda: False)
    paths.films.mkdir(parents=True)
    (paths.films / "kept.mp4").write_bytes(b"x")
    FilmInstaller(paths).remove()
    assert not paths.root.exists()
    assert (paths.films / "kept.mp4").exists()


def test_a_film_maker_set_up_by_another_version_is_set_up_again(tmp_path: Path) -> None:
    paths = paths_in(tmp_path)
    paths.python.parent.mkdir(parents=True)
    paths.python.write_bytes(b"x")
    (paths.root / SETUP_MARK).write_text(json.dumps({**setup_mark(), "engine": "0.0.9"}), "utf-8")
    assert not paths.ready()


def test_every_system_it_is_offered_on_has_a_python_and_programs_pinned_by_hash() -> None:
    assert build_for("win32", "AMD64") is BUILDS[("win32", "amd64")]
    assert build_for("linux", "riscv64") is None
    for build in BUILDS.values():
        assert re.fullmatch(r"[0-9a-f]{64}", build.python.sha256)
        assert build.python.url.startswith(
            "https://github.com/astral-sh/python-build-standalone/releases/download/"
        )
        lock = (DATA / build.lock).read_text(encoding="utf-8")
        assert f"manimgx=={ENGINE_VERSION}" in lock
        requirements = re.findall(
            r"^([A-Za-z0-9_.-]+)==\S+((?:\s*\\\s*--hash=sha256:[0-9a-f]{64})+)", lock, re.MULTILINE
        )
        named = re.findall(r"^[A-Za-z0-9]", lock, re.MULTILINE)
        assert len(requirements) == len(named)


def test_the_engine_runs_with_none_of_this_computers_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ADLE_SECRET_LOOKING_THING", "x")
    monkeypatch.setenv("PYTHONPATH", "elsewhere")
    environment = bare_environment(tmp_path / "home")
    assert "ADLE_SECRET_LOOKING_THING" not in environment
    assert "PYTHONPATH" not in environment
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy"):
        assert environment[name] == NOWHERE
    for name in ("HOME", "TMP", "TEMP"):
        assert Path(environment[name]).is_relative_to(tmp_path)
    if sys.platform == "win32":
        assert Path(environment["APPDATA"]).is_dir()
        assert Path(environment["LOCALAPPDATA"]).is_dir()
        assert os.environ["APPDATA"] != environment["APPDATA"]


def scene(folder: Path, mark: str | None = None) -> None:
    """A chapter and the take that plays it alone, as the film service writes them."""
    folder.mkdir(parents=True, exist_ok=True)
    note = f"        # fake: {mark}\n" if mark else ""
    (folder / "chapter_02.py").write_text(
        "import manimgx as m\n\n\nclass Chapter(m.Scene):\n    def construct(self):\n"
        f"{note}        self.say('Here is a circle.')\n        self.wait(2)\n",
        encoding="utf-8",
    )
    (folder / "take_02.py").write_text(
        "import adle_voice\nimport chapter_02\n\n\nclass Take(chapter_02.Chapter):\n"
        "    voice = adle_voice.voice\n",
        encoding="utf-8",
    )


def test_the_engine_says_what_a_scene_plays(tmp_path: Path) -> None:
    folder = tmp_path / "work"
    scene(folder)
    report = FilmEngine(paths_in(tmp_path, borrowed=True)).inspect(
        folder, "take_02.py", "Take", lambda: False
    )
    assert report.clean
    assert [play.line for play in report.plays] == [6, 7]
    assert report.seconds == pytest.approx(1.54 + 2.0, abs=0.01)


def test_a_scene_that_never_ends_is_ended_in_time_or_when_stopped(tmp_path: Path) -> None:
    folder = tmp_path / "work"
    scene(folder, "hang")
    engine = FilmEngine(paths_in(tmp_path, borrowed=True))
    with pytest.raises(FilmEngineTimeoutError):
        engine.inspect(folder, "take_02.py", "Take", lambda: False, seconds=1.0)
    stop = threading.Event()
    threading.Timer(0.5, stop.set).start()
    with pytest.raises(FilmEngineStoppedError):
        engine.inspect(folder, "take_02.py", "Take", stop.is_set, seconds=60.0)


def test_the_engines_home_is_readied_by_a_run_ended_if_it_hangs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A first run in an empty home was seen never to end, and the next to take seconds
    (2026-11-25): readying the home ends the first run, and is not a failure."""
    hangs = tmp_path / "hangs.py"
    hangs.write_text("import time\n\ntime.sleep(60)\n", encoding="utf-8")
    paths = FilmPaths(
        root=tmp_path / "film-engine",
        python=Path(sys.executable),
        engine=hangs,
        borrowed=True,
        work=tmp_path / "film-work",
        films=tmp_path / "films",
    )
    monkeypatch.setattr(runtime_module, "PRIME_SECONDS", 1.0)
    began = time.monotonic()
    FilmEngine(paths).prime(lambda: False)
    assert time.monotonic() - began < 15
    assert paths.home.is_dir()
    assert not (paths.root / "prime").exists()
    # The learner's Stop still stops it.
    stop = threading.Event()
    threading.Timer(0.3, stop.set).start()
    monkeypatch.setattr(runtime_module, "PRIME_SECONDS", 30.0)
    with pytest.raises(FilmEngineStoppedError):
        FilmEngine(paths).prime(stop.is_set)
