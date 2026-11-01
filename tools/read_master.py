"""
パワポのマスター（.pptx / .potx）から，スライドの体裁を読み取って JSON にする．

  スライドの大きさ，テーマの書体と色，レイアウトとプレースホルダーの位置，
  タイトル・本文（段 1〜3）・脚注の書式，飾り（プレースホルダー以外の四角・線・画像・文字），背景

単位は px（96 px/inch．1 px = 9525 EMU）．色は 'RRGGBB'．
build が .build/master.json に保存して使う（マスターが変わったときだけ作り直す）．

使い方: uv run --with python-pptx python read_master.py <master.pptx> [出力.json]
"""
import base64, colorsys, json, re, sys
from pathlib import Path
from lxml import etree
from pptx import Presentation

PX = 9525
NS = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
def q(tag): p, t = tag.split(':'); return '{%s}%s' % (NS[p], t)
def px(v): return round(int(v) / PX, 2)
WARN = []


# ------------------------------------------------------------------ 色
class Colors:
    def __init__(self, theme_xml, clrmap):
        self.scheme = {}
        cs = theme_xml.find('.//a:clrScheme', NS)
        for c in cs if cs is not None else []:
            v = c[0]
            self.scheme[etree.QName(c).localname] = (v.get('lastClr') if etree.QName(v).localname == 'sysClr' else v.get('val')) or '000000'
        self.map = dict(clrmap) if clrmap else {'bg1': 'lt1', 'tx1': 'dk1', 'bg2': 'lt2', 'tx2': 'dk2'}

    def resolve(self, el):
        """a:srgbClr / a:schemeClr / a:sysClr / a:prstClr を 'RRGGBB' にする（lumMod など色の加工も計算する）"""
        if el is None: return None
        name = etree.QName(el).localname
        if name == 'srgbClr': base = el.get('val')
        elif name == 'sysClr': base = el.get('lastClr') or '000000'
        elif name == 'schemeClr':
            v = el.get('val'); v = self.map.get(v, v)
            base = self.scheme.get(v, '000000')
        elif name == 'prstClr': base = {'black': '000000', 'white': 'FFFFFF', 'red': 'FF0000', 'blue': '0000FF'}.get(el.get('val'), '000000')
        else: return None
        r, g, b = (int(base[i:i + 2], 16) / 255 for i in (0, 2, 4))
        for m in el:
            mn, val = etree.QName(m).localname, int(m.get('val', '100000')) / 100000
            if mn in ('lumMod', 'lumOff'):
                h, l, s = colorsys.rgb_to_hls(r, g, b)
                l = l * val if mn == 'lumMod' else min(1, l + val)
                r, g, b = colorsys.hls_to_rgb(h, l, s)
            elif mn == 'tint': r, g, b = (c + (1 - c) * (1 - val) for c in (r, g, b))
            elif mn == 'shade': r, g, b = (c * val for c in (r, g, b))
        return ''.join('%02X' % round(max(0, min(1, c)) * 255) for c in (r, g, b))

    def fill(self, parent):
        """parent の直下の a:solidFill の色（無ければ None）"""
        if parent is None: return None
        f = parent.find('a:solidFill', NS)
        return self.resolve(f[0]) if f is not None and len(f) else None


# ------------------------------------------------------------------ 文字の書式
def font_names(theme_xml):
    out = {}
    for kind, tag in (('major', 'a:majorFont'), ('minor', 'a:minorFont')):
        f = theme_xml.find('.//' + tag, NS)
        if f is None: out[kind] = {'latin': 'Calibri', 'ea': ''}; continue
        lat = f.find('a:latin', NS); ea = f.find('a:ea', NS)
        jp = f.find("a:font[@script='Jpan']", NS)
        out[kind] = {'latin': lat.get('typeface') if lat is not None else 'Calibri',
                     'ea': (ea.get('typeface') if ea is not None and ea.get('typeface') else '') or (jp.get('typeface') if jp is not None else '')}
    return out

