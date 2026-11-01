#!/bin/sh
# 確認用: 見本の資料（examples/decks/research）を，プロファイルごとに作る．全部の枚を並べた画像も作る
# 使い方: try_profiles.sh <出力のフォルダ> [プロファイル名 ...]   （名前を省くと，見つかる全部のプロファイル）
set -e
TOOLS="$(cd "$(dirname "$0")" && pwd)"; OUT="$1"; shift
mkdir -p "$OUT"
NAMES="$*"
[ -n "$NAMES" ] || NAMES="$(python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import config; print(" ".join(p["name"] for p in config.list_profiles()))' "$TOOLS")"
for p in $NAMES; do
  d="$OUT/$p"; mkdir -p "$d/figs"
  cp "$TOOLS/../examples/decks/research/research.src.html" "$d/sample.src.html"; cp "$TOOLS/../examples/decks/research/figs/"* "$d/figs/"
  printf '{ "profile": "%s" }\n' "$p" > "$d/slides.config.json"
  echo "== $p"
  "$TOOLS/build.sh" "$d"
  "$TOOLS/pptx_sheet.sh" "$d/sample.pptx" "$d/.build/sample.pptx-sheet.png" >/dev/null
  echo "   PDF の全部の枚: $d/.build/sample.sheet.png / パワポの全部の枚: $d/.build/sample.pptx-sheet.png"
done
