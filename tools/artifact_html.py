"""
Artifact（claude.ai のページ）で公開する HTML を作る．<名前>.html に，同じフォルダの <名前>.pdf と <名前>.pptx を埋め込む．

Artifact の中では，ふつうのリンク（<a download>）ではファイルを保存できず，パワポのファイルは置くこともできない．
そこで中身をページに埋め込み，書き出しボタンは downloads の機能で渡す（runtime.js）．公開するときは
capabilities に {"downloads": true} を付ける．

使い方: python3 artifact_html.py <資料のフォルダ> <名前>   → <資料のフォルダ>/.build/<名前>.artifact.html
"""
import base64, sys
from pathlib import Path

deck, name = Path(sys.argv[1]).resolve(), sys.argv[2]
html = (deck / f'{name}.html').read_text(encoding='utf-8')
blocks = ''
for kind in ('pdf', 'pptx'):
    f = deck / f'{name}.{kind}'
    if f.is_file():
        blocks += f'<script type="application/octet-stream" id="msf-file-{kind}">{base64.b64encode(f.read_bytes()).decode()}</script>\n'
out = deck / '.build' / f'{name}.artifact.html'
out.parent.mkdir(exist_ok=True)
i = html.rfind('</body>')
out.write_text(html[:i] + blocks + html[i:] if i >= 0 else html + blocks, encoding='utf-8')
print(f'{out.relative_to(deck)}: Artifact で公開する HTML（{out.stat().st_size / 1e6:.1f} MB．capabilities に downloads を付ける）')