def lvl_style(lst, n, colors):
    """a:lstStyle / titleStyle / bodyStyle の a:lvl{n}pPr から，分かる項目だけを辞書にする"""
    if lst is None: return {}
    p = lst.find('a:lvl%dpPr' % n, NS)
    if p is None: return {}
    st = {}
    for k in ('algn', 'marL', 'indent'):
        if p.get(k) is not None: st[k] = p.get(k) if k == 'algn' else px(p.get(k))
    bu = p.find('a:buChar', NS)
    if bu is not None: st['bullet'] = bu.get('char')
    if p.find('a:buNone', NS) is not None: st['bullet'] = ''
    lnspc = p.find('a:lnSpc/a:spcPct', NS)
    if lnspc is not None: st['line'] = int(lnspc.get('val')) / 100000
    r = p.find('a:defRPr', NS)
    if r is not None:
        if r.get('sz'): st['size'] = int(r.get('sz')) / 100
        if r.get('b') is not None: st['bold'] = r.get('b') == '1'
        if r.get('i') is not None: st['italic'] = r.get('i') == '1'
        c = colors.fill(r)
        if c: st['color'] = c
        for k in ('latin', 'ea'):
            e = r.find('a:' + k, NS)
            if e is not None and e.get('typeface'): st[k] = e.get('typeface')
    return st

def body_pr(sp):
    """a:bodyPr の揃え（上下）と内側の余白"""
    bp = sp.find('.//a:bodyPr', NS) if sp is not None else None
    out = {}
    if bp is None: return out
    if bp.get('anchor'): out['anchor'] = bp.get('anchor')
    for k, d in (('lIns', 'pad_l'), ('tIns', 'pad_t'), ('rIns', 'pad_r'), ('bIns', 'pad_b')):
        if bp.get(k) is not None: out[d] = px(bp.get(k))
    return out

def merge(*ds):
    out = {}
    for d in ds:
        for k, v in (d or {}).items():
            if v is not None: out[k] = v
    return out

def fix_fonts(st, fonts, kind):
    """'+mj-lt' などのテーマの書体を名前にする"""
    for k in ('latin', 'ea'):
        v = st.get(k)
        if v in (None, '') or v.startswith('+'):
            grp = 'major' if (v or '').startswith('+mj') or (v is None and kind == 'major') else 'minor'
            st[k] = fonts[grp]['latin' if k == 'latin' else 'ea']
    return st


# ------------------------------------------------------------------ プレースホルダー
def ph_info(sp):
    ph = sp.find('.//p:nvPr/p:ph', NS)
    if ph is None: return None
    return {'type': ph.get('type', 'body'), 'idx': int(ph.get('idx', '0'))}

def xfrm(sp):
    x = sp.find('.//p:spPr/a:xfrm', NS) if etree.QName(sp).localname != 'grpSp' else sp.find('p:grpSpPr/a:xfrm', NS)
    if x is None: return None
    off, ext = x.find('a:off', NS), x.find('a:ext', NS)
    if off is None or ext is None: return None
    return {'x': px(off.get('x')), 'y': px(off.get('y')), 'w': px(ext.get('cx')), 'h': px(ext.get('cy')),
            'flipH': x.get('flipH') == '1', 'flipV': x.get('flipV') == '1', 'rot': int(x.get('rot', '0')) / 60000}

def placeholders(tree):
    out = []
    for sp in tree.iter(q('p:sp')):
        info = ph_info(sp)
        if info is None: continue
        info['rect'] = xfrm(sp); info['el'] = sp
        out.append(info)
    return out

def ph_text(sp):
    """プレースホルダーに書かれた文字（フィールドは除く）．脚注の名前の既定値に使う"""
    return '\n'.join(''.join(r.text or '' for r in p.iter(q('a:t')) if etree.QName(r.getparent()).localname == 'r')
                     for p in sp.iter(q('a:p'))).strip()

SAME = {'ctrTitle': 'title', 'subTitle': 'body', 'obj': 'body'}
def find_ph(phs, typ, idx=None):
    for p in phs:
        if p['type'] == typ and (idx is None or p['idx'] == idx): return p
    for p in phs:
        if SAME.get(p['type'], p['type']) == SAME.get(typ, typ): return p
    return None


