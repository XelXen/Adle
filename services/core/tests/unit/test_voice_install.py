"""Setting a natural voice up, and taking it away (ADR-042).

Nothing is downloaded: the files come from a stand-in for the network, the programs from a
stand-in for pip, and the word said to check the voice from the stand-in engine
(tests/support/fake_voice_engine.py).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import types
from collections.abc import Callable
from pathlib import Path

import httpx2 as httpx
import pytest

from adle_core.voice import install as install_module
from adle_core.voice.catalog import TIERS, ModelFile, ModelRepo, Speaker, Tier, TierId
from adle_core.voice.catalog import tier as find_tier
from adle_core.voice.install import (
    VoiceInstaller,
    VoiceSetupError,
    base_python,
    is_whole,
    quiet_environment,
    room_needed,
    torch_index,
)
from adle_core.voice.runtime import SETUP_MARK, VoicePaths, lock_for, setup_mark

FAKE_ENGINE = Path(__file__).resolve().parents[1] / "support" / "fake_voice_engine.py"
CONFIG = b'{"voice": "small"}'
#: More than one piece of a download (a mebibyte each).
WEIGHTS = bytes(range(256)) * 10_000
REVISION = "0123456789abcdef0123456789abcdef01234567"


def git_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def a_tier(
    *files: tuple[str, bytes], tier_id: TierId = "kokoro", repo: str = "test/Small-Voice"
) -> Tier:
    """A size of voice made of these files: a large one pinned by SHA-256, a small one by
    its Git hash, as the catalogue pins them."""
    return Tier(
        id=tier_id,
        name="Small",
        description="A voice for tests.",
        family="kokoro",
        repos=(
            ModelRepo(
                repo,
                REVISION,
                tuple(
                    ModelFile(path, len(data), sha256=sha256(data))
                    if len(data) > 1000
                    else ModelFile(path, len(data), git_sha1=git_sha1(data))
                    for path, data in files
                ),
            ),
        ),
        min_memory_gb=None,
        speakers=(Speaker("af_heart", "Heart", "Warm and clear."),),
        default_speaker="af_heart",
        aligned=False,
    )


def paths_in(root: Path, *, programs: bool = True, borrowed: bool = False) -> VoicePaths:
    """A voice folder as the core makes one, spoken in by the stand-in engine. With
    ``programs``, the programs are there already, as an earlier setup leaves them."""
    paths = VoicePaths(
        root=root,
        pythons={"kokoro": Path(sys.executable), "qwen": Path(sys.executable)},
        models=root / "models",
        aligner=root / "aligner",
        engine=FAKE_ENGINE,
        clips=root / "clips",
        borrowed=borrowed,
    )
    if programs:
        for family in ("kokoro", "qwen"):
            mark = setup_mark(family)
            if mark is None:
                continue
            paths.own_python(family).parent.mkdir(parents=True, exist_ok=True)
            paths.own_python(family).write_bytes(b"")
            (paths.environment(family) / SETUP_MARK).write_text(json.dumps(mark), "utf-8")
    return paths


class Network:
    """A stand-in for the network: it has some files, by name, and remembers what was asked.
    With ``moved``, every file is first sent from somewhere else, as Hugging Face sends a
    large one from where it keeps it."""

    def __init__(self, files: dict[str, bytes], *, moved: bool = False) -> None:
        self.files = files
        self.moved = moved
        self.asked: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.asked.append(url)
        name = url.rsplit("/", 1)[1]
        if self.moved and not url.startswith("https://store.example/"):
            return httpx.Response(302, headers={"Location": f"https://store.example/{name}"})
        if name in self.files:
            return httpx.Response(200, content=self.files[name])
        return httpx.Response(404)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self), follow_redirects=True)


def nothing(*_: object) -> None:
    return None


def never() -> bool:
    return False


# -- a file is kept only if it is the one pinned ---------------------------------------------


def test_a_file_is_whole_only_if_it_is_exactly_the_one_pinned(tmp_path: Path) -> None:
    weights = tmp_path / "weights"
    weights.write_bytes(WEIGHTS)
    assert is_whole(weights, size=len(WEIGHTS), sha256=sha256(WEIGHTS), git_sha1=None)
    assert not is_whole(weights, size=len(WEIGHTS), sha256=sha256(b"other"), git_sha1=None)
    assert not is_whole(weights, size=len(WEIGHTS) - 1, sha256=sha256(WEIGHTS), git_sha1=None)
    config = tmp_path / "config.json"
    config.write_bytes(CONFIG)
    assert is_whole(config, size=len(CONFIG), sha256=None, git_sha1=git_sha1(CONFIG))
    assert not is_whole(config, size=len(CONFIG), sha256=None, git_sha1=git_sha1(b"x"))
    assert not is_whole(tmp_path / "missing", size=1, sha256=None, git_sha1=git_sha1(b"x"))
    # A file with no hash pinned is never taken for whole.
    assert not is_whole(config, size=len(CONFIG), sha256=None, git_sha1=None)


def test_a_setup_fetches_each_file_from_its_pinned_revision_and_tries_the_voice(
    tmp_path: Path,
) -> None:
    tier = a_tier(("config.json", CONFIG), ("voices/heart.pt", WEIGHTS))
    network = Network({"config.json": CONFIG, "heart.pt": WEIGHTS}, moved=True)
    paths = paths_in(tmp_path / "voice")
    said: list[tuple[str, int, int]] = []

    VoiceInstaller(paths, client=network.client()).install(
        tier, lambda message, done, total: said.append((message, done, total)), never
    )

    folder = paths.models / "Small-Voice"
    assert (folder / "config.json").read_bytes() == CONFIG
    assert (folder / "voices" / "heart.pt").read_bytes() == WEIGHTS
    assert network.asked[:2] == [
        f"https://huggingface.co/test/Small-Voice/resolve/{REVISION}/config.json",
        "https://store.example/config.json",
    ]
    downloads = [entry for entry in said if entry[0] == "Downloading the voice"]
    assert downloads[-1][1:] == (len(CONFIG) + len(WEIGHTS),) * 2
    assert said[-1] == ("Trying the voice", 1, 1)
    assert paths.ready(tier)
    # Nothing is left of the word said, or of a download.
    assert not list(paths.root.glob("probe*"))
    assert not list(paths.root.rglob("*.part"))

    # Asked again, nothing is downloaded again.
    network.asked.clear()
    VoiceInstaller(paths, client=network.client()).install(tier, nothing, never)
    assert network.asked == []


@pytest.mark.parametrize(
    "arrives",
    [WEIGHTS[:-1] + b"x", WEIGHTS + b"more", WEIGHTS[:-10]],
    ids=["changed", "longer", "shorter"],
)
def test_a_file_that_arrives_different_is_not_kept(tmp_path: Path, arrives: bytes) -> None:
    tier = a_tier(("voices/heart.pt", WEIGHTS))
    paths = paths_in(tmp_path / "voice")
    installer = VoiceInstaller(paths, client=Network({"heart.pt": arrives}).client())
    with pytest.raises(VoiceSetupError, match="didn’t arrive whole"):
        installer.install(tier, nothing, never)
    assert not [path for path in paths.root.rglob("*") if path.suffix in (".pt", ".part")]
    assert not paths.ready(tier)


def test_a_download_that_cannot_be_had_is_said_plainly(tmp_path: Path) -> None:
    tier = a_tier(("voices/heart.pt", WEIGHTS))
    paths = paths_in(tmp_path / "voice")
    with pytest.raises(VoiceSetupError) as missing:
        VoiceInstaller(paths, client=Network({}).client()).install(tier, nothing, never)
    assert missing.value.message == (
        "Couldn’t download the voice. Check the connection and try again."
    )

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    offline = httpx.Client(transport=httpx.MockTransport(unreachable))
    with pytest.raises(VoiceSetupError) as failed:
        VoiceInstaller(paths, client=offline).install(tier, nothing, never)
    assert failed.value.message == missing.value.message


def test_a_download_stopped_half_way_leaves_nothing_half_written(tmp_path: Path) -> None:
    tier = a_tier(("voices/heart.pt", WEIGHTS))
    paths = paths_in(tmp_path / "voice")
    asked = [0]

    def stopped_after_the_first_piece() -> bool:
        asked[0] += 1
        return asked[0] > 1

    installer = VoiceInstaller(paths, client=Network({"heart.pt": WEIGHTS}).client())
    with pytest.raises(VoiceSetupError, match="Stopped"):
        installer.install(tier, nothing, stopped_after_the_first_piece)
    assert not [path for path in paths.models.rglob("*") if path.is_file()]


def test_a_file_another_size_has_already_is_copied_and_not_downloaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = a_tier(("speech/model.bin", WEIGHTS), repo="test/First")
    second = a_tier(
        ("speech/model.bin", WEIGHTS),
        ("config.json", CONFIG),
        tier_id="standard",
        repo="test/Second",
    )
    monkeypatch.setattr(install_module, "TIERS", (first, second))
    network = Network({"model.bin": WEIGHTS, "config.json": CONFIG})
    paths = paths_in(tmp_path / "voice")
    VoiceInstaller(paths, client=network.client()).install(first, nothing, never)
    network.asked.clear()

    VoiceInstaller(paths, client=network.client()).install(second, nothing, never)
    assert [url.rsplit("/", 1)[1] for url in network.asked] == ["config.json"]
    assert (paths.models / "Second" / "speech" / "model.bin").read_bytes() == WEIGHTS


def test_a_setup_that_would_not_fit_on_the_disk_is_refused_before_anything_is_fetched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kokoro = find_tier("kokoro")
    assert kokoro is not None
    room = types.SimpleNamespace(total=10**12, used=10**12 - 10**8, free=10**8)
    monkeypatch.setattr(install_module.shutil, "disk_usage", lambda path: room)
    network = Network({})
    paths = paths_in(tmp_path / "voice")
    with pytest.raises(VoiceSetupError) as refused:
        VoiceInstaller(paths, client=network.client()).install(kokoro, nothing, never)
    gigabytes = max(1, round(room_needed(kokoro, paths) / 1e9))
    assert refused.value.message == (
        f"There isn’t room for this voice: it needs about {gigabytes} GB free."
    )
    assert network.asked == []


def test_only_what_is_not_here_yet_needs_room(tmp_path: Path) -> None:
    kokoro = find_tier("kokoro")
    assert kokoro is not None
    bare = paths_in(tmp_path / "bare", programs=False)
    # Nothing here: the models, and the programs installed beside pip's copy of them.
    assert room_needed(kokoro, bare) == room_needed(kokoro) > kokoro.repos[0].size
    # Programs another voice of the family set up are not counted again.
    ready = paths_in(tmp_path / "ready")
    assert room_needed(kokoro, ready) == kokoro.repos[0].size
    # Nor the files a stopped setup left, each of the size it should be.
    config = next(file for file in kokoro.repos[0].files if file.path == "config.json")
    placed = ready.models / kokoro.repos[0].folder / config.path
    placed.parent.mkdir(parents=True)
    placed.write_bytes(b"x" * config.size)
    assert room_needed(kokoro, ready) == kokoro.repos[0].size - config.size


def test_a_voice_set_up_by_hand_is_used_as_it_is(tmp_path: Path) -> None:
    paths = paths_in(tmp_path / "voice", borrowed=True)
    kokoro = find_tier("kokoro")
    assert kokoro is not None
    for act in (
        lambda: VoiceInstaller(paths).install(kokoro, nothing, never),
        lambda: VoiceInstaller(paths).remove(kokoro, []),
    ):
        with pytest.raises(VoiceSetupError, match="set up by hand"):
            act()


# -- the programs -------------------------------------------------------------------------


def a_pip(code: int = 0) -> tuple[list[list[str]], Callable[..., int]]:
    asked: list[list[str]] = []

    def pip(command: list[str], cancelled: Callable[[], bool], heard: Callable[[str], None]) -> int:
        asked.append(command)
        heard("collecting")
        heard("collecting")
        heard("installing")
        return code

    return asked, pip


def test_the_programs_are_installed_exactly_as_locked_in_an_environment_of_their_own(
    tmp_path: Path,
) -> None:
    """With the core's own Python making the environment, as it does in the app."""
    paths = paths_in(tmp_path / "voice", programs=False)
    lock = lock_for("kokoro")
    assert lock is not None
    asked, pip = a_pip()
    said: list[tuple[str, int, int]] = []
    tier = a_tier(("config.json", CONFIG))

    installer = VoiceInstaller(paths, run_pip=pip)
    installer.programs(tier, lock, lambda *entry: said.append(entry), never)

    python = paths.own_python("kokoro")
    assert python.is_file()
    (command,) = asked
    assert command[:5] == [str(python), "-I", "-m", "pip", "install"]
    for flag in ("--require-hashes", "--no-deps", "--only-binary=:all:", "--no-cache-dir"):
        assert flag in command
    assert command[command.index("--index-url") + 1] == "https://pypi.org/simple"
    assert Path(command[command.index("-r") + 1]).read_text(encoding="utf-8") == lock
    packages = len(re.findall(r"^[A-Za-z0-9]", lock, flags=re.MULTILINE))
    assert said[-2:] == [
        ("Downloading the voice’s programs", 2, packages),
        ("Installing the voice’s programs", 0, 0),
    ]
    mark = json.loads((paths.environment("kokoro") / SETUP_MARK).read_text(encoding="utf-8"))
    assert mark == setup_mark("kokoro")

    # Set up already: nothing is installed again.
    installer.programs(tier, lock, nothing, never)
    assert len(asked) == 1


