"""Where the natural voice lives, whether it is ready, and the engine that speaks (ADR-042).

The voice is an optional download kept under the data folder: a Python environment for each
family of voice (``voice/env-kokoro`` with torch for the processor and Kokoro,
``voice/env-qwen`` with torch for an NVIDIA card and Qwen3-TTS), the models
(``voice/models``), the aligner (``voice/aligner``), and the clips spoken (``voice/clips``). The
engine runs in the environment of the voice chosen, as a process of its own (``engine.py``),
and is spoken to over its standard input and output. The core never imports what it imports.

For development, ``ADLE_VOICE_KOKORO_PYTHON``, ``ADLE_VOICE_QWEN_PYTHON``,
``ADLE_VOICE_MODELS`` and ``ADLE_VOICE_ALIGNER`` point at voices set up elsewhere, and
``ADLE_VOICE_ENGINE`` at another engine program (the tests use one that speaks nothing).
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from adle_core.errors import AdleError
from adle_core.voice.catalog import ALIGNER, TIERS, Family, Tier

PYTHON_ENVS = {"kokoro": "ADLE_VOICE_KOKORO_PYTHON", "qwen": "ADLE_VOICE_QWEN_PYTHON"}
MODELS_ENV = "ADLE_VOICE_MODELS"
ALIGNER_ENV = "ADLE_VOICE_ALIGNER"
ENGINE_ENV = "ADLE_VOICE_ENGINE"

#: Written into a family's environment once its programs are set up whole: the lock they
#: were installed from and the Python they were installed for.
SETUP_MARK = "adle-setup.json"
_INSIDE = "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
_SYSTEMS = {"win32": "windows", "linux": "linux", "darwin": "macos"}

#: The first answer waits for the models to load and the card to warm up.
FIRST_ANSWER_SECONDS = 600.0
#: Any later one is a line or two of speech.
ANSWER_SECONDS = 300.0


class VoiceUnavailableError(AdleError):
    def __init__(self, message: str = "The natural voice isn’t set up on this computer.") -> None:
        super().__init__(message, code="voice_unavailable")


class VoiceEngineError(AdleError):
    def __init__(self, message: str = "The natural voice couldn’t speak this.") -> None:
        super().__init__(message, code="voice_failed")


def python_version() -> str:
    """The Python the core runs on, which the voice's programs are installed for."""
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def lock_for(family: str, system: str = sys.platform) -> str | None:
    """The locked programs of a family for this system, or None where it is not offered."""
    name = f"{family}-{_SYSTEMS.get(system, system)}.txt"
    found = resources.files("adle_core.voice.data").joinpath(name)
    return found.read_text(encoding="utf-8") if found.is_file() else None


@functools.cache
def lock_digest(family: str, system: str = sys.platform) -> str | None:
    lock = lock_for(family, system)
    return hashlib.sha256(lock.encode("utf-8")).hexdigest() if lock is not None else None


def setup_mark(family: str) -> dict[str, str] | None:
    """What a family's environment says when its programs are exactly this Adle's."""
    digest = lock_digest(family)
    return {"lock": digest, "python": python_version()} if digest is not None else None