# ------------------------------------------------------------------ 飾り（プレースホルダー以外の図形）
def deco_shapes(tree, part, colors, fonts, off=(0, 0), scale=(1, 1), where=''):
    out = []
    for el in tree:
        name = etree.QName(el).localname
        if name == 'sp' and ph_info(el) is not None: continue
        if name not in ('sp', 'cxnSp', 'pic', 'grpSp'): continue
        r = xfrm(el)
        if r is None: continue
        r = {'x': off[0] + r['x'] * scale[0], 'y': off[1] + r['y'] * scale[1], 'w': r['w'] * scale[0], 'h': r['h'] * scale[1], 'rot': r['rot']}
        label = (el.find('.//p:cNvPr', NS).get('name') if el.find('.//p:cNvPr', NS) is not None else name)
        if name == 'grpSp':                                         # グループは子の座標を親の枠へ写す
            gx = el.find('p:grpSpPr/a:xfrm', NS); ch, ce = gx.find('a:chOff', NS), gx.find('a:chExt', NS)
            cw, chh = px(ce.get('cx')) or 1, px(ce.get('cy')) or 1
            sx, sy = r['w'] / cw, r['h'] / chh
            out += deco_shapes(el, part, colors, fonts, (r['x'] - px(ch.get('x')) * sx, r['y'] - px(ch.get('y')) * sy), (sx, sy), where)
            continue
        if name == 'pic':
            blip = el.find('.//a:blip', NS)
            rid = blip.get(q('r:embed')) if blip is not None else None
            if not rid: continue
            img = part.related_part(rid)
            out.append({'kind': 'img', 'rect': r, 'mime': img.content_type, 'data': base64.b64encode(img.blob).decode(), 'name': label})
            continue
        sppr = el.find('p:spPr', NS)
        geom = sppr.find('a:prstGeom', NS) if sppr is not None else None
        g = geom.get('prst') if geom is not None else 'custom'
        ln = sppr.find('a:ln', NS) if sppr is not None else None
        line_w = px(ln.get('w', '9525')) if ln is not None else 0
        line_c = colors.fill(ln) if ln is not None and ln.find('a:noFill', NS) is None else None
        if line_c is None and ln is not None and ln.find('a:noFill', NS) is None:   # 線の色がスタイルの側にある場合
            lr = el.find('p:style/a:lnRef', NS)
            if lr is not None and len(lr) and lr.get('idx') != '0': line_c = colors.resolve(lr[0])
        if name == 'cxnSp' or g in ('line', 'straightConnector1'):
            if r['w'] > 0.5 and r['h'] > 0.5: WARN.append(f'{where}: 斜めの線「{label}」は HTML では描かない（パワポには出る）'); continue
            if line_c is None: continue
            out.append({'kind': 'line', 'rect': r, 'color': line_c, 'width': line_w, 'name': label})
            continue
        fill = colors.fill(sppr) if sppr is not None else None
        if fill is None and sppr is not None and sppr.find('a:noFill', NS) is None and sppr.find('a:gradFill', NS) is None and sppr.find('a:blipFill', NS) is None:
            fr = el.find('p:style/a:fillRef', NS)
            if fr is not None and len(fr) and fr.get('idx') != '0': fill = colors.resolve(fr[0])
        if sppr is not None and (sppr.find('a:gradFill', NS) is not None or sppr.find('a:blipFill', NS) is not None):
            WARN.append(f'{where}: 「{label}」のグラデーション・画像の塗りは HTML では単色にできないので描かない（パワポには出る）'); continue
        if g not in ('rect', 'roundRect', 'ellipse', 'snip1Rect', 'round1Rect', 'round2SameRect'):
            WARN.append(f'{where}: 「{label}」の形（{g}）は HTML では四角で近似する')
        text = []
        for p in el.findall('.//a:p', NS):
            t = ''.join(x.text or '' for x in p.iter(q('a:t')))
            if t: text.append(t)
        tstyle = {}
        r0 = el.find('.//a:r/a:rPr', NS)
        if r0 is not None:
            if r0.get('sz'): tstyle['size'] = int(r0.get('sz')) / 100
            tstyle['bold'] = r0.get('b') == '1'
            c = colors.fill(r0)
            if c: tstyle['color'] = c
        fr = el.find('p:style/a:fontRef', NS)
        if 'color' not in tstyle and fr is not None and len(fr): tstyle['color'] = colors.resolve(fr[0])
        algn = el.find('.//a:p/a:pPr', NS)
        tstyle['algn'] = algn.get('algn') if algn is not None and algn.get('algn') else 'l'
        tstyle.update(body_pr(el))
        if fill is None and line_c is None and not text: continue
        out.append({'kind': 'shape', 'geom': g, 'rect': r, 'fill': fill, 'line': line_c, 'line_w': line_w if line_c else 0,
                    'text': text, 'text_style': tstyle, 'name': label})
    return out

