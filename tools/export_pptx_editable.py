"""
スライドの HTML から「全部編集できる」パワポを作る（プロファイルのマスターの上に置き直す）．

  タイトル・表紙・脚注        … マスターのプレースホルダー（色・大きさはマスターのまま）
  日付                         … 開いた日に自動で変わるフィールド（設定の footer.date_format の書式）
  文                           … 編集できるテキスト（設定の書体）．色・箇条書きの記号・改行位置は HTML と同じ
  表                           … パワポの表
  式                           … テキストで書けるものは斜体・上付き・下付きのテキスト（build が HTML の段階で変える）
                                 文字で組めない式はパワポの数式（Office の数式．pandoc で変換）．代わりの表示として画像も入れる
                                 （PowerPoint では数式，LibreOffice などでは画像が出る）．変換できない式・pandoc が無いときは画像だけ
                                 設定の math.plugin に式のプラグインを書けば，それが先に置く
  図                           … 画像

位置と改行は，ブラウザ（Chrome）で測った HTML のレイアウトをそのまま写す．
使い方: build.sh が呼ぶ（python3 export_pptx_editable.py <資料のフォルダ> <名前>.html <出力.pptx>）
"""
import base64, datetime, io, json, sys, time
from html import escape
from pathlib import Path
from lxml import etree
from pptx import Presentation
from pptx.util import Emu
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
from playwright.sync_api import sync_playwright
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); import eqrender, omml, theme_css

PX = 9525                                    # 1px（96 px/inch）
NS_A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
NS_P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
NS_A14 = 'http://schemas.microsoft.com/office/drawing/2010/main'
NS_MC = 'http://schemas.openxmlformats.org/markup-compatibility/2006'
def A(tag): return '{%s}%s' % (NS_A, tag)
F = {'latin': 'Arial', 'ea': 'Arial'}        # 書体（main で設定から入れる）
DATE_FIELD = {'en-long': ('datetime4', 'en-US'), 'ymd': ('datetime1', 'ja-JP'), 'iso': (None, None)}


# ------------------------------------------------------------------ テキストの XML
def rpr(el, pt, color='000000', bold=False, italic=False, script=None, latin=None, ea=None):
    el.set('lang', 'ja-JP'); el.set('altLang', 'en-US'); el.set('sz', str(int(round(pt * 100)))); el.set('b', '1' if bold else '0'); el.set('i', '1' if italic else '0')
    if script: el.set('baseline', '-25000' if script == '_' else '30000')
    f = etree.SubElement(el, A('solidFill')); etree.SubElement(f, A('srgbClr')).set('val', color)
    etree.SubElement(el, A('latin')).set('typeface', latin or F['latin']); etree.SubElement(el, A('ea')).set('typeface', ea or F['ea']); etree.SubElement(el, A('cs')).set('typeface', latin or F['latin'])
    return el

def add_run(p, text, pt, **kw):
    r = etree.SubElement(p, A('r')); rpr(etree.SubElement(r, A('rPr')), pt, **kw); etree.SubElement(r, A('t')).text = text

class Ctx:
    """1 枚のスライドに式や画像を置くための入れ物"""
    def __init__(self, slide, page, stats, R):
        self.slide, self.page, self.stats, self.pending, self.sc, self.R = slide, page, stats, [], 1, R

