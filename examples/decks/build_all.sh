#!/bin/sh
# 見本の資料を全部作る（図を作り直してから，各フォルダで build）．使い方: examples/decks/build_all.sh [--html-only]
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
uv run --quiet --with matplotlib --with numpy python "$HERE/make_figs.py"
for d in "$HERE"/*/; do
  [ -f "$d/slides.config.json" ] || continue
  echo "== $(basename "$d")"
  "$HERE/../../tools/build.sh" "$d" "$@"
done
