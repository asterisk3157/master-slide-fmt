"""
文字で組めない式（分数，Σ，ハットなど）を LaTeX で描く．
HTML には SVG の画像として埋め込む．パワポの式の画像（PowerPoint の数式の代わりの表示）は，この絵をブラウザで撮ったもの（HTML とパワポで同じ見え方になる）．

  書体は設定の math.font: "sans"（Helvetica．Arial に近い．ギリシャ文字だけ TeX の書体） / "serif"（Computer Modern）
  math.preamble に書いた行（\\definecolor など）はプリアンブルに足す
  LaTeX（latex・dvisvgm．日本語を含む式は xelatex・pdftocairo）が無いときは available() が False を返す
"""
import base64, html, re, shutil, subprocess, tempfile
from pathlib import Path

_BASE = r"""\documentclass[10pt]{article}
\usepackage{amsmath,amssymb,bm,xcolor}
%(font)s
%(preamble)s
\pagestyle{empty}
\newsavebox\eqbox
\begin{document}
\sbox\eqbox{%(color)s$\displaystyle %%s$}\typeout{EQDEPTH=\the\dp\eqbox}\usebox\eqbox
\end{document}
"""
FONTS = {'sans': r'\usepackage{helvet}\renewcommand\familydefault{\sfdefault}' + '\n' + r'\usepackage[helvet]{sfmath}', 'serif': ''}
TEX = TEX_JA = None

def configure(font='sans', preamble='', color=None):
    """書体・プリアンブル・式の色を決める（式のプラグインの setup() にも同じ TEX を渡す．%s が 1 つだけ）．
    color は文字の色（'RRGGBB'）．黒以外（暗い背景の形など）のときだけ，式をその色で描く"""
    global TEX, TEX_JA
    c = (color or '000000').lstrip('#').upper()
    pre = (preamble or '') + ('\n\\definecolor{msftext}{HTML}{%s}' % c if c != '000000' else '')
    TEX = _BASE % {'font': FONTS.get(font, FONTS['sans']), 'preamble': pre.replace('%', '%%'),
                   'color': '\\color{msftext}' if c != '000000' else ''}
    TEX_JA = TEX.replace(r'\documentclass[10pt]{article}', r'\documentclass[10pt,border=0pt]{standalone}').replace(
        r'\pagestyle{empty}', r'\usepackage{xeCJK}\setCJKmainfont{Hiragino Kaku Gothic ProN}\setCJKsansfont{Hiragino Kaku Gothic ProN}')
    _cache.clear()

def available():
    return all(shutil.which(c) for c in ('latex', 'dvisvgm'))

_cache = {}
configure()

def render(tex):
    """(svg の文字列, 幅 pt, 高さ pt, 深さ pt)．10 pt の本文での大きさ"""
    if tex in _cache: return _cache[tex]
    with tempfile.TemporaryDirectory() as d:
        wd = Path(d); ja = not tex.isascii()
        (wd / 'eq.tex').write_text((TEX_JA if ja else TEX) % tex, encoding='utf-8')
        r = subprocess.run(['xelatex' if ja else 'latex', '-interaction=nonstopmode', '-halt-on-error', 'eq.tex'], cwd=wd, capture_output=True, text=True)
        if r.returncode: raise RuntimeError('latex: ' + r.stdout[-600:])
        dp = float(re.search(r'EQDEPTH=([\d.]+)pt', r.stdout).group(1))
        if ja: subprocess.run(['pdftocairo', '-svg', 'eq.pdf', 'eq.svg'], cwd=wd, capture_output=True, check=True)
        else: subprocess.run(['dvisvgm', '--no-fonts', '--exact-bbox', '--output=eq.svg', 'eq.dvi'], cwd=wd, capture_output=True, check=True)
        svg = (wd / 'eq.svg').read_text(encoding='utf-8')
    w = float(re.search(r"width=['\"]([\d.]+)pt", svg).group(1)); h = float(re.search(r"height=['\"]([\d.]+)pt", svg).group(1))
    _cache[tex] = (svg, w, h, min(dp, h)); return _cache[tex]

def img_tag(tex):
    """HTML に埋め込む <img>．大きさは周りの文字に比例（em）"""
    svg, w, h, dp = render(tex)
    src = 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode()
    return '<img class="eq" data-tex="%s" alt="" src="%s" style="width:%.4fem;height:%.4fem;vertical-align:%.4fem">' % (html.escape(tex, quote=True), src, w / 10, h / 10, -dp / 10)
