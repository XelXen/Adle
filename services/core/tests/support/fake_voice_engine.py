"""A stand-in for the voice engine (adle_core/voice/engine.py), for tests: the same protocol,
no models. It "says" each line as silence, a third of a second a word, and puts each word
where its third of a second is. A line containing FAIL is refused, as the engine refuses.

``ADLE_FAKE_VOICE_DELAY`` makes it take that many seconds over each line it says, as a voice
slower than the lesson would (ADR-051); it loads nothing, at once."""

from __future__ import annotations

import json
import os
import sys
import time
import wave

from adle_core.voice.engine import words_of

RATE = 16_000
PER_WORD = 0.3


def speak(text: str, out: str) -> dict[str, object]:
    if "FAIL" in text:
        raise ValueError("refused")
    time.sleep(float(os.environ.get("ADLE_FAKE_VOICE_DELAY") or 0))
    words = words_of(text)
    seconds = max(1, len(words)) * PER_WORD
    with wave.open(out, "wb") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(RATE)
        clip.writeframes(b"\0\0" * int(RATE * seconds))
    return {
        "seconds": round(seconds, 3),
        "words": [
            {"index": index, "length": length, "start": n * PER_WORD, "end": (n + 1) * PER_WORD}
            for n, (index, length, _) in enumerate(words)
        ],
    }


def main() -> int:
    for line in sys.stdin:
        request = json.loads(line)
        try:
            if request.get("op") == "hello":
                answer: dict[str, object] = {"cuda": False, "threads": 1}
            elif request.get("op") == "load":
                answer = {}
            elif request.get("op") == "speak":
                answer = speak(request["text"], request["out"])
            else:
                raise ValueError("unknown request")
            print(json.dumps({"id": request.get("id"), "ok": True, **answer}), flush=True)
        except Exception as error:
            message = {"id": request.get("id"), "ok": False, "error": type(error).__name__}
            print(json.dumps(message), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
