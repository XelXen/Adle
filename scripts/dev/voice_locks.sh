#!/usr/bin/env bash
# Lock the programs each natural voice runs with (ADR-042), for every system it is offered on:
# exact versions, every file's hash. The core installs from these with --require-hashes.
#
#   bash scripts/dev/voice_locks.sh
#
# Needs uv. Writes services/core/adle_core/voice/data/<family>-<system>.txt. Run it when a
# version below changes, then try the voice by hand on each system (CONTRIBUTING.md).
set -euo pipefail
cd "$(dirname "$0")/../.."
out=services/core/adle_core/voice/data
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

spacy_model="en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
printf '%s\n' "torch==2.11.0+cpu" "kokoro==0.9.4" "soundfile==0.13.1" "$spacy_model" > "$work/kokoro-cpu.in"
printf '%s\n' "torch==2.11.0" "kokoro==0.9.4" "soundfile==0.13.1" "$spacy_model" > "$work/kokoro-mac.in"
printf '%s\n' "torch==2.11.0+cu128" "torchaudio==2.11.0+cu128" "faster-qwen3-tts==0.3.2" \
  "qwen-tts==0.1.1" "soundfile==0.13.1" > "$work/qwen.in"
# Left out, because the voice never runs them: Gradio, which Qwen3-TTS lists for its
# demonstration; SoX's wrapper, which it imports for a tokenizer the 12 Hz models do not use
# (the engine answers that import, ADR-042); and docopt, for num2words' command line. The last
# two are published only as source to be built, and the voice's programs are installed only as
# built files whose hashes are checked.
printf '%s\n' "gradio ; python_version < '3'" "sox ; python_version < '3'" \
  "docopt ; python_version < '3'" > "$work/leave-out.txt"

lock() { # input, platform, name, PyTorch index (or none)
  local extra=()
  [ "$4" != none ] && extra=(--extra-index-url "https://download.pytorch.org/whl/$4")
  # Into a file first: written to standard output, uv on Windows was seen to wait for ever.
  uv pip compile "$work/$1" --python-platform "$2" --python-version 3.12 --generate-hashes \
    --index-strategy unsafe-best-match "${extra[@]}" --override "$work/leave-out.txt" \
    --no-header --no-annotate --quiet -o "$work/$3.lock"
  {
    echo "# Locked by uv pip compile on $(date +%Y-%m-%d) for ADR-042; regenerate with scripts/dev/voice_locks.sh."
    cat "$work/$3.lock"
  } > "$out/$3.txt"
  echo "$3: $(grep -c '^[a-zA-Z]' "$out/$3.txt") packages"
}

lock kokoro-cpu.in x86_64-pc-windows-msvc kokoro-windows cpu
lock kokoro-cpu.in x86_64-manylinux_2_28 kokoro-linux cpu
lock kokoro-mac.in aarch64-apple-darwin kokoro-macos none
lock qwen.in x86_64-pc-windows-msvc qwen-windows cu128
lock qwen.in x86_64-manylinux_2_28 qwen-linux cu128