class WithoutVenv(VoiceInstaller):
    """Makes the environment's Python without running venv, to be quick."""

    def make_environment(self, environment: Path) -> bool:
        python = self._paths.own_python("kokoro")
        python.parent.mkdir(parents=True, exist_ok=True)
        python.write_bytes(b"")
        return True


def test_programs_that_could_not_be_installed_leave_no_environment_behind(
    tmp_path: Path,
) -> None:
    paths = paths_in(tmp_path / "voice", programs=False)
    lock = lock_for("kokoro")
    assert lock is not None
    _, pip = a_pip(code=1)
    with pytest.raises(VoiceSetupError) as failed:
        WithoutVenv(paths, run_pip=pip).programs(a_tier(), lock, nothing, never)
    assert failed.value.message == (
        "Couldn’t download the voice’s programs. Check the connection and try again."
    )
    assert not paths.environment("kokoro").exists()


def test_programs_installed_for_another_version_of_adle_are_installed_again(
    tmp_path: Path,
) -> None:
    paths = paths_in(tmp_path / "voice")
    kokoro = find_tier("kokoro")
    assert kokoro is not None
    for repo in kokoro.repos:
        for file in repo.files:
            (paths.models / repo.folder / file.path).parent.mkdir(parents=True, exist_ok=True)
            (paths.models / repo.folder / file.path).write_bytes(b"")
    assert paths.ready(kokoro)
    marker = paths.environment("kokoro") / SETUP_MARK
    marker.write_text(json.dumps({**(setup_mark("kokoro") or {}), "lock": "older"}), "utf-8")
    assert not paths.ready(kokoro)
    asked, pip = a_pip()
    lock = lock_for("kokoro")
    assert lock is not None
    WithoutVenv(paths, run_pip=pip).programs(kokoro, lock, nothing, never)
    assert len(asked) == 1
    assert paths.ready(kokoro)


