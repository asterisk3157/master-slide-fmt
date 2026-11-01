"""
文中の式（$…$）のうち，テキストで書けるものを HTML のテキスト（Arial の斜体・上付き・下付き）に変える．

式を文字で書く資料（変数は斜体，添字は上付き・下付き，Σ や arg min も文字）に合わせて，
テキストで書ける式はすべてテキストにし，文字では組めない式だけを絵（→ パワポでは画像）に残す．

  テキストにする: 記号，ギリシャ文字，上付き・下付き（両方あってもよい），太字，立体，min_h・max_d（下付きで書く），括弧，ノルム
  絵に残す: 分数，上下に範囲の付く Σ・Π・∫，根号，行列，ハット・チルダ，\\underbrace，\\color

build.sh が *.src.html → *.html を作るときに convert_html() を通す．
"""
import html, re

GREEK = {
    'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ', 'epsilon': 'ε', 'varepsilon': 'ε', 'zeta': 'ζ', 'eta': 'η',
    'theta': 'θ', 'iota': 'ι', 'kappa': 'κ', 'lambda': 'λ', 'mu': 'μ', 'nu': 'ν', 'xi': 'ξ', 'pi': 'π', 'rho': 'ρ',
    'sigma': 'σ', 'tau': 'τ', 'upsilon': 'υ', 'phi': 'φ', 'varphi': 'φ', 'chi': 'χ', 'psi': 'ψ', 'omega': 'ω',
    'Gamma': 'Γ', 'Delta': 'Δ', 'Theta': 'Θ', 'Lambda': 'Λ', 'Xi': 'Ξ', 'Pi': 'Π', 'Sigma': 'Σ', 'Phi': 'Φ', 'Psi': 'Ψ', 'Omega': 'Ω',
}
SYM = {
    'cdot': '·', 'times': '×', 'pm': '±', 'in': '∈', 'leq': '≤', 'le': '≤', 'geq': '≥', 'ge': '≥', 'neq': '≠', 'ne': '≠',
    'approx': '≈', 'equiv': '≡', 'sim': '∼', 'infty': '∞', 'partial': '∂', 'nabla': '∇', 'leftarrow': '←', 'gets': '←',
    'rightarrow': '→', 'to': '→', 'ldots': '…', 'dots': '…', 'cdots': '⋯', 'prime': '′', 'mid': '|', 'ell': 'ℓ',
    'lbrace': '{', 'rbrace': '}', 'vert': '|', 'Vert': '‖',
}
REL = set('=<>≤≥≈≠∼≡∈→←×+−')
ACCENT = {'hat': '̂', 'tilde': '̃', 'bar': '̄', 'widehat': '̂', 'widetilde': '̃'}
FUNC = {'exp', 'log', 'ln', 'sin', 'cos', 'tan', 'max', 'min', 'arg', 'det', 'lim', 'Re', 'Im', 'sinc', 'tr', 'diag', 'rank'}
CAL = {'L': 'ℒ', 'B': 'ℬ', 'H': 'ℋ', 'N': '𝒩', 'O': '𝒪', 'S': '𝒮', 'P': '𝒫', 'C': '𝒞', 'A': '𝒜'}
IGNORE = {'displaystyle', 'textstyle', 'limits', 'nolimits', '!', 'big', 'Big', 'bigg', 'Bigg', 'bigl', 'bigr', 'Bigl', 'Bigr', 'left', 'right', 'middle'}
_TOK = re.compile(r'\\[A-Za-z]+|\\.|[{}_^]|\s+|.', re.S)


class Complex(Exception):
    """テキストでは書けない式（絵に残す）"""