def fill_paragraph(body, para, ctx, bullet=None, mar=0, indent=0, spc_before=0, bold=False, align=None, box_x=None):
    """para（JS が測った 1 段落）を txBody に書く．行の切れ目は HTML と同じ位置で改行する．
    背の高い式を含む行は HTML では行の間隔が広がるので，そこで段落を分けて前の間隔で合わせる"""
    pt = para['fs'] * 0.75; lines = para['lines'] or [{'y': 0, 'runs': []}]
    def new_p(first, gap):
        p = etree.SubElement(body, A('p')); ppr = etree.SubElement(p, A('pPr'))
        ppr.set('marL', str(int(mar * PX))); ppr.set('indent', str(int(indent * PX)) if first else '0')
        ppr.set('algn', {'center': 'ctr', 'right': 'r'}.get(align or para.get('align'), 'l'))
        ln = etree.SubElement(ppr, A('lnSpc')); etree.SubElement(ln, A('spcPts')).set('val', str(int(round(para['lh'] * 0.75 * 100))))
        sb = etree.SubElement(ppr, A('spcBef')); etree.SubElement(sb, A('spcPts')).set('val', str(int(round(max(gap, 0) * 0.75 * 100))))
        sa = etree.SubElement(ppr, A('spcAft')); etree.SubElement(sa, A('spcPts')).set('val', '0')
        if bullet and first:
            etree.SubElement(ppr, A('buFont')).set('typeface', theme_css.bullet_font(bullet, F['latin'], F['ea'])); etree.SubElement(ppr, A('buChar')).set('char', bullet)
        else:
            etree.SubElement(ppr, A('buNone'))
        return p
    p = new_p(True, spc_before)
    for k, line in enumerate(lines):
        if k:
            extra = line['y'] - lines[k - 1]['y'] - para['lh']
            if abs(extra) > 2:
                rpr(etree.SubElement(p, A('endParaRPr')), pt); p = new_p(False, extra)
            else:
                br = etree.SubElement(p, A('br')); rpr(etree.SubElement(br, A('rPr')), pt)
        for ri, run in enumerate(line['runs']):
            rpt = run['fs'] * 0.75 * ctx.sc
            ctx.stats['sizes'].add(round(run['fs'] * ctx.sc, 1))
            rest = line['runs'][ri + 1:]
            if 'gap' in run and box_x is not None and rest and all('t' in x for x in rest):
                # 行の最後の空きの後ろ（右寄せの式の番号など）は，測った右端に右揃えの文字の箱を別に置く（書体の幅が違っても右端にそろう）
                w = line['right'] - run['x'] + 30
                tb = textbox(ctx, line['right'] - w, line['y'] - para['lh'] / 2, w, para['lh'], wrap=False, anchor='ctr')
                q = etree.SubElement(tb, A('p')); qp = etree.SubElement(q, A('pPr')); qp.set('algn', 'r'); etree.SubElement(qp, A('buNone'))
                for x in rest:
                    add_run(q, x['t'], x['fs'] * 0.75 * ctx.sc, color=x['color'], bold=x['bold'] or bold, italic=x.get('italic', False), script=x.get('script'))
                break
            if 'gap' in run:                                       # 文の途中の大きな空き
                r = etree.SubElement(p, A('r')); rp = rpr(etree.SubElement(r, A('rPr')), rpt)
                rp.set('spc', str(int(round((run['gap'] * 0.75 - 0.278 * rpt) * 100)))); etree.SubElement(r, A('t')).text = '\u00a0'; continue
            if 't' in run:                                         # 文字（テキストで書いた式もここ．斜体・上付き・下付きをそのまま写す）
                add_run(p, run['t'], rpt, color=run['color'], bold=run['bold'] or bold, italic=run.get('italic', False), script=run.get('script')); continue
            ctx.pending.append((run, rpt))                         # 残った式は画像（かプラグイン）を重ね，文の側は空白で場所を空ける
            r = etree.SubElement(p, A('r')); rp = rpr(etree.SubElement(r, A('rPr')), rpt)
            rp.set('spc', str(int(round((run['rect']['w'] * 0.75 - 0.278 * rpt) * 100)))); etree.SubElement(r, A('t')).text = ' '
    rpr(etree.SubElement(p, A('endParaRPr')), pt)

def top_of(para):                                    # 1 行目の上端（行の中心 − 行送りの半分）
    return para['lines'][0]['y'] - para['lh'] / 2 if para['lines'] else para['rect']['y']

def bottom_of(para):
    return para['lines'][-1]['y'] + para['lh'] / 2 if para['lines'] else para['rect']['y'] + para['rect']['h']

