"""Setting up a natural voice on this computer, at the learner's word (ADR-042).

Three things are fetched, and nothing else: the programs the voice runs with, exactly the
versions locked in ``voice/data`` with every file's hash required (from the Python Package
Index and, for torch, PyTorch's own index); the voice's model files, from a fixed revision on
Hugging Face, each kept only if its hash is the one pinned in the catalogue; and for Qwen3-TTS
the aligner, the same way. Nothing of the learner's is sent: these are downloads.

The programs go into an environment of the voice's family made from the core's own Python
(``python -m venv``), never into the core's. A file already here with the right hash is not
fetched again, so a setup stopped half way goes on where it stopped.
"""

from __future__ import annotations

import errno
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2 as httpx

from adle_core.errors import AdleError
from adle_core.voice.catalog import (
    ALIGNER,
    INSTALLED_OVER_DOWNLOADED,
    TIERS,
    Download,
    ModelFile,
    Tier,
    download_size,
    program_bytes,
)
from adle_core.voice.runtime import SETUP_MARK, VoiceEngine, VoicePaths, lock_for, setup_mark

logger = logging.getLogger(__name__)

#: Where torch is built for each family: on the processor, or for NVIDIA's cards. On a Mac
#: it comes from the Python Package Index, as everything else does.
_TORCH_INDEX = {
    "kokoro": "https://download.pytorch.org/whl/cpu",
    "qwen": "https://download.pytorch.org/whl/cu128",
}


def torch_index(family: str, system: str = sys.platform) -> str | None:
    return None if system == "darwin" else _TORCH_INDEX[family]


def base_python(executable: str = sys.executable) -> str:
    """The Python an environment is made from: the core's own. Packaged for Windows, the core
    runs as ``adle-core.exe`` with ``python.exe`` beside it; venv names the Python it puts in
    an environment after the program it ran as, so the environment is made with python.exe."""
    here = Path(executable)
    beside = here.with_name("python.exe")
    if here.name.lower() != "python.exe" and here.suffix.lower() == ".exe" and beside.is_file():
        return str(beside)
    return executable


def quiet_environment(environ: dict[str, str] | None = None) -> dict[str, str]:
    """What venv and pip run with: none of this computer's settings for pip or Python, so
    that what is installed, and where, is exactly what the lock says. A proxy this computer
    uses is kept: these are downloads of files whose hashes are checked."""
    source = dict(os.environ) if environ is None else environ
    dropped = ("PIP_", "PYTHON", "VIRTUAL_ENV", "CONDA_", "UV_")
    environment = {
        key: value for key, value in source.items() if not key.upper().startswith(dropped)
    }
    environment.update({"PIP_CONFIG_FILE": os.devnull, "PYTHONUTF8": "1"})
    return environment


#: Read a large file this much at a time.
_CHUNK = 1024 * 1024
#: The longest the programs may take to install: torch for a graphics card is gigabytes.
_PROGRAMS_SECONDS = 3 * 60 * 60


class VoiceSetupError(AdleError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="voice_setup_failed")


Report = Callable[[str, int, int], None]
Cancelled = Callable[[], bool]


def room_needed(tier: Tier, paths: VoicePaths | None = None) -> int:
    """About how much of the disk a setup of this size takes, at most, while it works: its
    models, its programs installed, and pip's copy of what it downloaded until it is done.
    With ``paths``, only what is not here already: programs another voice of the family set
    up, or the files of a setup that was stopped."""
    if paths is None:
        missing = download_size(tier)
    else:
        missing = sum(
            file.size
            for repo in tier.repos
            for file in repo.files
            if not _sized(paths.models / repo.folder / file.path, file.size)
        )
        if tier.aligned and not _sized(paths.aligner_file(), ALIGNER.size):
            missing += ALIGNER.size
        if paths.programs_ready(tier.family):
            return missing
    programs = program_bytes(tier.family)
    return missing + int(programs * (1 + INSTALLED_OVER_DOWNLOADED[tier.family]))


def _sized(path: Path, size: int) -> bool:
    return path.is_file() and path.stat().st_size == size


def _git_blob_sha1(path: Path) -> str:
    digest = hashlib.sha1(usedforsecurity=False)
    digest.update(f"blob {path.stat().st_size}\0".encode())
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def is_whole(path: Path, *, size: int, sha256: str | None, git_sha1: str | None) -> bool:
    """Whether a file is here and is exactly the one pinned."""
    if not path.is_file() or path.stat().st_size != size:
        return False
    if sha256 is not None:
        return _sha256(path) == sha256
    if git_sha1 is not None:
        return _git_blob_sha1(path) == git_sha1
    return False