def background(cSld, colors, part):
    bg = cSld.find('p:bg', NS)
    if bg is None: return None
    pr = bg.find('p:bgPr', NS)
    if pr is not None:
        c = colors.fill(pr)
        if c: return {'color': c}
        blip = pr.find('.//a:blip', NS)
        if blip is not None and blip.get(q('r:embed')):
            img = part.related_part(blip.get(q('r:embed')))
            return {'image': base64.b64encode(img.blob).decode(), 'mime': img.content_type}
        if pr.find('a:gradFill', NS) is not None:
            gs = pr.find('.//a:gs', NS)
            WARN.append('背景のグラデーションは，最初の色の単色で近似する')
            return {'color': colors.resolve(gs[0])} if gs is not None and len(gs) else None
    ref = bg.find('p:bgRef', NS)
    if ref is not None and len(ref): return {'color': colors.resolve(ref[0])}
    return None


# ------------------------------------------------------------------ 本体
def read(path):
    WARN.clear()
    prs = Presentation(path)
    master = prs.slide_master
    mel = master.element
    theme_part = next(r.target_part for r in master.part.rels.values() if r.reltype.endswith('/theme'))
    theme = etree.fromstring(theme_part.blob)
    cm = mel.find('p:clrMap', NS)
    colors = Colors(theme, cm.attrib if cm is not None else None)
    fonts = font_names(theme)
    W, H = px(prs.slide_width), px(prs.slide_height)

    m_tree = mel.find('p:cSld/p:spTree', NS)
    m_phs = placeholders(m_tree)
    tx = mel.find('p:txStyles', NS)
    title_st = tx.find('p:titleStyle', NS) if tx is not None else None
    body_st = tx.find('p:bodyStyle', NS) if tx is not None else None
    m_title = find_ph(m_phs, 'title'); m_body = find_ph(m_phs, 'body')
    m_deco = deco_shapes(m_tree, master.part, colors, fonts, where='マスター')
    m_bg = background(mel.find('p:cSld', NS), colors, master.part)

    def ph_style(kind, lay_ph, lvl=1):
        """プレースホルダーの文字の書式: マスターの txStyles → マスターのプレースホルダー → レイアウトのプレースホルダー"""
        base = lvl_style(title_st if kind == 'title' else body_st, lvl, colors)
        mp = m_title if kind == 'title' else (find_ph(m_phs, lay_ph['type']) if lay_ph else m_body) or m_body
        mst = lvl_style(mp['el'].find('.//a:lstStyle', NS), lvl, colors) if mp is not None else {}
        lst = lvl_style(lay_ph['el'].find('.//a:lstStyle', NS), lvl, colors) if lay_ph is not None else {}
        bp = merge(body_pr(mp['el']) if mp is not None else {}, body_pr(lay_ph['el']) if lay_ph is not None else {})
        st = fix_fonts(merge(base, mst, lst), fonts, 'major' if kind == 'title' else 'minor')
        st.setdefault('color', colors.resolve(etree.fromstring('<a:schemeClr xmlns:a="%s" val="tx1"/>' % NS['a'])))
        st.update(bp)
        return st

    body_levels = []
    for n in (1, 2, 3):
        s = fix_fonts(merge(lvl_style(body_st, n, colors), lvl_style(m_body['el'].find('.//a:lstStyle', NS), n, colors) if m_body else {}), fonts, 'minor')
        body_levels.append(s)

    def foot_style(typ, lay_ph):
        mp = find_ph(m_phs, typ)
        st = merge({'size': 12, 'color': '898989', 'algn': {'dt': 'l', 'ftr': 'ctr', 'sldNum': 'r'}[typ]},
                   lvl_style(mp['el'].find('.//a:lstStyle', NS), 1, colors) if mp is not None else {},
                   lvl_style(lay_ph['el'].find('.//a:lstStyle', NS), 1, colors) if lay_ph is not None else {})
        st.update(merge(body_pr(mp['el']) if mp is not None else {}, body_pr(lay_ph['el']) if lay_ph is not None else {}))
        return fix_fonts(st, fonts, 'minor')

    layouts = []
    for i, lay in enumerate(prs.slide_layouts):
        lel = lay.element
        tree = lel.find('p:cSld/p:spTree', NS)
        phs = placeholders(tree)
        show_master = lel.get('showMasterSp') != '0'
        deco = (list(m_deco) if show_master else []) + deco_shapes(tree, lay.part, colors, fonts, where='レイアウト「%s」' % lay.name)
        entry = {'index': i, 'name': lay.name, 'type': lel.get('type', 'cust'), 'show_master': show_master,
                 'placeholders': [], 'deco': deco, 'background': background(lel.find('p:cSld', NS), colors, lay.part) or m_bg}
        for p in phs:
            mp = find_ph(m_phs, p['type'], None)
            rect = p['rect'] or (mp['rect'] if mp else None)
            kind = 'title' if p['type'] in ('title', 'ctrTitle') else ('foot' if p['type'] in ('dt', 'ftr', 'sldNum') else 'body')
            st = foot_style(p['type'], p) if kind == 'foot' else ph_style(kind, p)
            entry['placeholders'].append({'type': p['type'], 'idx': p['idx'], 'rect': rect, 'style': st, 'text': ph_text(p['el'])})
        # レイアウトに無い脚注は，マスターの位置と書式で出す（パワポの側でも同じ位置に文字の箱を置く）
        have = {p['type'] for p in phs}
        for typ in ('dt', 'ftr', 'sldNum'):
            mp = find_ph(m_phs, typ)
            if typ not in have and mp is not None and mp['rect']:
                entry['placeholders'].append({'type': typ, 'idx': mp['idx'], 'rect': mp['rect'], 'style': foot_style(typ, None), 'text': ph_text(mp['el']), 'from_master': True})
        layouts.append(entry)

    return {
        'source': Path(path).name,
        'size': {'w': W, 'h': H, 'emu_w': int(prs.slide_width), 'emu_h': int(prs.slide_height), 'aspect': aspect_name(W, H)},
        'fonts': fonts, 'colors': colors.scheme,
        'text_color': colors.resolve(etree.fromstring('<a:schemeClr xmlns:a="%s" val="tx1"/>' % NS['a'])),
        'body_levels': body_levels,
        'master_body_rect': m_body['rect'] if m_body else None,
        'layouts': layouts,
        'auto': auto_layouts(layouts, H),
        'warnings': list(dict.fromkeys(WARN)),
    }

