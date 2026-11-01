#!/bin/sh
# 確認用: パワポを PDF にして，全部の枚を並べた画像を作る
#   既定は LibreOffice（headless．日本語の字間が PowerPoint と少し違う）．--powerpoint で PowerPoint 本体に書き出させる（Mac のみ．より正確）
# 使い方: pptx_sheet.sh <名前>.pptx [出力.png] [--powerpoint]
set -e
TOOLS="$(cd "$(dirname "$0")" && pwd)"
PPTX="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"; OUT="${2:-${PPTX%.pptx}.pptx-sheet.png}"
TMP="$(mktemp -d)"
if [ "$3" = "--powerpoint" ] || [ "$2" = "--powerpoint" ]; then
  [ "$2" = "--powerpoint" ] && OUT="${PPTX%.pptx}.pptx-sheet.png"
  osascript "$TOOLS/ppt2pdf.scpt" "$PPTX" "$TMP/out.pdf"
else
  SOFFICE="$(command -v soffice || command -v libreoffice || echo /Applications/LibreOffice.app/Contents/MacOS/soffice)"
  [ -x "$SOFFICE" ] || { echo "LibreOffice が無い（--powerpoint で PowerPoint を使える）" >&2; exit 1; }
  "$SOFFICE" --headless --convert-to pdf --outdir "$TMP" "$PPTX" >/dev/null 2>&1
  mv "$TMP/$(basename "${PPTX%.pptx}").pdf" "$TMP/out.pdf"
fi
uv run --quiet --with pymupdf --with pillow python "$TOOLS/contact_sheet.py" "$TMP/out.pdf" "$OUT" 4 480