class VoiceInstaller:
    def __init__(
        self,
        paths: VoicePaths,
        *,
        client: httpx.Client | None = None,
        run_pip: Callable[[list[str], Cancelled, Callable[[str], None]], int] | None = None,
    ) -> None:
        self._paths = paths
        self._client = client
        self._run_pip = run_pip or _run_pip

    # -- the whole setup ------------------------------------------------------------------

    def install(self, tier: Tier, report: Report, cancelled: Cancelled) -> None:
        """Set a size of voice up, whole, or raise ``VoiceSetupError`` saying what failed."""
        try:
            self._install(tier, report, cancelled)
        except OSError as error:
            if error.errno == errno.ENOSPC:
                raise VoiceSetupError(
                    "There isn’t room for the voice on this computer. Free some space, then "
                    "try again."
                ) from error
            raise VoiceSetupError("Couldn’t save the voice. Try again.") from error

    def _install(self, tier: Tier, report: Report, cancelled: Cancelled) -> None:
        if self._paths.borrowed:
            raise VoiceSetupError("This voice was set up by hand and is used as it is.")
        lock = lock_for(tier.family)
        if lock is None:
            raise VoiceSetupError("This voice isn’t available on this kind of computer.")
        self._paths.root.mkdir(parents=True, exist_ok=True)
        needed = room_needed(tier, self._paths)
        if shutil.disk_usage(self._paths.root).free < needed:
            raise VoiceSetupError(
                f"There isn’t room for this voice: it needs about {_gigabytes(needed)} free."
            )
        self.programs(tier, lock, report, cancelled)
        files = [(repo, file) for repo in tier.repos for file in repo.files]
        total = sum(file.size for _, file in files) + (ALIGNER.size if tier.aligned else 0)
        done = 0
        for repo, file in files:
            target = self._paths.models / repo.folder / file.path
            self.fetch(repo.url(file), target, file, report, cancelled, done, total)
            done += file.size
        if tier.aligned:
            target = self._paths.aligner_file()
            self.fetch_download(ALIGNER, target, report, cancelled, done, total)
        report("Trying the voice", 1, 1)
        self.verify(tier)

    def programs(self, tier: Tier, lock: str, report: Report, cancelled: Cancelled) -> None:
        """The family's environment, with exactly the locked programs in it."""
        environment = self._paths.environment(tier.family)
        python = self._paths.own_python(tier.family)
        marker = environment / SETUP_MARK
        wanted = setup_mark(tier.family)
        try:
            found = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            found = None
        if python.is_file() and found == wanted:
            return
        report("Setting up the voice’s programs", 0, 1)
        shutil.rmtree(environment, ignore_errors=True)
        environment.parent.mkdir(parents=True, exist_ok=True)
        if not self.make_environment(environment) or not python.is_file():
            shutil.rmtree(environment, ignore_errors=True)
            raise VoiceSetupError("Couldn’t make a place for the voice’s programs.")
        locked = environment / "adle-requirements.txt"
        locked.write_text(lock, encoding="utf-8")
        packages = len(re.findall(r"^[A-Za-z0-9]", lock, flags=re.MULTILINE))
        report("Downloading the voice’s programs", 0, packages)
        seen = [0]

        def heard(event: str) -> None:
            if event == "installing":
                # Unpacked, torch is thousands of files: this takes minutes, and pip does not
                # say how far it has come.
                report("Installing the voice’s programs", 0, 0)
                return
            seen[0] = min(packages, seen[0] + 1)
            report("Downloading the voice’s programs", seen[0], packages)

        command = [
            str(python),
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
            "--progress-bar",
            "off",
            "--index-url",
            "https://pypi.org/simple",
        ]
        extra = torch_index(tier.family)
        if extra is not None:
            command += ["--extra-index-url", extra]
        code = self._run_pip([*command, "-r", str(locked)], cancelled, heard)
        if cancelled():
            shutil.rmtree(environment, ignore_errors=True)
            raise VoiceSetupError("Stopped.")
        if code != 0:
            shutil.rmtree(environment, ignore_errors=True)
            raise VoiceSetupError(
                "Couldn’t download the voice’s programs. Check the connection and try again."
            )
        marker.write_text(json.dumps(wanted), encoding="utf-8")

    def make_environment(self, environment: Path) -> bool:
        """An empty environment made from the core's own Python, with pip in it."""
        made = subprocess.run(  # noqa: S603 - the core's own Python, with fixed arguments
            [base_python(), "-I", "-m", "venv", str(environment)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=600,
            env=quiet_environment(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return made.returncode == 0

    # -- files ----------------------------------------------------------------------------

    def fetch(
        self,
        url: str,
        target: Path,
        file: ModelFile,
        report: Report,
        cancelled: Cancelled,
        done: int,
        total: int,
    ) -> None:
        if is_whole(target, size=file.size, sha256=file.sha256, git_sha1=file.git_sha1):
            return
        # The same file of another of the voice's models, already here and checked.
        twin = self._twin(file)
        if twin is not None:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(twin, target)
            if is_whole(target, size=file.size, sha256=file.sha256, git_sha1=file.git_sha1):
                return
        self._download(url, target, file.size, report, cancelled, done, total)
        if not is_whole(target, size=file.size, sha256=file.sha256, git_sha1=file.git_sha1):
            target.unlink(missing_ok=True)
            raise VoiceSetupError("A file of the voice didn’t arrive whole. Try again.")

    def fetch_download(
        self,
        download: Download,
        target: Path,
        report: Report,
        cancelled: Cancelled,
        done: int,
        total: int,
    ) -> None:
        if is_whole(target, size=download.size, sha256=download.sha256, git_sha1=None):
            return
        self._download(download.url, target, download.size, report, cancelled, done, total)
        if not is_whole(target, size=download.size, sha256=download.sha256, git_sha1=None):
            target.unlink(missing_ok=True)
            raise VoiceSetupError("A file of the voice didn’t arrive whole. Try again.")

    def _twin(self, file: ModelFile) -> Path | None:
        for tier in TIERS:
            for repo in tier.repos:
                for other in repo.files:
                    same = (file.sha256 and other.sha256 == file.sha256) or (
                        file.git_sha1 and other.git_sha1 == file.git_sha1
                    )
                    if not same:
                        continue
                    path = self._paths.models / repo.folder / other.path
                    if path.is_file() and path.stat().st_size == file.size:
                        return path
        return None

    def _download(
        self,
        url: str,
        target: Path,
        size: int,
        report: Report,
        cancelled: Cancelled,
        done: int,
        total: int,
    ) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + ".part")
        client = self._client or httpx.Client(
            # As pip's downloads go: through this computer's proxy, if it has one.
            follow_redirects=True,
            trust_env=True,
            timeout=httpx.Timeout(60.0),
        )
        try:
            # Hugging Face sends a large file from where it keeps it: the address it redirects
            # to is followed. What arrives is kept only if its hash is the one pinned.
            with client.stream("GET", url) as answer:
                if answer.status_code != 200:
                    raise VoiceSetupError(
                        "Couldn’t download the voice. Check the connection and try again."
                    )
                received = 0
                last = -1
                with partial.open("wb") as handle:
                    for chunk in answer.iter_bytes(_CHUNK):
                        if cancelled():
                            raise VoiceSetupError("Stopped.")
                        handle.write(chunk)
                        received += len(chunk)
                        if received > size:
                            raise VoiceSetupError("A file of the voice didn’t arrive whole.")
                        step = (done + received) * 100 // max(1, total)
                        if step != last:
                            last = step
                            report("Downloading the voice", done + received, total)
            os.replace(partial, target)
        except httpx.HTTPError as error:
            raise VoiceSetupError(
                "Couldn’t download the voice. Check the connection and try again."
            ) from error
        finally:
            partial.unlink(missing_ok=True)
            if self._client is None:
                client.close()

    # -- checking it works -------------------------------------------------------------

    def verify(self, tier: Tier) -> None:
        """The voice says a word, here, before it is called set up."""
        probe = self._paths.root / "probe.clip"
        voice: dict[str, Any] = {"tier": tier.id}
        if tier.default_speaker:
            voice["speaker"] = tier.default_speaker
        else:
            voice["design"] = "A calm, clear voice."
            voice["reference"] = str(self._paths.root / "probe-voice.wav")
        leftovers = [probe]
        if "reference" in voice:
            leftovers += [Path(voice["reference"]), Path(f"{voice['reference']}.txt")]
        engine = VoiceEngine(self._paths, tier.family)
        try:
            engine.speak("Ready.", voice, probe)
        except AdleError as error:
            raise VoiceSetupError("The voice was set up but couldn’t speak. Try again.") from error
        finally:
            engine.close()
            for leftover in leftovers:
                leftover.unlink(missing_ok=True)

    # -- taking it away ------------------------------------------------------------------

    def remove(self, tier: Tier, keep: list[Tier]) -> None:
        """Remove a size of voice: its models and, if no size left needs it, its programs.
        ``keep`` are the sizes that stay."""
        if self._paths.borrowed:
            raise VoiceSetupError("This voice was set up by hand and is used as it is.")
        needed = {repo.folder for other in keep for repo in other.repos}
        for repo in tier.repos:
            if repo.folder not in needed:
                shutil.rmtree(self._paths.models / repo.folder, ignore_errors=True)
        if not any(other.family == tier.family for other in keep):
            shutil.rmtree(self._paths.environment(tier.family), ignore_errors=True)
        if tier.aligned and not any(other.aligned for other in keep):
            shutil.rmtree(self._paths.aligner, ignore_errors=True)


def _gigabytes(size: int) -> str:
    return f"{max(1, round(size / 1_000_000_000))} GB"


_COLLECTING = re.compile(r"^Collecting ")
_INSTALLING = re.compile(r"^Installing collected packages")


def _run_pip(command: list[str], cancelled: Cancelled, heard: Callable[[str], None]) -> int:
    """Run pip, stopping it if asked to, and say each package it begins on. What pip prints
    names packages and nothing else; none of it is kept."""
    process = subprocess.Popen(  # noqa: S603 - the voice's own Python and pip, fixed arguments
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=quiet_environment(),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert process.stdout is not None
    try:
        for line in process.stdout:
            if cancelled():
                process.kill()
                break
            if _COLLECTING.match(line):
                heard("collecting")
            elif _INSTALLING.match(line):
                heard("installing")
        return process.wait(timeout=_PROGRAMS_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        return 1
    finally:
        process.stdout.close()