@dataclass(frozen=True, slots=True)
class VoicePaths:
    root: Path
    #: The Python of each family's environment.
    pythons: dict[str, Path]
    models: Path
    aligner: Path
    engine: Path
    clips: Path
    #: Set by a developer: a voice set up elsewhere, used as it is and never removed.
    borrowed: bool

    @classmethod
    def under(cls, data_dir: Path, environ: Mapping[str, str] = os.environ) -> VoicePaths:
        root = data_dir / "voice"
        pythons: dict[str, Path] = {}
        borrowed = False
        for family, variable in PYTHON_ENVS.items():
            given = environ.get(variable, "").strip()
            borrowed = borrowed or bool(given)
            pythons[family] = Path(given) if given else root / f"env-{family}" / _INSIDE
        models = environ.get(MODELS_ENV, "").strip()
        aligner = environ.get(ALIGNER_ENV, "").strip()
        engine = environ.get(ENGINE_ENV, "").strip()
        return cls(
            root=root,
            pythons=pythons,
            models=Path(models) if models else root / "models",
            aligner=Path(aligner) if aligner else root / "aligner",
            engine=Path(engine) if engine else Path(__file__).with_name("engine.py"),
            clips=root / "clips",
            borrowed=borrowed,
        )

    def python(self, family: Family) -> Path:
        """The Python a family's engine runs on: its own environment's, or one borrowed."""
        return self.pythons[family]

    def environment(self, family: Family) -> Path:
        """Where a family's programs are installed by Adle. Only this is ever removed."""
        return self.root / f"env-{family}"

    def own_python(self, family: Family) -> Path:
        return self.environment(family) / _INSIDE

    def aligner_file(self) -> Path:
        return self.aligner / "hub" / "checkpoints" / Path(ALIGNER.path).name

    def programs_ready(self, family: Family) -> bool:
        """Whether a family's programs are here and are exactly the ones this Adle locks,
        for the Python it runs on. Programs from another version are set up again."""
        if not self.python(family).is_file():
            return False
        if self.borrowed:
            return True
        try:
            mark = json.loads((self.environment(family) / SETUP_MARK).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        wanted = setup_mark(family)
        return wanted is not None and mark == wanted

    def ready(self, tier: Tier) -> bool:
        """Whether a size of voice is here, whole: its programs, models and aligner."""
        if not self.programs_ready(tier.family):
            return False
        if tier.aligned and not self.aligner_file().is_file():
            return False
        return all(
            (self.models / repo.folder / file.path).is_file()
            for repo in tier.repos
            for file in repo.files
        )

    def ready_tiers(self) -> list[Tier]:
        return [tier for tier in TIERS if self.ready(tier)]


@dataclass(frozen=True, slots=True)
class Spoken:
    #: How long the clip is, in seconds.
    seconds: float
    #: Where each word is: its place in the text, and its time in the clip.
    words: list[dict[str, float | int]]


class VoiceEngine:
    """One engine process, and one request to it at a time."""

    def __init__(self, paths: VoicePaths, family: Family) -> None:
        self._paths = paths
        self._python = paths.python(family)
        self._process: subprocess.Popen[str] | None = None
        self._reader: threading.Thread | None = None
        self._answers: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.Lock()
        self._next_id = 0
        self._answered_once = False

    def _start(self) -> subprocess.Popen[str]:
        if self._process is not None and self._process.poll() is None:
            return self._process
        environment = {
            key: value for key, value in os.environ.items() if not key.startswith("PYTHON")
        }
        environment.update(
            {
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "HF_HUB_DISABLE_TELEMETRY": "1",
                "PYTHONUTF8": "1",
                "PYTHONUNBUFFERED": "1",
            }
        )
        self._process = subprocess.Popen(  # noqa: S603 - a fixed program and paths of Adle's own
            [
                str(self._python),
                # As isolated as the core: no PYTHON* variables, no user packages, nothing
                # from the current folder.
                "-I",
                "-X",
                "utf8",
                str(self._paths.engine),
                str(self._paths.models),
                str(self._paths.aligner),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            # What the libraries say about themselves is of no use to the learner, and the
            # text being spoken is the learner's: nothing of it is kept.
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env=environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self._answers = queue.Queue()
        self._answered_once = False
        process = self._process

        def read() -> None:
            assert process.stdout is not None
            for line in process.stdout:
                self._answers.put(line)
            self._answers.put(None)

        self._reader = threading.Thread(target=read, daemon=True, name="voice-engine")
        self._reader.start()
        return process

    def request(
        self, payload: dict[str, Any], cancelled: Callable[[], bool] = lambda: False
    ) -> dict[str, Any]:
        with self._lock:
            process = self._start()
            self._next_id += 1
            ident = self._next_id
            assert process.stdin is not None
            try:
                process.stdin.write(json.dumps({**payload, "id": ident}) + "\n")
                process.stdin.flush()
            except OSError as error:
                self.close()
                raise VoiceEngineError() from error
            limit = ANSWER_SECONDS if self._answered_once else FIRST_ANSWER_SECONDS
            deadline = time.monotonic() + limit
            while True:
                if cancelled():
                    # A line cannot be stopped half spoken: the engine is stopped instead.
                    self.close()
                    raise VoiceEngineError("Stopped.")
                if time.monotonic() > deadline:
                    self.close()
                    raise VoiceEngineError("The natural voice took too long to answer.")
                try:
                    line = self._answers.get(timeout=0.25)
                except queue.Empty:
                    continue
                if line is None:
                    self.close()
                    raise VoiceEngineError("The natural voice stopped.")
                try:
                    answer = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(answer, dict) or answer.get("id") != ident:
                    continue
                self._answered_once = True
                if not answer.get("ok"):
                    raise VoiceEngineError()
                return answer

    def hello(self) -> dict[str, Any]:
        return self.request({"op": "hello"})

    def speak(
        self,
        text: str,
        voice: dict[str, Any],
        out: Path,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> Spoken:
        answer = self.request(
            {"op": "speak", "text": text, "voice": voice, "out": str(out)}, cancelled
        )
        words = answer.get("words")
        seconds = answer.get("seconds")
        if not isinstance(words, list) or not isinstance(seconds, int | float) or not out.is_file():
            raise VoiceEngineError()
        clean = [
            {
                "index": int(word["index"]),
                "length": int(word["length"]),
                "start": float(word["start"]),
                "end": float(word["end"]),
            }
            for word in words
            if isinstance(word, dict)
            and all(
                isinstance(word.get(key), int | float)
                for key in ("index", "length", "start", "end")
            )
        ]
        return Spoken(seconds=float(seconds), words=clean)

    def close(self) -> None:
        """Stop the engine: it ends when its input does, or is ended. Nothing is left open."""
        process, self._process = self._process, None
        reader, self._reader = self._reader, None
        if process is None:
            return
        try:
            if process.stdin is not None:
                process.stdin.close()
            process.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
            process.wait(timeout=10)
        if reader is not None:
            reader.join(timeout=10)
        if process.stdout is not None:
            process.stdout.close()