def textbox(ctx, x, y, w, h, wrap=True, anchor='t'):
    tb = ctx.slide.shapes.add_textbox(Emu(int(x * PX)), Emu(int(y * PX)), Emu(int(max(w, 1) * PX)), Emu(int(max(h, 1) * PX)))
    body = tb.text_frame._txBody
    bp = body.find(A('bodyPr'))
    for k in ('lIns', 'tIns', 'rIns', 'bIns'): bp.set(k, '0')
    bp.set('wrap', 'square' if wrap else 'none'); bp.set('anchor', anchor)
    for c in list(bp): bp.remove(c)
    etree.SubElement(bp, A('noAutofit'))
    for p in body.findall(A('p')): body.remove(p)
    return body

def office_math(ctx, om, pic, r, size, color, tex, left=False):
    """パワポの数式を置く．PowerPoint が自分で数式を保存するときと同じく，数式の箱を mc:AlternateContent で包み，
    代わりの表示（Fallback）に式の画像を入れる（数式を描けないアプリでは画像が出る）．
    PowerPoint の数式は LaTeX の絵より幅が広くなることがある．番号つきの式（left）は測った左端にそろえ，広がる分は右（番号との間）へ逃がす．
    文中の式は測った中心にそろえる"""
    pad = r['w'] * 0.5
    x0, w = (r['x'], r['w'] + 2 * pad) if left else (r['x'] - pad, r['w'] + 2 * pad)
    tb = ctx.slide.shapes.add_textbox(Emu(int(x0 * PX)), Emu(int(r['y'] * PX)), Emu(int(w * PX)), Emu(int(r['h'] * PX)))
    body = tb.text_frame._txBody; bp = body.find(A('bodyPr'))
    for k in ('lIns', 'tIns', 'rIns', 'bIns'): bp.set(k, '0')
    bp.set('wrap', 'none'); bp.set('anchor', 'ctr')
    for c in list(bp): bp.remove(c)
    etree.SubElement(bp, A('noAutofit'))
    for p in body.findall(A('p')): body.remove(p)
    p = etree.SubElement(body, A('p')); ppr = etree.SubElement(p, A('pPr')); ppr.set('algn', 'l' if left else 'ctr'); ppr.set('marL', '0'); ppr.set('indent', '0')
    etree.SubElement(ppr, A('buNone'))                              # マスターの既定の文字に記号があっても付けない（付くと式が文中扱いになる）
    om = omml.for_pptx(om, size, color, ea=F['ea'])
    if left: om = omml.para(om, 'left')                             # 式だけの段落は PowerPoint が中央にそろえるので，式の側で左を指定する
    etree.SubElement(p, '{%s}m' % NS_A14, nsmap={'a14': NS_A14}).append(om)
    sp = tb._element; tree = sp.getparent(); i = tree.index(sp)
    for el in (sp, pic._element):                                   # 代替テキストは LaTeX のまま（読み上げ・アクセシビリティの確認用）
        el.find('.//' + qn('p:cNvPr')).set('descr', tex)
    ac = etree.Element('{%s}AlternateContent' % NS_MC, nsmap={'mc': NS_MC})
    etree.SubElement(ac, '{%s}Choice' % NS_MC, Requires='a14', nsmap={'a14': NS_A14}).append(sp)
    etree.SubElement(ac, '{%s}Fallback' % NS_MC).append(pic._element)
    tree.insert(i, ac)

