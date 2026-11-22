"""What this computer can run of the natural voices (ADR-042).

The lightest voice of all is the computer's own and needs nothing. Kokoro runs on the
processor of any recent computer for which torch is built (Windows and Linux on Intel or AMD,
and a Mac with Apple's processor). Qwen3-TTS needs an NVIDIA graphics card with enough
memory: 4 GB for the smaller, 8 GB for the larger. The card is found by asking NVIDIA's own
tool, which is there wherever its driver is; nothing is installed to find out.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass

from adle_core.voice.catalog import Tier

#: Kokoro runs where torch is built for the processor: these, as platform.machine() names them.
_PROCESSORS = {
    "win32": {"amd64", "x86_64"},
    "linux": {"x86_64", "amd64"},
    "darwin": {"arm64"},
}
#: Qwen3-TTS runs where torch is built for NVIDIA's cards.
_WITH_CUDA = {"win32", "linux"}


@dataclass(frozen=True, slots=True)
class Hardware:
    system: str
    machine: str
    #: The NVIDIA graphics card, when there is one, and how much memory it has.
    gpu: str | None
    gpu_memory_gb: float | None


@dataclass(frozen=True, slots=True)
class Fit:
    fits: bool
    #: Why not, in a sentence, when it does not.
    why: str = ""


def nvidia_card(
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
) -> tuple[str, float] | None:
    """The first NVIDIA card's name and memory in GB, as its driver's tool reports them."""
    tool = which("nvidia-smi")
    if tool is None:
        return None
    try:
        found = run(
            [tool, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if found.returncode != 0:
        return None
    first = (found.stdout or "").strip().splitlines()[:1]
    if not first:
        return None
    name, _, memory = first[0].rpartition(",")
    try:
        megabytes = float(memory.strip())
    except ValueError:
        return None
    name = " ".join(name.split())[:80]
    return (name, round(megabytes / 1024, 1)) if name else None


def detect(card: Callable[[], tuple[str, float] | None] = nvidia_card) -> Hardware:
    found = card() if sys.platform in _WITH_CUDA else None
    return Hardware(
        system=sys.platform,
        machine=platform.machine().lower(),
        gpu=found[0] if found else None,
        gpu_memory_gb=found[1] if found else None,
    )


def fit(tier: Tier, hardware: Hardware) -> Fit:
    """Whether a size of voice runs on this computer, and why not when it does not."""
    if tier.min_memory_gb is None:
        if hardware.machine in _PROCESSORS.get(hardware.system, set()):
            return Fit(True)
        return Fit(False, "It doesn’t run on this kind of computer.")
    if hardware.system not in _WITH_CUDA:
        return Fit(False, "It needs an NVIDIA graphics card, which this computer can’t use.")
    if hardware.gpu is None or hardware.gpu_memory_gb is None:
        return Fit(False, "It needs an NVIDIA graphics card.")
    if hardware.gpu_memory_gb < tier.min_memory_gb:
        return Fit(
            False,
            f"It needs an NVIDIA graphics card with {tier.min_memory_gb:g} GB of memory; "
            f"this one has {hardware.gpu_memory_gb:g} GB.",
        )
    return Fit(True)
