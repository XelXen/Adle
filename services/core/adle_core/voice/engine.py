"""The voice engine: speaks a lesson's narration with Kokoro or Qwen3-TTS, and knows when it
says each word (ADR-042).

A program of its own, run by the core inside the voice environment (``voice/env``) with
``-I``, never imported by the core: it needs torch and the models, which the core does not
have. It reads one request a line on standard input and answers each with one line on
standard output, as JSON. Everything else it or its libraries print goes to standard error.

Requests::

    {"id": 1, "op": "hello"}
    {"id": 1, "op": "load", "voice": {"tier": "expressive"}}
    {"id": 2, "op": "speak", "text": "...", "out": "<file>.ogg",
     "voice": {"tier": "kokoro", "speaker": "af_heart"}}
    {"id": 2, "op": "speak", "text": "...", "out": "<file>.ogg",
     "voice": {"tier": "standard", "speaker": "Ryan"}}
    {"id": 3, "op": "speak", "text": "...", "out": "<file>.ogg",
     "voice": {"tier": "expressive", "design": "A calm, warm voice ...", "reference": "<file>.wav"}}

Answers: ``{"id": n, "ok": true, ...}`` or ``{"id": n, "ok": false, "error": "..."}``. A spoken
answer says how long the clip is and where each word of the text is in it, by its place in
the text (``index``, ``length``) and its time (``start``, ``end``): from Kokoro's own
durations, or as the aligner found it for Qwen3-TTS, which does not say. A word that cannot be
placed is left out: nothing is guessed.

Nothing here reaches the network. The core points it at models it downloaded and checked,
and the libraries are told they are offline before they are imported.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

# The libraries are told they are offline before any of them is imported.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

LANGUAGE = "English"
#: The aligner: torchaudio's English wav2vec 2.0 model (fairseq, MIT), placed by the core.
ALIGNER_FILE = "wav2vec2_fairseq_base_ls960_asr_ls960.pth"
#: A word as it is found in the text: a number, or letters with apostrophes inside.
_WORD = re.compile(r"\d+(?:\.\d+)?|[A-Za-z]+(?:['’][A-Za-z]+)*")
_ONES = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = ["_", "_", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def spoken_number(digits: str) -> str:
    """How a number written with digits is said, for finding it in the audio: "2.5" is
    "two point five". Up to 9999; anything longer is said digit by digit."""
    whole, _, fraction = digits.partition(".")
    value = int(whole) if whole else 0
    if len(whole) > 4:
        words = [_ONES[int(digit)] for digit in whole]
    else:
        words = []
        if value >= 1000:
            words += [_ONES[value // 1000], "thousand"]
            value %= 1000
        if value >= 100:
            words += [_ONES[value // 100], "hundred"]
            value %= 100
        if value >= 20:
            words.append(_TENS[value // 10])
            value %= 10
            if value:
                words.append(_ONES[value])
        elif value or not words:
            words.append(_ONES[value])
    if fraction:
        words += ["point", *(_ONES[int(digit)] for digit in fraction)]
    return " ".join(words)


def words_of(text: str) -> list[tuple[int, int, str]]:
    """Each word of the text: where it is, how long it is, and how it is said."""
    found = []
    for match in _WORD.finditer(text):
        written = match.group(0)
        said = spoken_number(written) if written[0].isdigit() else written.replace("’", "'")
        found.append((match.start(), len(written), said))
    return found


def _stand_in_for_sox() -> None:
    """Qwen3-TTS imports SoX's Python wrapper for its older 25 Hz tokenizer, which the 12 Hz
    models spoken with here never use. The wrapper is published only as source to be built,
    and the voice's programs are installed only as built files whose hashes are checked
    (ADR-042), so it is left out, and an empty module answers the import that is never used."""
    import importlib.util
    import types

    if "sox" not in sys.modules and importlib.util.find_spec("sox") is None:
        sys.modules["sox"] = types.ModuleType("sox")


class Voice:
    """The models, loaded when first needed and kept while the engine runs."""

    def __init__(self, models: str, aligner: str) -> None:
        self.models = models
        self.aligner_dir = aligner
        self._loaded: dict[str, Any] = {}
        self._aligner: Any = None
        self._kokoro: Any = None
        self._pipelines: dict[str, Any] = {}

    def _model(self, name: str) -> Any:
        import torch

        _stand_in_for_sox()
        from faster_qwen3_tts import FasterQwen3TTS

        if name not in self._loaded:
            # One model on the card at a time: a voice is designed once, then spoken with.
            for other in list(self._loaded):
                del self._loaded[other]
            torch.cuda.empty_cache()
            model = FasterQwen3TTS.from_pretrained(
                os.path.join(self.models, name),
                device="cuda",
                dtype=torch.bfloat16,
                local_files_only=True,
            )
            model.warmup()
            self._loaded[name] = model
        return self._loaded[name]

    def hello(self) -> dict[str, Any]:
        import torch

        if not torch.cuda.is_available():
            return {"cuda": False, "threads": torch.get_num_threads()}
        properties = torch.cuda.get_device_properties(0)
        return {
            "cuda": True,
            "device": torch.cuda.get_device_name(0),
            "memory_gb": round(properties.total_memory / 1024**3, 1),
        }

    def load(self, voice: dict[str, Any]) -> dict[str, Any]:
        """Load what a voice speaks with before there is anything to say (ADR-051): the model
        its first line is said with, and the aligner. Nothing is written."""
        tier = voice.get("tier")
        if tier == "kokoro":
            self.kokoro("Ready.", str(voice.get("speaker") or "af_heart"))
            return {}
        if tier == "standard":
            self._model("Qwen3-TTS-12Hz-0.6B-CustomVoice")
        elif tier == "expressive":
            # A lesson's voice is designed first, from its description, saying its first line.
            self._model("Qwen3-TTS-12Hz-1.7B-VoiceDesign")
        else:
            raise ValueError(f"unknown voice tier {tier!r}")
        self._load_aligner()
        return {}

    def speak(self, text: str, voice: dict[str, Any], out: str) -> dict[str, Any]:
        import numpy as np
        import soundfile

        tier = voice.get("tier")
        if tier == "kokoro":
            wav, rate, words = self.kokoro(text, str(voice.get("speaker") or "af_heart"))
            soundfile.write(out, wav, rate, format="OGG", subtype="VORBIS")
            return {"seconds": round(len(wav) / rate, 3), "words": words}
        if tier == "standard":
            model = self._model("Qwen3-TTS-12Hz-0.6B-CustomVoice")
            wavs, rate = model.generate_custom_voice(
                text=text, speaker=str(voice.get("speaker") or "Ryan"), language=LANGUAGE
            )
        elif tier == "expressive":
            reference = str(voice["reference"])
            design = str(voice.get("design") or "")
            if not os.path.exists(reference):
                # The voice is designed once, from its description, saying this first line;
                # every later line is spoken in that voice, so it does not change between
                # them.
                designer = self._model("Qwen3-TTS-12Hz-1.7B-VoiceDesign")
                wavs, rate = designer.generate_voice_design(
                    text=text, instruct=design, language=LANGUAGE
                )
                soundfile.write(reference, np.asarray(wavs[0], dtype=np.float32), rate)
                with open(reference + ".txt", "w", encoding="utf-8") as said:
                    said.write(text)
            else:
                with open(reference + ".txt", encoding="utf-8") as said:
                    reference_text = said.read()
                speaker = self._model("Qwen3-TTS-12Hz-1.7B-Base")
                wavs, rate = speaker.generate_voice_clone(
                    text=text,
                    language=LANGUAGE,
                    ref_audio=reference,
                    ref_text=reference_text,
                )
        else:
            raise ValueError(f"unknown voice tier {tier!r}")
        wav = np.asarray(wavs[0], dtype=np.float32)
        words = self.align(wav, rate, text)
        soundfile.write(out, wav, rate, format="OGG", subtype="VORBIS")
        return {"seconds": round(len(wav) / rate, 3), "words": words}

    def kokoro(self, text: str, speaker: str) -> tuple[Any, int, list[dict[str, Any]]]:
        """Kokoro on the processor. It knows how long it gives each word, and so when it says
        each one: those are the times, with nothing aligned or guessed."""
        import numpy as np
        from kokoro import KModel, KPipeline

        if not re.fullmatch(r"[ab][fm]_[a-z]+", speaker):
            raise ValueError("unknown voice")
        folder = os.path.join(self.models, "Kokoro-82M")
        if self._kokoro is None:
            self._kokoro = KModel(
                repo_id="hexgrad/Kokoro-82M",
                config=os.path.join(folder, "config.json"),
                model=os.path.join(folder, "kokoro-v1_0.pth"),
            ).eval()
        # "a" reads American English, "b" British: the first letter of the voice's name.
        language = speaker[0]
        if language not in self._pipelines:
            self._pipelines[language] = KPipeline(
                lang_code=language, repo_id="hexgrad/Kokoro-82M", model=self._kokoro
            )
        pipeline = self._pipelines[language]
        pack = pipeline.load_voice(os.path.join(folder, "voices", f"{speaker}.pt"))
        rate = 24000
        pieces: list[Any] = []
        words: list[dict[str, Any]] = []
        offset = 0.0
        cursor = 0
        for result in pipeline(text, voice=pack, speed=1.0):
            audio = result.audio
            audio = audio.numpy() if hasattr(audio, "numpy") else np.asarray(audio)
            for token in result.tokens or []:
                if token.start_ts is None or token.end_ts is None:
                    continue
                if not any(character.isalnum() for character in token.text):
                    continue
                # Found where it is in the text as written. A token the reader rewrote is
                # not in it, and is left out.
                at = text.find(token.text, cursor)
                if at < 0:
                    continue
                cursor = at + len(token.text)
                words.append(
                    {
                        "index": at,
                        "length": len(token.text),
                        "start": round(offset + float(token.start_ts), 3),
                        "end": round(offset + float(token.end_ts), 3),
                    }
                )
            pieces.append(audio)
            offset += len(audio) / rate
        if not pieces:
            raise ValueError("nothing was said")
        return np.concatenate(pieces).astype(np.float32), rate, words

    def _load_aligner(self) -> None:
        import torch
        import torchaudio

        if self._aligner is None:
            placed = os.path.join(self.aligner_dir, "hub", "checkpoints", ALIGNER_FILE)
            if not os.path.exists(placed):
                raise FileNotFoundError("The aligner is not where it was installed.")
            torch.hub.set_dir(os.path.join(self.aligner_dir, "hub"))
            bundle = torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H
            self._aligner = bundle.get_model().to("cuda")

    def align(self, wav: Any, rate: int, text: str) -> list[dict[str, Any]]:
        """Where each word of ``text`` is in ``wav``: forced alignment, letter by letter."""
        import torch
        import torchaudio

        bundle = torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H
        self._load_aligner()
        labels = bundle.get_labels()
        index = {label: position for position, label in enumerate(labels)}

        tokens: list[int] = []
        owners: list[int] = []
        words = words_of(text)
        for number, (_, _, said) in enumerate(words):
            for spoken in said.split():
                if tokens:
                    tokens.append(index["|"])
                    owners.append(-1)
                for letter in spoken.upper():
                    if letter in index:
                        tokens.append(index[letter])
                        owners.append(number)
        if not tokens:
            return []
        waveform = torch.from_numpy(wav).unsqueeze(0)
        waveform = torchaudio.functional.resample(waveform, rate, bundle.sample_rate)
        with torch.inference_mode():
            emission, _ = self._aligner(waveform.to("cuda"))
            emission = torch.log_softmax(emission, dim=-1)
            if emission.size(1) < len(tokens):
                return []
            aligned, scores = torchaudio.functional.forced_align(
                emission, torch.tensor([tokens], dtype=torch.int32, device="cuda"), blank=0
            )
        spans = torchaudio.functional.merge_tokens(aligned[0], scores[0].exp())
        frame = waveform.size(1) / emission.size(1) / bundle.sample_rate
        times: dict[int, list[float]] = {}
        for span, owner in zip(spans, owners, strict=True):
            if owner < 0:
                continue
            found = times.setdefault(owner, [span.start * frame, span.end * frame])
            found[1] = span.end * frame
        return [
            {
                "index": words[number][0],
                "length": words[number][1],
                "start": round(start, 3),
                "end": round(end, 3),
            }
            for number, (start, end) in sorted(times.items())
        ]


def main() -> int:
    models, aligner = sys.argv[1], sys.argv[2]
    # The answers have standard output to themselves: what the libraries print goes to
    # standard error, where the core keeps nothing.
    answers = os.fdopen(os.dup(1), "w", encoding="utf-8", buffering=1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    voice = Voice(models, aligner)
    for line in sys.stdin:
        if not line.strip():
            continue
        request: dict[str, Any] = {}
        try:
            request = json.loads(line)
            if request.get("op") == "hello":
                answer = voice.hello()
            elif request.get("op") == "load":
                answer = voice.load(dict(request["voice"]))
            elif request.get("op") == "speak":
                answer = voice.speak(
                    str(request["text"]), dict(request["voice"]), str(request["out"])
                )
            else:
                raise ValueError("unknown request")
            answers.write(json.dumps({"id": request.get("id"), "ok": True, **answer}) + "\n")
        except Exception as error:
            answers.write(
                json.dumps(
                    {
                        "id": request.get("id"),
                        "ok": False,
                        "error": f"{type(error).__name__}: {str(error)[:300]}",
                    }
                )
                + "\n"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