def place_math(ctx):
    """文の上に重ねる式を置く．順に，プラグイン → パワポの数式（代わりに画像つき）→ 画像"""
    tiers = sorted({round(v, 2) for v in ctx.R['sizes'].values()})
    for run, pt in ctx.pending:
        r = run['rect']; tex = run['math']
        size = min(tiers, key=lambda v: abs(v - pt)); size = size if abs(size - pt) < 0.7 else round(pt * 2) / 2
        why = PLUGIN_WHY
        if PLUGIN is not None:
            try:
                color = None if run['color'] == '000000' else tuple(int(run['color'][i:i + 2], 16) for i in (0, 2, 4))
                PLUGIN.add(ctx.slide, tex, size, color, tuple(int(r[k] * PX) for k in ('x', 'y', 'w', 'h')))
                ctx.stats['plugin'] += 1; ctx.stats['custom'] += size not in tiers
                continue
            except Exception as e: why = 'プラグイン: ' + str(e).splitlines()[0]
        png = ctx.page.locator('[data-mid="%s"]' % run['id']).screenshot()
        pic = ctx.slide.shapes.add_picture(io.BytesIO(png), Emu(int(r['x'] * PX)), Emu(int(r['y'] * PX)), Emu(int(r['w'] * PX)), Emu(int(r['h'] * PX)))
        if OFFICE:
            try:
                office_math(ctx, omml.to_omml(tex), pic, r, size, run['color'], tex, left=run.get('eq', False))
                ctx.stats['office'] += 1; ctx.stats['custom'] += size not in tiers
                continue
            except Exception as e: why = str(e).splitlines()[0]
        else: why = OFFICE_WHY
        ctx.stats['image'].append((ctx.stats['slide'], why[:60], tex[:70]))
    ctx.pending = []


# ------------------------------------------------------------------ 要素ごとの配置
def n_lines(p): return max(len(p['lines']), 1)

def put_para(ctx, it):
    # 右に余裕を持たせ，パワポ側で勝手に折り返されないようにする（改行は HTML と同じ位置に入れてある）
    w = min(it['rect']['w'] + 40, ctx.R['W'] - 8 - it['rect']['x'])
    body = textbox(ctx, it['rect']['x'], top_of(it), w, it['rect']['h'])
    bullet = {'lead': ctx.R['bullets']['lead'], 'cap': ctx.R['bullets']['body']}.get(it['kind'])
    fill_paragraph(body, it, ctx, bullet=bullet, mar=it['padL'], indent=-it['padL'], box_x=it['rect']['x'])

def put_list(ctx, it):
    ps = it['paras']; x0 = it['rect']['x']
    body = textbox(ctx, x0, top_of(ps[0]), min(it['rect']['w'] + 40, ctx.R['W'] - 8 - x0), it['rect']['h'])
    for k, p in enumerate(ps):
        gap = 0 if k == 0 else top_of(p) - bottom_of(ps[k - 1])
        bu = ctx.R['bullets']['body'] if p['level'] == 0 else ctx.R['bullets']['sub']
        fill_paragraph(body, p, ctx, bullet=bu, mar=p['rect']['x'] - x0 + p['padL'], indent=-p['padL'], spc_before=gap, box_x=x0)

def put_box(ctx, it):
    r = it['rect']
    sh = ctx.slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(int(r['x'] * PX)), Emu(int(r['y'] * PX)), Emu(int(r['w'] * PX)), Emu(int(r['h'] * PX)))
    c = ctx.R['colors']['box_border']
    sh.fill.background(); sh.line.color.rgb = RGBColor.from_string(c); sh.line.width = Emu(int(2 * PX)); sh.shadow.inherit = False
    pad = it['padL']
    body = textbox(ctx, r['x'] + pad, top_of(it), r['w'] - pad, r['h'])          # 右の余白ぶん広げ，字幅の違いで折り返さないようにする
    fill_paragraph(body, it, ctx, box_x=r['x'] + pad)

def put_img(ctx, it):
    src = ctx.page.evaluate('id => document.querySelector(`[data-iid="${id}"]`).src', it['iid'])
    r = it['rect']
    if src.startswith('data:image/svg') or not src.startswith('data:'):
        png = ctx.page.locator('[data-iid="%s"]' % it['iid']).screenshot()      # SVG や外部の図は，見えている絵をそのまま使う
    else:
        png = base64.b64decode(src.split(',', 1)[1])
    ctx.slide.shapes.add_picture(io.BytesIO(png), Emu(int(r['x'] * PX)), Emu(int(r['y'] * PX)), Emu(int(r['w'] * PX)), Emu(int(r['h'] * PX)))