def simple_math(tex):
    """LaTeX を [文字, 斜体, 太字, 上下('_' / '^' / None)] の列にする．書けなければ Complex"""
    toks = [t for t in _TOK.findall(tex) if not t.isspace()]
    st = {'pos': 0}
    def peek(): return toks[st['pos']] if st['pos'] < len(toks) else None
    def take():
        t = peek(); st['pos'] += 1; return t
    def arg(upright, bold, script):
        if peek() is None: raise Complex('引数が無い')
        if peek() == '{':
            take(); g = group(upright, bold, script)
            if take() != '}': raise Complex('括弧が閉じていない')
            return g
        return atom(take(), [upright], bold, script)
    def atom(t, up, bold, script):
        ch = lambda c, it: [[c, it and not up[0], bold, script]]
        if t == '{':
            g = group(up[0], bold, script)
            if take() != '}': raise Complex('括弧が閉じていない')
            return g
        if t in ('_', '^', '}'): raise Complex('添字の位置がおかしい')
        if t.startswith('\\'):
            n = t[1:]
            if n in GREEK: return ch(GREEK[n], n[0].islower())
            if n in SYM:
                c = SYM[n]; return ch((' ' + c + ' ') if (script is None and c in REL) else c, False)
            if n in IGNORE: return []
            if n == 'rm': up[0] = True; return []
            if n in ('mathrm', 'text', 'textrm', 'operatorname'): return arg(True, bold, script)
            if n in ('mathbf', 'boldsymbol', 'bm'): return arg(True, True, script)
            if n == 'mathit': return arg(False, bold, script)
            if n in ('mathcal', 'mathscr'):
                a = arg(True, bold, script)
                if len(a) != 1 or a[0][0] not in CAL: raise Complex('この花文字は文字に無い')
                a[0][0] = CAL[a[0][0]]; return a
            if n in ACCENT: raise Complex('ハット・チルダ（合成文字で書くと山形が右にずれて別の記号に見える）')
            if n in FUNC: return [[n, False, bold, script]] + ([[' ', False, bold, script]] if n == 'arg' else [])
            if n in (',', ';', ':', ' '): return ch(' ' if n == ',' else ' ', False)
            if n in ('quad', 'qquad'): return ch('　', False)
            if n in ('{', '}'): return ch(n, False)
            if n == '|': return ch('‖', False)
            raise Complex(t)
        if t == "'": return ch('′', False)
        if t == '*': return ch('∗', False)
        if t == '-': t = '−'
        if script is None and t in REL: return ch(' ' + t + ' ', False)
        return ch(t, t.isalpha())
    def group(upright, bold, script):
        up = [upright]; out = []
        while peek() is not None and peek() != '}':
            t = take()
            if t in ('_', '^'):
                out += arg(up[0], bold, script or t)      # 添字の中の添字は，同じ高さに続けて書く
            else:
                out += atom(t, up, bold, script)
        return out
    runs = group(False, False, None)
    if st['pos'] != len(toks): raise Complex('余り')
    merged = []
    for c, it, b, sc in runs:
        if merged and merged[-1][1:] == [it, b, sc]: merged[-1][0] += c
        else: merged.append([c, it, b, sc])
    if merged:                                            # 式の両端の間隔は要らない
        merged[0][0] = merged[0][0].lstrip(' '); merged[-1][0] = merged[-1][0].rstrip(' ')
    return [m for m in merged if m[0]]


def to_html(runs):
    out = []
    for c, it, b, sc in runs:
        s = html.escape(c)
        if it: s = '<i>' + s + '</i>'
        if b: s = '<b>' + s + '</b>'
        if sc: s = ('<sub>' if sc == '_' else '<sup>') + s + ('</sub>' if sc == '_' else '</sup>')
        out.append(s)
    return '<span class="mt">' + ''.join(out) + '</span>'


_MATH = re.compile(r'\$([^$]+)\$')
_SKIP = re.compile(r'(<script\b.*?</script>|<style\b.*?</style>)', re.S | re.I)


def convert_html(src, render=None):
    """HTML の中の $…$ を，テキストで書けるものだけテキストに変える．(変換後, テキストにした数, 残した式の一覧)"""
    n = [0]; kept = []
    def one(m):
        tex = html.unescape(m.group(1))
        try:
            r = to_html(simple_math(tex)); n[0] += 1; return r
        except Complex as e:
            kept.append((str(e), tex)); return render(tex) if render else m.group(0)   # 文字で組めない式は render（eqrender.img_tag）で絵にする
    parts = _SKIP.split(src)
    return ''.join(p if _SKIP.fullmatch(p) else _MATH.sub(one, p) for p in parts), n[0], kept


if __name__ == '__main__':
    import sys
    s, n, kept = convert_html(open(sys.argv[1], encoding='utf-8').read())
    print('テキストにした式', n, '/ 絵に残す式', len(kept))
    for why, tex in kept: print('  ', why, '|', tex[:80])
