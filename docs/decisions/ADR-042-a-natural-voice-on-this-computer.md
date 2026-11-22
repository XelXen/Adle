# ADR-042: A natural voice, set up on this computer at the learner's word

- **Status:** Accepted
- **Date:** 2026-11-21
- **Builds on:** ADR-013 (narration by the computer's own voices, words marked only where
  the voice says where it is) and ADR-035 (a lesson is watched, its words along its foot).

## Context

The computer's own voices are what Adle read lessons with, and they sound like what they
are. The owner asked for something "much more natural but still local": Qwen3-TTS, 0.6B for
light machines and 1.7B where the machine can run it, with 1.7B's voice design used to
design a voice for each lesson when its transcript is written. Then, as a ladder: "if the
hardware can support it then system tts for most lightweight then kokoro, then qwen 0.6B and
then 1.7B with natural voice thing".

Measured on the development machine (an RTX 4080 Laptop GPU with 12 GB): Kokoro-82M speaks
4.6 times faster than real time on the processor alone and is ready in 2.3 s; Qwen3-TTS 0.6B
spoke 11.2 s of speech in 8.0 s on the card; 1.7B designed a voice and spoke two lines in
36 s, loading included. Qwen3-TTS does not say when it says each word; Kokoro does.

## Decisions

- **Four voices, from the lightest to the richest**, and the learner chooses:
  - **Computer's voice:** as before (ADR-013). Always there, nothing to set up.
  - **Natural:** Kokoro-82M, on the processor, on Windows and Linux (x86-64) and on a Mac
    with Apple's processor. Five speakers. About 0.6 GB to download.
  - **Rich:** Qwen3-TTS 12 Hz 0.6B CustomVoice, on an NVIDIA graphics card with at least
    4 GB, on Windows and Linux. Four speakers. About 5.8 GB.
  - **Expressive:** Qwen3-TTS 12 Hz 1.7B: VoiceDesign designs a voice for each lesson from a
    sentence written with the lesson, and 1.7B Base speaks every line in it. An NVIDIA card
    with at least 8 GB. About 12 GB.
  What this computer can run is found once a run (the system, the processor, and the card's
  name and memory as `nvidia-smi` reports them), each voice that cannot run says why in a
  sentence, and the richest that can is offered as the best for this computer.
- **Where each word is said is known, never guessed.** Kokoro's own durations; for
  Qwen3-TTS, forced alignment with torchaudio's English wav2vec 2.0 model (from fairseq,
  MIT; not torchaudio's MMS aligner, whose weights are CC-BY-NC). A number is found as it is
  said ("two point five"). A word that cannot be placed is not marked.
- **A lesson is recorded once, in the background, and nothing waits for it.** Each distinct
  line is recorded in the voice in use, as a clip with the time of each word, in a lane of
  its own (`voice`) so that it never waits behind a lesson being written. A clip is named by
  the voice and the words, so a lesson whose words or voice change is recorded again, and
  nothing is played in a voice that was not chosen. A line not recorded yet is read by the
  computer's voice. The clips are kept under the data folder (`voice/clips/<lesson>`), and
  go with their lesson, their course, or their voice.