def _border(tcpr, on, color):
    for side in ('lnL', 'lnR', 'lnT', 'lnB'):
        ln = etree.SubElement(tcpr, A(side))
        if on:
            ln.set('w', str(PX)); f = etree.SubElement(ln, A('solidFill')); etree.SubElement(f, A('srgbClr')).set('val', color)
        else:
            ln.set('w', '0'); etree.SubElement(ln, A('noFill'))

def put_table(ctx, it):
    rows = it['rows']; nr, nc = len(rows), max(len(r) for r in rows); r0 = it['rect']
    if any(len(r) != nc for r in rows): raise ValueError('結合したセルのある表は未対応')
    gf = ctx.slide.shapes.add_table(nr, nc, Emu(int(r0['x'] * PX)), Emu(int(r0['y'] * PX)), Emu(int(r0['w'] * PX)), Emu(int(r0['h'] * PX)))
    tbl = gf.table; tblPr = tbl._tbl.tblPr
    for k in ('firstRow', 'bandRow'): tblPr.set(k, '0')
    sid = tblPr.find(A('tableStyleId'))
    if sid is None: sid = etree.SubElement(tblPr, A('tableStyleId'))
    sid.text = '{2D5ABB26-0587-4C30-8999-92F81FD0307C}'            # スタイルなし・罫線なし（罫線と塗りはセルごとに付ける）
    for j in range(nc): tbl.columns[j].width = Emu(int(rows[0][j]['rect']['w'] * PX))
    for i in range(nr): tbl.rows[i].height = Emu(int(rows[i][0]['rect']['h'] * PX))
    for i, row in enumerate(rows):
        for j, c in enumerate(row):
            tc = tbl.cell(i, j)._tc
            body = tc.find(A('txBody'))
            for p in body.findall(A('p')): body.remove(p)
            fill_paragraph(body, c, ctx, bold=c['bold'])
            tcpr = tc.find(A('tcPr'))
            if tcpr is None: tcpr = etree.SubElement(tc, A('tcPr'))
            for ch in list(tcpr): tcpr.remove(ch)
            pad = int(min(c['padL'], 6) * PX)
            tcpr.set('marL', str(pad)); tcpr.set('marR', str(pad)); tcpr.set('marT', '0'); tcpr.set('marB', '0'); tcpr.set('anchor', 'ctr')
            _border(tcpr, c['border'], c.get('borderColor', '000000'))
            if c['hasFill']:
                f = etree.SubElement(tcpr, A('solidFill')); etree.SubElement(f, A('srgbClr')).set('val', c['fill'])
            else:
                etree.SubElement(tcpr, A('noFill'))

PUT = {'para': put_para, 'list': put_list, 'box': put_box, 'img': put_img, 'table': put_table}


# ------------------------------------------------------------------ 脚注（マスターの部品）
PH = '''<p:sp xmlns:p="%(p)s" xmlns:a="%(a)s"><p:nvSpPr><p:cNvPr id="%(id)d" name="%(name)s"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>
<p:nvPr><p:ph type="%(type)s" sz="quarter" idx="%(idx)d"/></p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/><a:p>%(body)s</a:p></p:txBody></p:sp>'''

def foot_body(typ, R, today, rpr_xml):
    ft = R['footer']
    if typ == 'ftr': return '<a:r>%s<a:t>%s</a:t></a:r>' % (rpr_xml, escape(ft['text']))
    if typ == 'sldNum': return '<a:fld id="{EAF98E47-F0C4-4887-A05D-5E9F7E355DE0}" type="slidenum">%s<a:t>‹#›</a:t></a:fld>' % rpr_xml
    kind, lang = DATE_FIELD.get(ft.get('date_format', 'en-long'), (None, None))
    if ft.get('date') == 'field' and kind and not ft.get('date_value'):
        return '<a:fld id="{3AFDAFF1-9B2A-45F7-9168-4939F684F6F7}" type="%s">%s<a:t>%s</a:t></a:fld>' % (kind, rpr_xml.replace('lang="ja-JP"', 'lang="%s"' % lang), today)
    return '<a:r>%s<a:t>%s</a:t></a:r>' % (rpr_xml, today)

