"""
古い形の資料（体裁の CSS・脚注・スクリプトを src に直接書いたもの）を，このスキルの形に直す．

  - <style> の中の，共通の体裁（base.css やマスターから作る部分）の規則を外す．資料だけの規則（.row など）は残す
  - 各スライドの <div class="foot">…</div>（名前を直接書いた脚注）と，表紙の <div class="cover-line"> を外す
  - 書き出しボタン（<div id="export">）と，古い自動縮小のスクリプト（fitSlides を含む <script>）を外す

使い方: python3 migrate_deck.py <古い.src.html> <新しい.src.html>
"""
import re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = {'.slide', '.slide .inner', '.slide h2', 'footer', '.foot', '.foot .num', '.foot .date', '.red', '.blue', '#export', '#export a', '#export a:hover',
       '.slide.cover .cover-line', '.slide.cover .cover-title', '.slide.cover .cover-sub', 'body.export.nofoot .foot', '@page'}

def selectors_of_base():
    css = (HERE / 'base.css').read_text(encoding='utf-8')
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    return {norm(m) for m in re.findall(r'([^{}]+)\{', css)}

def norm(sel): return re.sub(r'\s+', ' ', sel.strip())

def main(src, out):
    s = Path(src).read_text(encoding='utf-8')
    shared = selectors_of_base() | OLD
    def fix_style(m):
        kept, dropped = [], 0
        for line in m.group(1).splitlines():
            t = line.strip()
            if not t or (t.startswith('/*') and t.endswith('*/') and '{' not in t): dropped += bool(t); continue
            sel = norm(t.split('{', 1)[0]) if '{' in t else None
            if sel and (sel in shared or sel.split(' ')[0] in ('@page', 'body.export') or sel.startswith('body.export')): dropped += 1; continue
            kept.append(line)
        print(f'  <style>: 共通の規則 {dropped} 行を外し，{len(kept)} 行を残した')
        return '<style>\n  /* この資料だけの調整（体裁はマスターと設定から build が入れる） */\n' + '\n'.join(kept) + '\n</style>'
    s = re.sub(r'<style>\n?(.*?)</style>', fix_style, s, count=1, flags=re.S)
    n_foot = len(re.findall(r'\s*<div class="foot">.*?</div>', s))
    s = re.sub(r'\n?[ \t]*<div class="foot">.*?</div>', '', s)
    s = re.sub(r'\n?[ \t]*<div class="cover-line"></div>', '', s)
    s = re.sub(r'\n?<div id="export">.*?</div>', '', s)
    n_js = 0
    def drop_js(m):
        nonlocal n_js
        if 'fitSlides' in m.group(0): n_js += 1; return ''
        return m.group(0)
    s = re.sub(r'\n?<script>.*?</script>', drop_js, s, flags=re.S)
    Path(out).write_text(s, encoding='utf-8')
    print(f'  脚注 {n_foot} 個・古いスクリプト {n_js} 個を外した → {out}')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
