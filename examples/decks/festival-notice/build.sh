#!/bin/sh
# *.src.html から .html（体裁・図・式を埋め込み）・.pdf・.pptx を作る．--html-only で HTML だけ
# スキルの道具を探す順: 環境変数 MASTER_SLIDE_FMT → 上のフォルダの .claude/skills/master-slide-fmt → ~/.claude/skills/master-slide-fmt
HERE="$(cd "$(dirname "$0")" && pwd)"
[ -n "$MASTER_SLIDE_FMT" ] && exec "$MASTER_SLIDE_FMT/tools/build.sh" "$HERE" "$@"
d="$HERE"
while [ "$d" != "/" ]; do
  [ -x "$d/.claude/skills/master-slide-fmt/tools/build.sh" ] && exec "$d/.claude/skills/master-slide-fmt/tools/build.sh" "$HERE" "$@"
  d="$(dirname "$d")"
done
[ -x "$HOME/.claude/skills/master-slide-fmt/tools/build.sh" ] && exec "$HOME/.claude/skills/master-slide-fmt/tools/build.sh" "$HERE" "$@"
echo "master-slide-fmt が見つからない．環境変数 MASTER_SLIDE_FMT にスキルのフォルダを入れる" >&2; exit 1
