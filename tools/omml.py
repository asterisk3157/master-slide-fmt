"""
LaTeX の式を，パワポの数式（Office の数式．OMML の <m:oMath>）にする．pandoc を使う．

  available()      … pandoc があるか
  to_omml(tex)     … <m:oMath> の要素（lxml）．pandoc が読めない書き方なら例外（呼ぶ側で画像にする）
  for_pptx(om, pt, color, latin, ea) … パワポの書き方に直す（文字ごとに a:rPr で大きさ・色・書体を付ける）

pandoc は Word の文書（docx）を作るので，その中の数式だけを取り出す．
"""
import copy, re, shutil, subprocess, tempfile, zipfile
from pathlib import Path
from lxml import etree

M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
MATH_FONT = 'Cambria Math'
_cache = {}


def available():
    return shutil.which('pandoc') is not None

def prep(tex):
    """pandoc が読めない古い書き方を直す（{\\rm H} → \\mathrm{H} など）"""
    for old, new in (('rm', 'mathrm'), ('bf', 'mathbf'), ('it', 'mathit'), ('sf', 'mathsf'), ('tt', 'mathtt')):
        tex = re.sub(r'\{\\%s\s+([^{}]*)\}' % old, r'\\%s{\1}' % new, tex)
        tex = re.sub(r'\\%s\s*\{([^{}]*)\}' % old, r'\\%s{\1}' % new, tex)
    tex = re.sub(r'\\arg\s*\\(min|max)(?![A-Za-z])',r'\\operatorname*{arg\\ \1}', tex)   # そのままだと arg と min の間が詰まる
    return tex.replace(r'\displaystyle', '').strip()

def to_omml(tex):
    key = prep(tex)
    if key not in _cache:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'eq.md').write_text('$$' + key + '$$\n', encoding='utf-8')
            r = subprocess.run(['pandoc', 'eq.md', '-o', 'eq.docx'], cwd=d, capture_output=True, text=True)
            if r.returncode or 'Could not convert TeX math' in r.stderr:
                why = next((l.strip() for l in r.stderr.splitlines() if 'unexpected' in l), 'pandoc が読めない書き方')
                raise RuntimeError(f'pandoc: {why}')
            doc = etree.fromstring(zipfile.ZipFile(Path(d) / 'eq.docx').read('word/document.xml'))
        om = doc.find('.//{%s}oMath' % M)
        if om is None: raise RuntimeError('pandoc が数式を作らなかった')
        for e in [e for e in om.iter() if isinstance(e.tag, str) and e.tag.startswith('{%s}' % W)]:
            e.getparent().remove(e)                  # Word の書式（w:rPr）は外す
        _cache[key] = om
    return copy.deepcopy(_cache[key])

def for_pptx(om, pt, color='000000', latin=MATH_FONT, ea=None):
    """パワポの数式の文字は <m:r> の中に a:rPr を持つ（m:rPr の後，m:t の前）．立体（m:sty p）以外は斜体"""
    for r in om.iter('{%s}r' % M):
        sty = r.find('{%s}rPr/{%s}sty' % (M, M))
        rp = etree.Element('{%s}rPr' % A, lang='en-US', altLang='ja-JP', sz=str(int(round(pt * 100))),
                           i='0' if sty is not None and sty.get('{%s}val' % M) in ('p', 'b') else '1')
        f = etree.SubElement(rp, '{%s}solidFill' % A); etree.SubElement(f, '{%s}srgbClr' % A).set('val', color)
        etree.SubElement(rp, '{%s}latin' % A).set('typeface', latin)
        etree.SubElement(rp, '{%s}ea' % A).set('typeface', ea or latin)
        etree.SubElement(rp, '{%s}cs' % A).set('typeface', latin)
        t = r.find('{%s}t' % M)
        (t.addprevious(rp) if t is not None else r.append(rp))
    return om


if __name__ == '__main__':
    import sys
    for tex in sys.argv[1:] or [r'\hat{p}(L) = \frac{1}{N} \sum_{n=1}^{N} e_n(L)']:
        try: print('ok ', tex, len(etree.tostring(to_omml(tex))))
        except Exception as e: print('NG ', tex, e)
