"""What a natural voice is made of, pinned and checkable (ADR-042).

Three natural voices, from the lightest to the richest, past the computer's own voice:
Kokoro (82M, runs on the processor), Qwen3-TTS 0.6B and Qwen3-TTS 1.7B (on an NVIDIA graphics
card). Each comes from a fixed revision on Hugging Face with every file's size and hash, all of
them under Apache-2.0. Qwen3-TTS does not say when it says each word, so its voices come with
the aligner that finds out (torchaudio's English wav2vec 2.0 model, from fairseq, MIT); Kokoro
knows, from its own durations. Nothing is fetched that is not listed here, and nothing listed
is kept unless its hash is right.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

TierId = Literal["kokoro", "standard", "expressive"]
#: Voices of one family run with the same programs, in one environment.
Family = Literal["kokoro", "qwen"]


@dataclass(frozen=True, slots=True)
class ModelFile:
    """One file of a model at its revision: a large one by its SHA-256 (as Git LFS keeps it),
    a small one by its Git blob hash (as Git keeps it)."""

    path: str
    size: int
    sha256: str | None = None
    git_sha1: str | None = None


@dataclass(frozen=True, slots=True)
class ModelRepo:
    #: The repository on Hugging Face, and the folder it is kept in here.
    repo: str
    revision: str
    files: tuple[ModelFile, ...]

    @property
    def folder(self) -> str:
        return self.repo.split("/", 1)[1]

    def url(self, file: ModelFile) -> str:
        return f"https://huggingface.co/{self.repo}/resolve/{self.revision}/{file.path}"

    @property
    def size(self) -> int:
        return sum(file.size for file in self.files)


@dataclass(frozen=True, slots=True)
class Download:
    url: str
    #: Where it is kept, under the voice's folder.
    path: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class Speaker:
    id: str
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class Tier:
    id: TierId
    name: str
    description: str
    family: Family
    repos: tuple[ModelRepo, ...]
    #: The least memory on an NVIDIA graphics card it runs in, with room to spare. None: it
    #: runs on the processor, and needs no such card.
    min_memory_gb: float | None
    #: Its voices to choose from. A voice designed for each lesson has none.
    speakers: tuple[Speaker, ...]
    default_speaker: str | None
    #: It does not know when it says each word, and needs the aligner to find out.
    aligned: bool


def _files(*entries: tuple[str, int, str]) -> tuple[ModelFile, ...]:
    """Files from (path, size, hash): a 64-character hash is SHA-256, a 40-character one Git's."""
    return tuple(
        ModelFile(path, size, sha256=digest)
        if len(digest) == 64
        else ModelFile(path, size, git_sha1=digest)
        for path, size, digest in entries
    )


#: What each of the three repositories shares: its tokenizer and its speech tokenizer.
_SHARED = (
    ("generation_config.json", 245, "1872b16d4535564abf2db5d6debe6cddd82b7f2e"),
    ("merges.txt", 1671839, "20024bfe7c83998e9aeaf98a0cd6a2ce6306c2f0"),
    ("preprocessor_config.json", 127, "0525dd953bb9241912f7147666f0d535165d5d4f"),
    ("speech_tokenizer/config.json", 2336, "06cc8dc4c5ec8a1929086b71b98c313020d9268b"),
    ("speech_tokenizer/configuration.json", 76, "ab58e2eaf53cd14a1a2a7527d9261ceea93a24cd"),
    (
        "speech_tokenizer/model.safetensors",
        682293092,
        "836b7b357f5ea43e889936a3709af68dfe3751881acefe4ecf0dbd30ba571258",
    ),
    ("speech_tokenizer/preprocessor_config.json", 234, "ba40914f4f49ab98a8ca545d4892ef7291a39592"),
    ("tokenizer_config.json", 7344, "6ff9fd60cc623bb54bbd603cbd418c97a11528d7"),
    ("vocab.json", 2776833, "4783fe10ac3adce15ac8f358ef5462739852c569"),
)

#: Read from the Hugging Face API at these revisions on 2026-11-21.
CUSTOM_VOICE_0_6B = ModelRepo(
    "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
    "85e237c12c027371202489a0ec509ded67b5e4b5",
    _files(
        ("config.json", 4908, "5e8d5fc100536984e3a89bd87ef08e59e322b29b"),
        (
            "model.safetensors",
            1811626576,
            "bc3c7e785eb961179c25450d1acff03f839e0002f2f3a5aeb67b5735c0fa2adb",
        ),
        *_SHARED,
    ),
)
VOICE_DESIGN_1_7B = ModelRepo(
    "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    "5ecdb67327fd37bb2e042aab12ff7391903235d3",
    _files(
        ("config.json", 4421, "2c2c027c574a85c0d5a5d48e3cfed1a8a051ff9d"),
        (
            "model.safetensors",
            3833402552,
            "391e8db219f292c515297cdceeb43e4eae67cdde35fa57e79a6a8a532fca0522",
        ),
        *_SHARED,
    ),
)
BASE_1_7B = ModelRepo(
    "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    "fd4b254389122332181a7c3db7f27e918eec64e3",
    _files(
        ("config.json", 4494, "81b57e8e790c07e8fa7f82d8bdfd7574d485c396"),
        (
            "model.safetensors",
            3857413744,
            "38fc7fc51c5e776e840414b6fd443962e9411b9654888fd7913e4da643cb857c",
        ),
        *_SHARED,
    ),
)