- **A voice is set up only at the learner's word**, in Settings, which says what each one
  downloads before anything is, and where from one press away. One at a time, in the
  background, with its progress; it can be stopped, and a setup stopped or broken off goes
  on where it was.
  - **Its programs** go into an environment of the voice's family (`voice/env-kokoro`,
    `voice/env-qwen`), made with the core's own Python (`venv` and `ensurepip`, which the
    package now keeps, and on Windows `python.exe` beside the core's `adle-core.exe`: venv
    names the Python it puts in an environment after the program it ran as). pip installs exactly the lock for this system
    (`adle_core/voice/data/<family>-<system>.txt`, made by `scripts/dev/voice_locks.sh`):
    `--require-hashes --no-deps --only-binary=:all: --no-cache-dir`, from the Python Package
    Index and, for torch, PyTorch's own index (not on a Mac), with none of this computer's
    settings for pip or Python. Three packages are left out of the locks because the voice
    never runs them: Gradio; SoX's wrapper, imported by Qwen3-TTS for a tokenizer its 12 Hz
    models do not use (the engine answers that import with an empty module); and docopt.
    The last two exist only as source to be built.
  - **Its models** come from fixed revisions on Hugging Face, and each file is kept only if
    its size and its hash (SHA-256 for a large file, Git's hash for a small one) are the ones
    pinned in `voice/catalog.py`; the aligner from PyTorch's downloads, by SHA-256. A file
    one voice shares with another is copied, not downloaded again. A redirect is followed:
    what arrives is checked, not where it came from.
  - Room on the disk is checked first. Then the voice says "Ready." before it is called set
    up. Programs installed by another version of Adle (another lock) or for another Python
    are set up again.
- **The engine is a program of its own** (`voice/engine.py`), run with `-I` in the voice's
  environment and spoken to in JSON lines over its standard input and output; the core
  imports none of what it imports. Its libraries are told they are offline before they
  load. What it prints is thrown away: the text it speaks is the learner's. One model is on
  the card at a time.
- **Removing a voice** takes its models, its programs and the aligner where no other voice
  here needs them, and what it recorded.
- **A lesson says how its narrator sounds** (`voice` in the lesson format, one plain sentence
  of at most 240 characters, written by the model with the lesson). It is only ever the
  description a voice is designed from. A lesson without one, the sample course's or one
  written before, is read in Adle's own design.
- **Downloads go the way this computer's other downloads go**, through its proxy if it has
  one, and carry nothing of the learner's.
- For development, `ADLE_VOICE_KOKORO_PYTHON`, `ADLE_VOICE_QWEN_PYTHON`, `ADLE_VOICE_MODELS`,
  `ADLE_VOICE_ALIGNER` and `ADLE_VOICE_ENGINE` point at a voice set up elsewhere, which is
  used as it is and never set up or removed from Adle. The tests use a stand-in engine.

## Advisories in the voice's programs

`pip-audit` over the five locks finds advisories that were each read, and none reaches what
the voice does. CI sets exactly these aside and fails on any other:

| Advisory | In | Why it does not reach Adle |
|---|---|---|
| PYSEC-2025-194 | torch 2.11.0 | Memory corruption in `torch.jit.script` on crafted input; the voice compiles no script. A fixed torch exists only for CUDA 13, which needs a newer driver |
| PYSEC-2026-3447, GHSA-xmj3-9gf7-h52w | setuptools 81.0.0 | Building a source package, and a legacy way of installing a wheel on Windows; pip installs the voice's wheels itself. torch 2.11 requires setuptools below 82 |
| PYSEC-2026-3804 | accelerate 1.12.0 | A crafted checkpoint index; the voice's files are pinned by hash |
| PYSEC-2025-217, PYSEC-2026-2288, -2289, -2290, -3929, -4174 | transformers 4.57.3 | Checkpoint conversion, training, a crafted `config.json` or tokenizer from a repository Adle did not pin, saving a tokenizer, code fetched from the Hub: the voice loads only pinned, checked files, offline. Qwen3-TTS requires exactly this version |

## Consequences

- Adle can read in a voice that sounds like a person, with every word marked, on the
  learner's own computer and nowhere else.
- What is downloaded is large (0.6 to 12 GB) and is the learner's choice. On this machine
  Natural took 378 s to set up (programs 4 minutes, models 2) and comes to 1.4 GB on disk;
  Rich's programs took 8 minutes to download and install (2.9 GB downloaded).
- The voice's programs are not part of what Adle ships, and `THIRD_PARTY.md` does not list
  them. The models are under Apache-2.0 (Kokoro, Qwen3-TTS) and MIT (the aligner); the
  programs under permissive licences, eSpeak NG (Kokoro's fallback for words it does not
  know) under the GNU GPL 3, and NVIDIA's CUDA libraries under NVIDIA's own terms. The
  learner downloads them from their publishers.
- The engine is not shut off from the network by the system: it is told it is offline, and
  everything it reads is here. A learner who has no voice set up runs none of it.
- Not done: a sample of a natural voice in Settings before it is used; a graphics card
  other than NVIDIA's (torch is installed for CUDA only); the voices tried by hand on Linux
  and on a Mac.
