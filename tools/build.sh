#!/bin/sh
# 資料のフォルダで，*.src.html から 3 つを作る:
#   <名前>.html … 体裁・飾り・図・式を埋め込んだ 1 ファイル（プレビューと公開に使う）
#   <名前>.pdf  … 1 枚 1 ページ（大きさはマスターと同じ）．全部の枚を並べた画像を .build/<名前>.sheet.png に置く
#   <名前>.pptx … 全部編集できるパワポ（プロファイルのマスターの上）．作れなかったときだけ，中身が画像のパワポにする
#   .build/<名前>.artifact.html … Artifact で公開する版（PDF・パワポを埋め込み，書き出しボタンで渡せる）
# 使い方: build.sh <資料のフォルダ> [--html-only]
set -e
TOOLS="$(cd "$(dirname "$0")" && pwd)"
DECK="$(cd "$1" && pwd)"; ONLY="$2"
command -v uv >/dev/null 2>&1 || { echo "uv が無いので作れない．入れ方: https://docs.astral.sh/uv/（python3 $TOOLS/doctor.py で依存を確かめられる）" >&2; exit 1; }
uri() { python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).as_uri())' "$1"; }
found=0
for src in "$DECK"/*.src.html; do
  [ -f "$src" ] || continue; found=1
  name="$(basename "$src" .src.html)"
  uv run --quiet --with python-pptx python "$TOOLS/build_html.py" "$DECK" "$name.src.html"
  [ "$ONLY" = "--html-only" ] && continue
  CHROME="$(python3 "$TOOLS/doctor.py" --chrome "$DECK")"
  if [ -z "$CHROME" ]; then echo "Chrome が見つからないので，PDF とパワポは作らない（HTML だけ）．設定の \"chrome\" に場所を書ける" >&2; continue; fi
  "$CHROME" --headless=new --no-pdf-header-footer --virtual-time-budget=15000 --print-to-pdf="$DECK/$name.pdf" "$(uri "$DECK/$name.html")?export=pdf" 2>/dev/null
  uv run --quiet --with pymupdf --with pillow python "$TOOLS/contact_sheet.py" "$DECK/$name.pdf" "$DECK/.build/$name.sheet.png" 4 480
  if ! uv run --quiet --with python-pptx --with playwright python "$TOOLS/export_pptx_editable.py" "$DECK" "$DECK/$name.html" "$DECK/$name.pptx"; then
    echo "編集できるパワポを作れなかったので，中身が画像のパワポにする: $name" >&2
    MASTER="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["config"]["master"])' "$DECK/.build/resolved.json")"
    LAYOUT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["theme"]["layout"])' "$DECK/.build/resolved.json")"
    uv run --quiet --with python-pptx --with pymupdf python "$TOOLS/export_pptx.py" "$DECK/$name.pdf" "$DECK/$name.pptx" "$MASTER" "$LAYOUT"
  fi
  python3 "$TOOLS/artifact_html.py" "$DECK" "$name"            # Artifact で公開する版（PDF・パワポを埋め込む）
done
[ "$found" = 1 ] || { echo "$DECK に *.src.html が無い" >&2; exit 1; }