def test_an_environment_is_made_from_the_cores_python_by_the_name_venv_needs(
    tmp_path: Path,
) -> None:
    """Packaged for Windows, the core runs as adle-core.exe with python.exe beside it. venv
    names the Python it puts in an environment after the program it ran as, so an
    environment made from adle-core.exe would have no python.exe in it."""
    core = tmp_path / "core"
    core.mkdir()
    (core / "adle-core.exe").write_bytes(b"")
    assert base_python(str(core / "adle-core.exe")) == str(core / "adle-core.exe")
    (core / "python.exe").write_bytes(b"")
    assert base_python(str(core / "adle-core.exe")) == str(core / "python.exe")
    assert base_python(str(core / "python.exe")) == str(core / "python.exe")
    # Elsewhere the core runs as Python itself, by its own name.
    assert base_python("/opt/adle/resources/core/bin/python3.12") == (
        "/opt/adle/resources/core/bin/python3.12"
    )


def test_pip_runs_with_none_of_this_computers_settings_for_pip_or_python() -> None:
    environment = quiet_environment(
        {
            "PIP_TARGET": "elsewhere",
            "pip_index_url": "https://mirror.example/simple",
            "PYTHONPATH": "somewhere",
            "VIRTUAL_ENV": "another",
            "UV_INDEX": "another",
            "PATH": "the path",
            "HTTPS_PROXY": "http://proxy.example:8080",
        }
    )
    assert environment == {
        "PATH": "the path",
        "HTTPS_PROXY": "http://proxy.example:8080",
        "PIP_CONFIG_FILE": os.devnull,
        "PYTHONUTF8": "1",
    }
    # Torch for a Mac comes from the Python Package Index; elsewhere from PyTorch's own.
    assert torch_index("kokoro", "darwin") is None
    assert torch_index("kokoro", "win32") == "https://download.pytorch.org/whl/cpu"
    assert torch_index("qwen", "linux") == "https://download.pytorch.org/whl/cu128"


