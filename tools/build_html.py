"""
*.src.html → <名前>.html（体裁の CSS・飾り・図・式を埋め込んだ 1 ファイル）

  1. 設定を解決する（既定値 → プロファイル → slides.config.json）
  2. マスターを読む（.build/master.json．マスターが変わったときだけ読み直す）
  3. マスターと設定から CSS と飾りを作る（theme_css.py）
  4. $…$ の式: テキストで書けるものはテキストに，残りは LaTeX の絵に（LaTeX が無ければ MathJax で表示）
  5. figs/ の図を埋め込む

使い方: uv run --with python-pptx python build_html.py <資料のフォルダ> <名前>.src.html
"""
import base64, datetime, hashlib, html, json, mimetypes, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import config, eqrender, mathtext, read_master, theme_css

VERSION = hashlib.sha1((HERE / 'read_master.py').read_bytes()).hexdigest()[:10]
MATHJAX = '''<script>window.MathJax = { tex: { inlineMath: [['$', '$']] }, svg: { fontCache: 'none' } };</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg.js"></script>'''


def master_json(deck, master_path):
    """マスターを読んだ結果を .build/master.json に置く（マスターの中身と道具の版が同じなら読み直さない）"""
    b = Path(deck) / '.build'; b.mkdir(exist_ok=True)
    stamp = hashlib.sha1(Path(master_path).read_bytes()).hexdigest() + VERSION
    f = b / 'master.json'
    if f.is_file():
        d = json.loads(f.read_text(encoding='utf-8'))
        if d.get('_stamp') == stamp: return d
    d = read_master.strip(read_master.read(master_path)); d['_stamp'] = stamp
    f.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
    return d


SECTION = re.compile(r'(<section\b[^>]*\bclass="([^"]*)"[^>]*>)(.*?)(</section>)', re.S)
FOOT = re.compile(r'\s*<div class="(?:foot|deco|cover-line)"[^>]*>.*?</div>', re.S)

def today_text(fmt):
    d = datetime.date.today()
    return {'ymd': f'{d.year}/{d.month}/{d.day}', 'iso': d.isoformat()}.get(fmt, f'{d:%B} {d.day}, {d.year}')

def structure(s, th, name):
    """各スライドを「飾り → 見出し → 本文の領域（.inner）→ 出典 → 脚注」の形に組む．src に書いた脚注・飾りは置き換える"""
    ft = th['data']['footer']
    n = [0]
    def foot():
        n[0] += 1
        out = []
        if ft.get('date') != 'none': out.append('<span class="date">%s</span>' % today_text(ft.get('date_format')))
        if ft.get('text'): out.append('<span class="ftr">%s</span>' % html.escape(ft['text']))
        if ft.get('number', True): out.append('<span class="num">%d</span>' % n[0])
        return '<div class="foot">%s</div>' % ''.join(out)
    def ttl(m): return m.group(1) + '<span class="ttl">' + m.group(2) + '</span>' + m.group(3)
    def one(m):
        head, cls, body, tail = m.groups()
        if 'slide' not in cls.split(): return m.group(0)
        body = FOOT.sub('', body)
        if 'cover' in cls.split():
            body = re.sub(r'(<div class="cover-(?:title|sub)"[^>]*>)(.*?)(</div>)', ttl, body, flags=re.S)
            return '%s\n<div class="deco">%s</div>%s\n%s\n%s' % (head, th['deco']['cover'], body, foot(), tail)
        h2 = re.search(r'<h2\b[^>]*>.*?</h2>', body, re.S)
        h2s = re.sub(r'(<h2\b[^>]*>)(.*?)(</h2>)', ttl, h2.group(0), flags=re.S) if h2 else ''
        if h2: body = body[:h2.start()] + body[h2.end():]
        refs = re.findall(r'<p class="refs[^"]*"[^>]*>.*?</p>', body, re.S)
        for r in refs: body = body.replace(r, '')
        return '%s\n<div class="deco">%s</div>\n%s\n<div class="inner">%s</div>\n%s\n%s\n%s' % (
            head, th['deco']['content'], h2s, body, '\n'.join(refs), foot(), tail)
    s = SECTION.sub(one, s)
    if 'id="export"' not in s:                            # 書き出しボタン（同じフォルダの <名前>.pdf / .pptx．build が作る）
        btn = '<div id="export"><a href="%s.pdf" data-kind="pdf" download>PDF でエクスポート</a><a href="%s.pptx" data-kind="pptx" download>パワポでエクスポート</a></div>\n' % (name, name)
        s = s.replace('<main>', btn + '<main>', 1)
    return s