KOKORO_82M = ModelRepo(
    "hexgrad/Kokoro-82M",
    "f3ff3571791e39611d31c381e3a41a3af07b4987",
    _files(
        ("config.json", 2351, "14a726edd3718279eac426630879ff743955b16a"),
        (
            "kokoro-v1_0.pth",
            327212226,
            "496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4",
        ),
        (
            "voices/af_heart.pt",
            523425,
            "0ab5709b8ffab19bfd849cd11d98f75b60af7733253ad0d67b12382a102cb4ff",
        ),
        (
            "voices/af_bella.pt",
            523425,
            "8cb64e02fcc8de0327a8e13817e49c76c945ecf0052ceac97d3081480e8e48d6",
        ),
        (
            "voices/bf_emma.pt",
            523420,
            "d0a423deabf4a52b4f49318c51742c54e21bb89bbbe9a12141e7758ddb5da701",
        ),
        (
            "voices/am_michael.pt",
            523435,
            "9a443b79a4b22489a5b0ab7c651a0bcd1a30bef675c28333f06971abbd47bd37",
        ),
        (
            "voices/am_fenrir.pt",
            523430,
            "98e507eca1db08230ae3b6232d59c10aec9630022d19accac4f5d12fcec3c37a",
        ),
    ),
)

#: Finds each word in what was said. torchaudio looks for it in its hub folder by this name.
ALIGNER = Download(
    url="https://download.pytorch.org/torchaudio/models/wav2vec2_fairseq_base_ls960_asr_ls960.pth",
    path="aligner/hub/checkpoints/wav2vec2_fairseq_base_ls960_asr_ls960.pth",
    size=377664473,
    sha256="488fd4f16de84438ffc945334278c1b9fb9b7159a806c1080b16111a958c945d",
)

#: Kokoro's best-graded English voices, as its makers grade them (VOICES.md, 2026-11-21).
KOKORO_SPEAKERS: tuple[Speaker, ...] = (
    Speaker("af_heart", "Heart", "A warm American voice."),
    Speaker("af_bella", "Bella", "A bright American voice."),
    Speaker("bf_emma", "Emma", "A calm British voice."),
    Speaker("am_michael", "Michael", "A steady American voice."),
    Speaker("am_fenrir", "Fenrir", "A deep American voice."),
)
#: The small Qwen model's speakers that read English, as its makers describe them. It has
#: others, made for Chinese, Japanese and Korean.
QWEN_SPEAKERS: tuple[Speaker, ...] = (
    Speaker("Aiden", "Aiden", "A sunny American voice."),
    Speaker("Ryan", "Ryan", "A dynamic voice with rhythm."),
    Speaker("Serena", "Serena", "A warm, gentle voice."),
    Speaker("Vivian", "Vivian", "A bright young voice."),
)

#: From the lightest to the richest. The computer's own voice comes before them all.
TIERS: tuple[Tier, ...] = (
    Tier(
        "kokoro",
        "Natural",
        "A natural voice that runs on any recent computer. Kokoro.",
        "kokoro",
        (KOKORO_82M,),
        min_memory_gb=None,
        speakers=KOKORO_SPEAKERS,
        default_speaker="af_heart",
        aligned=False,
    ),
    Tier(
        "standard",
        "Rich",
        "A richer voice, on an NVIDIA graphics card. Qwen3-TTS 0.6B.",
        "qwen",
        (CUSTOM_VOICE_0_6B,),
        min_memory_gb=4.0,
        speakers=QWEN_SPEAKERS,
        default_speaker="Aiden",
        aligned=True,
    ),
    Tier(
        "expressive",
        "Expressive",
        "A voice designed for each lesson, to suit what it teaches, on an NVIDIA graphics "
        "card. Qwen3-TTS 1.7B.",
        "qwen",
        (VOICE_DESIGN_1_7B, BASE_1_7B),
        min_memory_gb=8.0,
        speakers=(),
        default_speaker=None,
        aligned=True,
    ),
)

#: How a lesson sounds when nothing more is known about it.
DEFAULT_DESIGN = (
    "A warm, clear and patient teacher's voice, mid-pitched and unhurried, "
    "gently enthusiastic, speaking natural English."
)


#: What each family's programs come to, downloaded, on each system it is offered on: torch
#: above all, built for the processor or for NVIDIA's cards with their libraries. Measured
#: from the locks on 2026-11-21, the wheel each system takes of each package.
PROGRAM_BYTES: dict[tuple[str, str], int] = {
    ("kokoro", "win32"): 231_000_000,
    ("kokoro", "linux"): 352_000_000,
    ("kokoro", "darwin"): 182_000_000,
    ("qwen", "win32"): 2_909_000_000,
    ("qwen", "linux"): 4_134_000_000,
}
#: And installed, against what was downloaded for them: measured on Windows.
INSTALLED_OVER_DOWNLOADED: dict[str, float] = {"kokoro": 3.7, "qwen": 1.7}


def program_bytes(family: str, system: str = sys.platform) -> int:
    return PROGRAM_BYTES.get((family, system), 0)


def tier(tier_id: str) -> Tier | None:
    return next((candidate for candidate in TIERS if candidate.id == tier_id), None)


def download_size(chosen: Tier) -> int:
    """What the models of a tier, and the aligner if it needs one, come to in bytes. Files the
    repositories share are counted once: they are fetched once."""
    seen: set[str] = set()
    total = ALIGNER.size if chosen.aligned else 0
    for repo in chosen.repos:
        for file in repo.files:
            key = file.sha256 or file.git_sha1 or f"{repo.repo}/{file.path}"
            if key in seen:
                continue
            seen.add(key)
            total += file.size
    return total