@pytest.mark.parametrize(
    ("family", "system"),
    [
        ("kokoro", "win32"),
        ("kokoro", "linux"),
        ("kokoro", "darwin"),
        ("qwen", "win32"),
        ("qwen", "linux"),
    ],
)
def test_every_program_a_voice_runs_with_is_pinned_with_its_hashes(
    family: str, system: str
) -> None:
    lock = lock_for(family, system)
    assert lock is not None
    entries = re.findall(r"^([A-Za-z0-9][^\s=@]*)(?:==\S+| @ https://\S+) \\$", lock, re.M)
    requirements = [line for line in lock.splitlines() if re.match(r"^[A-Za-z0-9]", line)]
    assert len(entries) == len(requirements) > 40
    for block in re.split(r"\n(?=[A-Za-z0-9])", lock.split("\n", 1)[1].strip()):
        assert re.search(r"--hash=sha256:[0-9a-f]{64}", block), block.splitlines()[0]
    names = {name.lower() for name in entries}
    assert "torch" in names
    # What the voice never runs, or what could only be built from source, is left out.
    assert not names & {"gradio", "sox", "docopt"}
    # A Qwen voice is offered only on a system with NVIDIA's cards and drivers for torch.
    assert lock_for("qwen", "darwin") is None


# -- taking a size away -------------------------------------------------------------------


def test_removing_a_size_keeps_what_another_size_here_still_needs(tmp_path: Path) -> None:
    paths = paths_in(tmp_path / "voice")
    for each in TIERS:
        for repo in each.repos:
            for file in repo.files:
                path = paths.models / repo.folder / file.path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"")
    paths.aligner_file().parent.mkdir(parents=True, exist_ok=True)
    paths.aligner_file().write_bytes(b"")
    kokoro, standard, expressive = TIERS
    if setup_mark("qwen") is None:
        pytest.skip("Qwen3-TTS is not offered on this system.")
    assert paths.ready_tiers() == list(TIERS)

    installer = VoiceInstaller(paths)
    installer.remove(standard, [kokoro, expressive])
    assert paths.ready_tiers() == [kokoro, expressive]
    # Its own model went; the programs and the aligner stay, for the other Qwen voice.
    assert not (paths.models / standard.repos[0].folder).exists()
    assert paths.environment("qwen").is_dir()
    assert paths.aligner_file().is_file()

    installer.remove(expressive, [kokoro])
    assert paths.ready_tiers() == [kokoro]
    assert not paths.environment("qwen").exists()
    assert not paths.aligner.exists()
    assert paths.environment("kokoro").is_dir()