def build(deck, src):
    deck = Path(deck).resolve(); src = deck / src
    cfg = config.resolve(deck)
    master = master_json(deck, cfg['master'])
    th = theme_css.theme(master, cfg)
    name = src.name[:-len('.src.html')]
    s = src.read_text(encoding='utf-8')

    # 式
    eqrender.configure(cfg['math'].get('font', 'sans'), cfg['math'].get('preamble', ''), th['resolved']['colors']['text'])
    use_latex = eqrender.available()
    s, n_text, kept = mathtext.convert_html(s, eqrender.img_tag if use_latex else None)
    mathjax = bool(kept) and not use_latex

    # 図（figs/ などの相対パスの画像）
    def embed(m):
        p = deck / m.group(2)
        if not p.is_file(): print(f'  注意: 図が無い: {m.group(2)}', file=sys.stderr); return m.group(0)
        mime = mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
        return '%s="data:%s;base64,%s"' % (m.group(1), mime, base64.b64encode(p.read_bytes()).decode())
    s = re.sub(r'(src)="(?!data:|https?:|#)([^"]+\.(?:png|jpe?g|gif|svg|webp))"', embed, s)

    # 飾り・見出し・本文の領域・脚注・書き出しボタンを，build の時点で HTML に書き込む（スクリプトが動かない表示でも崩れない）
    s = structure(s, th, name)

    # 体裁と，日付・図の自動縮小のスクリプトを入れる
    css = (HERE / 'base.css').read_text(encoding='utf-8') + '\n' + th['css']
    head = '<style id="msf-theme">\n%s\n</style>\n' % css + (MATHJAX + '\n' if mathjax else '')
    i = s.find('<style'); j = s.find('</head>')
    at = i if 0 <= i < j else j
    if at < 0: raise SystemExit(f'{src.name} に </head> が無い')
    s = s[:at] + head + s[at:]
    tail = '<script id="msf-data" type="application/json">%s</script>\n<script>\n%s\n</script>\n' % (
        json.dumps(th['data'], ensure_ascii=False), (HERE / 'runtime.js').read_text(encoding='utf-8'))
    k = s.rfind('</body>')
    s = (s[:k] + tail + s[k:]) if k >= 0 else s + tail
    (deck / f'{name}.html').write_text(s, encoding='utf-8')
    (deck / '.build' / 'resolved.json').write_text(json.dumps({'config': cfg, 'theme': th['resolved']}, ensure_ascii=False, indent=1), encoding='utf-8')
    (deck / '.build' / 'theme.css').write_text(th['css'], encoding='utf-8')

    p = cfg['_profile']
    print(f'{name}.html: プロファイル {p["name"]}（{p["reason"]}）/ マスター {Path(cfg["master"]).name}（{master["size"]["aspect"]}，'
          f'本文のレイアウト「{th["resolved"]["layout"]}」，表紙「{th["resolved"]["cover_layout"]}」）')
    print(f'  式 → テキスト {n_text} / 絵に残す {len(kept)}' + ('（LaTeX が無いので MathJax で表示．パワポでは画像になる）' if mathjax else ''))
    for w in th['warnings']: print('  注意:', w)
    return name


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2])