def add_footer(slide, R, layout_name, today):
    tree = slide.shapes._spTree; ns = {'p': NS_P, 'a': NS_A}
    nid = lambda: max(int(e.get('id')) for e in tree.iter(qn('p:cNvPr'))) + 1
    ft = R['footer']
    for typ, p in R['foot_ph'].get(layout_name, {}).items():
        if (typ == 'dt' and ft.get('date') == 'none') or (typ == 'ftr' and not ft.get('text')) or (typ == 'sldNum' and not ft.get('number', True)): continue
        if not p.get('from_master'):                                   # レイアウトにある部品: 位置と書式はマスターのまま，文字だけ入れる
            body = foot_body(typ, R, today, '<a:rPr lang="ja-JP" altLang="en-US"/>')
            tree.append(etree.fromstring(PH % dict(ns, id=nid(), name=typ, type=typ, idx=p['idx'], body=body)))
            continue
        st, r = p['style'], p['rect']                                  # レイアウトに無い部品: マスターの位置と書式で文字の箱を置く
        el = etree.Element(A('rPr')); rpr(el, st.get('size', 12), st.get('color', '777777'), st.get('bold', False), latin=st.get('latin'), ea=st.get('ea'))
        rx = etree.tostring(el, encoding='unicode').replace(' xmlns:a="%s"' % NS_A, '')
        sp = etree.fromstring('''<p:sp xmlns:p="%(p)s" xmlns:a="%(a)s"><p:nvSpPr><p:cNvPr id="%(id)d" name="%(name)s"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
<p:spPr><a:xfrm><a:off x="%(x)d" y="%(y)d"/><a:ext cx="%(w)d" cy="%(h)d"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
<p:txBody><a:bodyPr vert="horz" wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" rtlCol="0" anchor="ctr"/><a:lstStyle/><a:p><a:pPr algn="%(algn)s"><a:buNone/></a:pPr>%(body)s</a:p></p:txBody></p:sp>''' % dict(
            ns, id=nid(), name=typ, x=int(r['x'] * PX), y=int(r['y'] * PX), w=int(r['w'] * PX), h=int(r['h'] * PX), algn=st.get('algn', 'l'),
            body=foot_body(typ, R, today, rx)))
        tree.append(sp)


def keep_placeholders(slide, types):
    for ph in list(slide.placeholders):
        if ph.placeholder_format.type is None: continue
        t = ph._element.find('.//' + qn('p:ph')).get('type', 'body')
        if t not in types: ph._element.getparent().remove(ph._element)


# ------------------------------------------------------------------ 本体
PLUGIN, PLUGIN_WHY = None, 'math.plugin が無い'
OFFICE, OFFICE_WHY = False, ''