def aspect_name(w, h):
    r = w / h
    for name, v in (('4:3', 4 / 3), ('16:9', 16 / 9), ('16:10', 1.6), ('A4', 297 / 210)):
        if abs(r - v) < 0.01: return name
    return '%.3f' % r

def auto_layouts(layouts, H):
    """本文用（タイトルだけのレイアウト）と表紙用（タイトル + サブタイトル）を選ぶ"""
    def types(l): return {p['type'] for p in l['placeholders']}
    def title_y(l):
        t = next((p for p in l['placeholders'] if p['type'] == 'title' and p['rect']), None)
        return t['rect']['y'] if t else 1e9
    cover = next((l for l in layouts if l['type'] == 'title'), None) or next((l for l in layouts if {'ctrTitle', 'subTitle'} <= types(l)), None)
    content = next((l for l in layouts if l['type'] == 'titleOnly'), None)
    if content is None:
        only = [l for l in layouts if 'title' in types(l) and types(l) <= {'title', 'dt', 'ftr', 'sldNum'}]
        only = [l for l in only if title_y(l) < H * 0.25]
        content = min(only, key=title_y) if only else None
    if content is None:
        withbody = [l for l in layouts if 'title' in types(l) and l['type'] in ('obj', 'tx', 'cust')]
        content = min(withbody, key=title_y) if withbody else None
    if content is None: content = layouts[0]
    return {'content': content['name'], 'cover': cover['name'] if cover else None}


def strip(d):
    """JSON に書けない lxml の要素を落とす"""
    if isinstance(d, dict): return {k: strip(v) for k, v in d.items() if k != 'el'}
    if isinstance(d, list): return [strip(v) for v in d]
    return d

if __name__ == '__main__':
    data = strip(read(sys.argv[1]))
    s = json.dumps(data, ensure_ascii=False, indent=1)
    if len(sys.argv) > 2: Path(sys.argv[2]).write_text(s, encoding='utf-8')
    else:
        short = json.loads(s)
        for l in short['layouts']:
            for d in l['deco']:
                d.pop('data', None)
        print(json.dumps(short, ensure_ascii=False, indent=1)[:6000])
    for w in data['warnings']: print('注意:', w, file=sys.stderr)
