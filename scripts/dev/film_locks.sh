#!/usr/bin/env bash
# Lock the film maker's programs (ADR-065) for every system it is offered on: exact versions,
# every file's hash. The core installs from these with --require-hashes.
#
#   bash scripts/dev/film_locks.sh
#
# Needs uv. Writes services/core/adle_core/film/data/manimgx-<system>.txt for the version of
# ManimGX in film/catalog.py (ENGINE_VERSION). Run it when that version changes; then write
# the engine's names again with its own Python (scripts/dev/film_names.py), set what each
# lock comes to downloaded in film/catalog.py (program_bytes), and make a film by hand.
set -euo pipefail
cd "$(dirname "$0")/../.."
out=services/core/adle_core/film/data
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

version=$(sed -n 's/^ENGINE_VERSION = "\(.*\)"$/\1/p' services/core/adle_core/film/catalog.py)
[ -n "$version" ] || { echo "No ENGINE_VERSION in film/catalog.py" >&2; exit 1; }
echo "manimgx==$version" > "$work/manimgx.in"

lock() { # platform, name
  # Into a file first: written to standard output, uv on Windows was seen to wait for ever.
  uv pip compile "$work/manimgx.in" --python-platform "$1" --python-version 3.13 \
    --generate-hashes --no-header --no-annotate --quiet -o "$work/$2.lock"
  {
    echo "# Locked by uv pip compile on $(date +%Y-%m-%d) for ADR-065; regenerate with scripts/dev/film_locks.sh."
    cat "$work/$2.lock"
  } > "$out/$2.txt"
  echo "$2: $(grep -c '^[a-zA-Z]' "$out/$2.txt") packages"
}

lock x86_64-pc-windows-msvc manimgx-windows
lock x86_64-manylinux_2_28 manimgx-linux
lock aarch64-manylinux_2_28 manimgx-linux-arm
lock aarch64-apple-darwin manimgx-macos
lock x86_64-apple-darwin manimgx-macos-intel