def load_plugin(path):
    """式のプラグイン（.py）を読む．add(slide, tex, size_pt, color, (x, y, w, h) の EMU) で式を置き，置けなければ例外を出す．
    setup(tex) があれば，HTML の式の絵と同じ LaTeX のひな形（%s に式）を渡す"""
    import importlib.util
    spec = importlib.util.spec_from_file_location('slide_math_plugin', path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    if hasattr(mod, 'setup'): mod.setup(eqrender.TEX)
    return mod

def main():
    global PLUGIN, PLUGIN_WHY, OFFICE, OFFICE_WHY
    deck, html, out = Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3]
    res = json.loads((deck / '.build' / 'resolved.json').read_text(encoding='utf-8'))
    cfg, R = res['config'], res['theme']
    F['latin'], F['ea'] = R['fonts']['latin'], R['fonts']['ea'] or R['fonts']['latin']
    eqrender.configure(cfg['math'].get('font', 'sans'), cfg['math'].get('preamble', ''), R['colors']['text'])
    if cfg['math'].get('plugin'):
        try: PLUGIN = load_plugin(cfg['math']['plugin'])
        except Exception as e: PLUGIN_WHY = f'math.plugin を読めない: {str(e).splitlines()[0][:60]}'
    if cfg['math'].get('pptx', 'office') != 'office': OFFICE_WHY = 'math.pptx が image'
    elif not omml.available(): OFFICE_WHY = 'pandoc が無い'
    else: OFFICE = True

    prs = Presentation(cfg['master'])
    for s in list(prs.slides._sldIdLst):                     # マスターのファイルに入っているスライドは外す
        prs.part.drop_rel(s.rId); prs.slides._sldIdLst.remove(s)
    layout = next(l for l in prs.slide_layouts if l.name == R['layout'])
    cover_layout = next((l for l in prs.slide_layouts if l.name == R['cover_layout']), None) if R['cover_layout'] else None
    dv = R['footer'].get('date_value')                         # footer.date_value があれば，その日に固定する
    d = datetime.date.fromisoformat(dv) if dv else datetime.date.today()
    today = {'ymd': f'{d.year}/{d.month}/{d.day}', 'iso': d.isoformat()}.get(R['footer'].get('date_format'), f'{d:%B} {d.day}, {d.year}')
    stats = {'plugin': 0, 'office': 0, 'image': [], 'slide': 0, 'custom': 0, 'sizes': set(), 'over': []}
    with sync_playwright() as pw:
        try: br = pw.chromium.launch(channel='chrome', headless=True)
        except Exception: br = pw.chromium.launch(headless=True)       # Chrome が無ければ Playwright の Chromium
        page = br.new_page(viewport={'width': int(R['W']), 'height': int(R['H'])}, device_scale_factor=3)
        page.goto('file://' + str(Path(html).resolve()) + '?export=pptx')
        page.wait_for_load_state('load'); time.sleep(5)       # 自動縮小（fitSlides）が終わるのを待つ
        data = page.evaluate((HERE / 'extract_layout.js').read_text(encoding='utf-8'))
        for n, sd in enumerate(data, 1):
            stats['slide'] = n
            if sd.get('over'): stats['over'].append((n, sd['over']))
            if sd.get('cover') and cover_layout is not None:    # 表紙: マスターのタイトルとサブタイトルに文字だけ入れる（色・大きさはマスターのまま）
                slide = prs.slides.add_slide(cover_layout)
                keep_placeholders(slide, {'ctrTitle', 'title', 'subTitle'})
                for ph in slide.placeholders:
                    t = ph._element.find('.//' + qn('p:ph')).get('type', 'body')
                    ph.text = '\v'.join(sd['title'] if t in ('ctrTitle', 'title') else sd['sub'])   # \v は段落の中の改行
                add_footer(slide, R, R['cover_layout'], today)
                continue
            slide = prs.slides.add_slide(layout)
            keep_placeholders(slide, {'title'})
            if slide.shapes.title is not None: slide.shapes.title.text = sd['title']
            ctx = Ctx(slide, page, stats, R); ctx.sc = sd['scale']
            for it in sd['items']:
                PUT[it['type']](ctx, it)
            place_math(ctx)
            add_footer(slide, R, R['layout'], today)
        br.close()
    prs.save(out)
    print(f"{Path(out).name}: {len(data)} 枚 / パワポの数式 {stats['office']}，式の画像 {len(stats['image'])}" + (f"，プラグインで置いた式 {stats['plugin']}" if PLUGIN else ''))
    for s, why, tex in stats['image'][:20]:
        print(f'  画像にした式: {s} 枚目  [{why}]  {tex}')
    for s, o in stats['over']:
        print(f'  はみ出し: {s} 枚目（{o}px．中身を縮めて入れてある．枚を分けるか文を短くする）')
    if cfg['sizes_pt'].get('strict', True):
        tiers = {round(v * 4 / 3, 1) for v in R['sizes'].values()}
        other = sorted(v for v in stats['sizes'] if all(abs(v - t) > 0.6 for t in tiers))
        if other: print('  段の外の文字の大きさ（px）:', ', '.join('%g' % v for v in other[:12]))

if __name__ == '__main__':
    main()
