"""
マスター（.pptx）を python-pptx で作る．手元にマスターが無いときと，公開の見本（examples/）を作るときに使う．

  --style plain     … python-pptx の素の Office テーマ（飾りなし）
  --style seminar   … 白地に左寄せの紺の見出しと細い色の線，脚注の上に細い線，表紙は左端に色の縦の帯（講義・勉強会の形）
  --style report    … 左端に紺の縦の帯，見出しの下に細い灰色の線，表紙は紺の背景に短い色の線（研究・業務の報告の形）
  --style club      … 上端に色の帯（タイトルは白），右上にロゴの画像，表紙は色の背景（サークル・イベントの形）
  --style dark      … 暗い背景に白い文字，見出しの下に短い色の線（LT・技術発表の形）
  --style conference … 上端に細い色の帯，下に薄い灰色の脚注の帯（学会発表の形）
  --style minimal   … 飾りなし，左上に細めの見出し，右下にページ番号だけ（余白の多い社内資料の形）
  --style pastel    … クリーム色の背景，見出しの下に丸い色の飾り，表紙に大小の円（旅行のしおり・案内の形）
  --style pitch     … 上端に細い紫の線，ページ番号を紫の丸の中に，表紙は紫の背景に大きな円（製品の紹介・ピッチの形）
  --style notice    … 上に緑の帯（見出しは白・中央），下に薄い緑の帯，表紙は緑の角丸の枠（地域のお知らせ・掲示の形）

使い方: uv run --with python-pptx --with pillow python make_plain_master.py <出力.pptx> [--aspect 4:3|16:9] [--style plain|seminar|report|club|dark|conference|minimal|pastel|pitch|notice]
        [--footer 'Your Name / Example Lab'] [--accent 1F4E9A]
作成者の欄（docProps）は空にする．
"""
import argparse, copy, io
from lxml import etree
from pptx import Presentation
from pptx.util import Emu

A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
NS = {'a': A, 'p': P}
IN = 914400
def qa(t): return '{%s}%s' % (A, t)
def qp(t): return '{%s}%s' % (P, t)


def scale_xfrms(el, sx):
    for x in el.iter(qa('xfrm')):
        off, ext = x.find(qa('off')), x.find(qa('ext'))
        if off is not None: off.set('x', str(int(int(off.get('x')) * sx)))
        if ext is not None: ext.set('cx', str(int(int(ext.get('cx')) * sx)))

def ph(tree, typ):
    for sp in tree.iter(qp('sp')):
        p = sp.find('.//p:nvPr/p:ph', NS)
        if p is not None and p.get('type', 'body') == typ: return sp
    return None

def set_xfrm(sp, x, y, w, h):
    sppr = sp.find(qp('spPr'))
    for old in sppr.findall(qa('xfrm')): sppr.remove(old)
    xf = etree.Element(qa('xfrm')); sppr.insert(0, xf)
    etree.SubElement(xf, qa('off'), x=str(int(x)), y=str(int(y))); etree.SubElement(xf, qa('ext'), cx=str(int(w)), cy=str(int(h)))

def set_text_style(sp, size=None, bold=None, color=None, algn=None, latin=None, ea=None, anchor=None):
    tx = sp.find(qp('txBody'))
    bp = tx.find(qa('bodyPr'))
    if anchor: bp.set('anchor', anchor)
    lst = tx.find(qa('lstStyle'))
    if lst is None: lst = etree.Element(qa('lstStyle')); tx.insert(1, lst)
    lv = lst.find(qa('lvl1pPr'))
    if lv is None: lv = etree.SubElement(lst, qa('lvl1pPr'))
    if algn: lv.set('algn', algn)
    r = lv.find(qa('defRPr'))
    if r is None: r = etree.SubElement(lv, qa('defRPr'))
    if size: r.set('sz', str(int(size * 100)))
    if bold is not None: r.set('b', '1' if bold else '0')
    if color:
        for c in r.findall(qa('solidFill')): r.remove(c)
        f = etree.Element(qa('solidFill')); etree.SubElement(f, qa('srgbClr'), val=color); r.insert(0, f)
    for k, v in (('latin', latin), ('ea', ea)):
        if v: etree.SubElement(r, qa(k), typeface=v)

def next_id(tree):
    return max(int(e.get('id')) for e in tree.iter(qp('cNvPr'))) + 1

def add_rect(tree, x, y, w, h, fill, name='帯', geom='rect', line=None, line_w=0):
    """四角（geom で楕円 ellipse・角丸 roundRect も）．fill=None で塗りなし，line で枠線"""
    fill_xml = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else '<a:noFill/>'
    line_xml = (f'<a:ln w="{int(line_w * 9525)}"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>' if line else '<a:ln><a:noFill/></a:ln>')
    sp = etree.fromstring(f'''<p:sp xmlns:p="{P}" xmlns:a="{A}"><p:nvSpPr><p:cNvPr id="{next_id(tree)}" name="{name}"/><p:cNvSpPr/><p:nvPr userDrawn="1"/></p:nvSpPr>
<p:spPr><a:xfrm><a:off x="{int(x)}" y="{int(y)}"/><a:ext cx="{int(w)}" cy="{int(h)}"/></a:xfrm><a:prstGeom prst="{geom}"><a:avLst/></a:prstGeom>
{fill_xml}{line_xml}</p:spPr></p:sp>''')
    tree.insert(2, sp)                                   # プレースホルダーより後ろ（下）に置く
    return sp

def add_line(tree, x, y, w, width_px, color, name='線'):
    sp = etree.fromstring(f'''<p:cxnSp xmlns:p="{P}" xmlns:a="{A}"><p:nvCxnSpPr><p:cNvPr id="{next_id(tree)}" name="{name}"/><p:cNvCxnSpPr/><p:nvPr userDrawn="1"/></p:nvCxnSpPr>
<p:spPr><a:xfrm><a:off x="{int(x)}" y="{int(y)}"/><a:ext cx="{int(w)}" cy="0"/></a:xfrm><a:prstGeom prst="line"><a:avLst/></a:prstGeom>
<a:ln w="{int(width_px * 9525)}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></a:ln></p:spPr></p:cxnSp>''')
    tree.insert(2, sp)

def add_pic(part, tree, png, x, y, w, h, name='ロゴ'):
    _, rid = part.get_or_add_image_part(io.BytesIO(png))
    sp = etree.fromstring(f'''<p:pic xmlns:p="{P}" xmlns:a="{A}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<p:nvPicPr><p:cNvPr id="{next_id(tree)}" name="{name}"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr userDrawn="1"/></p:nvPicPr>
<p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
<p:spPr><a:xfrm><a:off x="{int(x)}" y="{int(y)}"/><a:ext cx="{int(w)}" cy="{int(h)}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>''')
    tree.append(sp)

def set_bg(cSld, color):
    for b in cSld.findall(qp('bg')): cSld.remove(b)
    bg = etree.fromstring(f'<p:bg xmlns:p="{P}" xmlns:a="{A}"><p:bgPr><a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>')
    cSld.insert(0, bg)

def set_footer_text(tree, text):
    sp = ph(tree, 'ftr')
    if sp is None: return
    tx = sp.find(qp('txBody'))
    for p in tx.findall(qa('p')): tx.remove(p)
    p = etree.SubElement(tx, qa('p')); r = etree.SubElement(p, qa('r'))
    etree.SubElement(r, qa('rPr'), lang='en-US'); etree.SubElement(r, qa('t')).text = text

LOGO_FONTS = ['/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc', '/System/Library/Fonts/Hiragino Sans GB.ttc',
              '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', '/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc',
              'C:/Windows/Fonts/YuGothB.ttc', 'C:/Windows/Fonts/meiryob.ttc']

def logo_png(color, char='ボ'):
    """白い丸に色の縁，中に 1 文字（書体が見つからなければ三角）"""
    import os
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new('RGBA', (240, 240), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    c = tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))
    d.ellipse((8, 8, 232, 232), fill=(255, 255, 255, 255), outline=c, width=14)
    f = next((f for f in LOGO_FONTS if os.path.exists(f)), None)
    if f: d.text((120, 122), char, fill=c, font=ImageFont.truetype(f, 130), anchor='mm')
    else: d.polygon([(120, 50), (190, 175), (50, 175)], fill=c)
    b = io.BytesIO(); im.save(b, 'PNG'); return b.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out'); ap.add_argument('--aspect', default='16:9', choices=['4:3', '16:9'])
    ap.add_argument('--style', default='plain', choices=['plain', 'seminar', 'report', 'club', 'dark', 'conference', 'minimal', 'pastel', 'pitch', 'notice'])
    ap.add_argument('--footer', default=''); ap.add_argument('--accent', default=None)
    a = ap.parse_args()
    prs = Presentation()                                    # 素の Office テーマ（4:3，10 × 7.5 インチ）
    W, H = (int(10 * IN), int(7.5 * IN)) if a.aspect == '4:3' else (int(13.333 * IN), int(7.5 * IN))
    sx = W / prs.slide_width
    prs.slide_width, prs.slide_height = Emu(W), Emu(H)
    m = prs.slide_master
    mtree = m.element.find('p:cSld/p:spTree', NS)
    if sx != 1:
        scale_xfrms(m.element, sx)
        for l in prs.slide_layouts: scale_xfrms(l.element, sx)
    lay = {l.name: l for l in prs.slide_layouts}
    title_only, cover = lay['Title Only'], lay['Title Slide']
    tt = title_only.element.find('p:cSld/p:spTree', NS); ct = cover.element.find('p:cSld/p:spTree', NS)
    px = 9525
    WP, HP = W / px, H / px                                 # 大きさ（px）
    def foot(y, h, color, size=11, bold=False, left=40, right=40):
        for typ, x, w, algn in (('dt', left, 240, 'l'), ('ftr', WP / 2 - 260, 520, 'ctr'), ('sldNum', WP - right - 60, 60, 'r')):
            sp = ph(mtree, typ); set_xfrm(sp, x * px, y * px, w * px, h * px)
            set_text_style(sp, size=size, bold=bold, color=color, algn=algn, anchor='ctr')
    if a.style == 'seminar':
        acc = a.accent or '2E9C9C'
        add_line(mtree, 40 * px, 94 * px, W - 80 * px, 3, acc, '見出しの下の線')
        add_line(mtree, 40 * px, H - 36 * px, W - 80 * px, 1, 'C8C8C8', '脚注の上の線')
        foot(HP - 32, 24, '7F7F7F')
        set_xfrm(ph(tt, 'title'), 40 * px, 18 * px, W - 80 * px, 70 * px)
        set_text_style(ph(tt, 'title'), size=32, bold=True, color='1F3864', algn='l', anchor='b')
        cover.element.set('showMasterSp', '0')             # 表紙は見出しの線・脚注の線を出さない
        add_rect(ct, 0, 0, 18 * px, H, acc, '表紙の縦の帯')
        set_xfrm(ph(ct, 'ctrTitle'), 80 * px, HP * 0.30 * px, W - 160 * px, HP * 0.22 * px)
        set_text_style(ph(ct, 'ctrTitle'), size=40, bold=True, color='1F3864', algn='l', anchor='b')
        set_xfrm(ph(ct, 'subTitle'), 80 * px, HP * 0.56 * px, W - 160 * px, HP * 0.2 * px)
        set_text_style(ph(ct, 'subTitle'), size=20, bold=False, color='595959', algn='l', anchor='t')
    elif a.style == 'report':
        acc = a.accent or 'F2A33A'; navy = '1B2A4A'
        add_rect(mtree, 0, 0, 14 * px, H, navy, '左の帯')
        add_line(mtree, 48 * px, 100 * px, W - 96 * px, 1.5, 'D0D4DC', '見出しの下の線')
        foot(HP - 34, 24, '8A93A6', left=48, right=48)
        set_xfrm(ph(tt, 'title'), 48 * px, 22 * px, W - 96 * px, 74 * px)
        set_text_style(ph(tt, 'title'), size=30, bold=True, color=navy, algn='l', anchor='ctr')
        cover.element.set('showMasterSp', '0')
        set_bg(cover.element.find('p:cSld', NS), navy)
        add_rect(ct, 80 * px, HP * 0.56 * px, 120 * px, 6 * px, acc, '表紙の色の線')
        set_xfrm(ph(ct, 'ctrTitle'), 80 * px, HP * 0.28 * px, W - 160 * px, HP * 0.26 * px)
        set_text_style(ph(ct, 'ctrTitle'), size=44, bold=True, color='FFFFFF', algn='l', anchor='b')
        set_xfrm(ph(ct, 'subTitle'), 80 * px, HP * 0.61 * px, W - 160 * px, HP * 0.2 * px)
        set_text_style(ph(ct, 'subTitle'), size=20, bold=False, color='C9D3E6', algn='l', anchor='t')
    elif a.style == 'club':
        acc = a.accent or 'E8553D'
        band = 96 * px
        add_rect(mtree, 0, 0, W, band, acc, 'タイトルの帯')
        add_rect(mtree, 0, band, W, 6 * px, 'F6C343', '細い帯')
        add_rect(mtree, 0, H - 30 * px, W, 30 * px, '333333', '脚注の帯')
        add_pic(m.part, mtree, logo_png(acc), W - 86 * px, 13 * px, 70 * px, 70 * px)
        for typ, x, w, algn in (('dt', 24, 260, 'l'), ('ftr', W / px / 2 - 260, 520, 'ctr'), ('sldNum', W / px - 84, 60, 'r')):
            sp = ph(mtree, typ); set_xfrm(sp, x * px, H - 25 * px, w * px, 20 * px)
            set_text_style(sp, size=12, bold=False, color='FFFFFF', algn=algn, anchor='ctr')
        set_xfrm(ph(tt, 'title'), 40 * px, 8 * px, W - 150 * px, 80 * px)
        set_text_style(ph(tt, 'title'), size=36, bold=True, color='FFFFFF', algn='l', anchor='ctr')
        cover.element.set('showMasterSp', '0')             # 表紙はマスターの飾りを出さず，色の背景にする
        set_bg(cover.element.find('p:cSld', NS), acc)
        add_pic(cover.part, ct, logo_png(acc), W / 2 - 60 * px, 70 * px, 120 * px, 120 * px)
        set_text_style(ph(ct, 'ctrTitle'), size=48, bold=True, color='FFFFFF')
        set_text_style(ph(ct, 'subTitle'), size=24, bold=False, color='FFF4D6')
    elif a.style == 'dark':
        acc = a.accent or '5BC0EB'
        cm = m.element.find('p:clrMap', NS)                  # 文字の色（tx1）を明るい色に，背景（bg1）を暗い色にする
        cm.set('bg1', 'dk1'); cm.set('tx1', 'lt1'); cm.set('bg2', 'dk2'); cm.set('tx2', 'lt2')
        set_bg(m.element.find('p:cSld', NS), '1E2028')
        add_rect(mtree, 56 * px, 104 * px, 64 * px, 5 * px, acc, '見出しの下の短い線')
        foot(HP - 34, 24, '8A8F9C', left=56, right=56)
        set_xfrm(ph(tt, 'title'), 56 * px, 28 * px, W - 112 * px, 72 * px)
        set_text_style(ph(tt, 'title'), size=34, bold=True, color='FFFFFF', algn='l', anchor='b')
        cover.element.set('showMasterSp', '0')
        set_bg(cover.element.find('p:cSld', NS), '14161C')
        add_rect(ct, 80 * px, HP * 0.56 * px, 96 * px, 6 * px, acc, '表紙の色の線')
        set_xfrm(ph(ct, 'ctrTitle'), 80 * px, HP * 0.26 * px, W - 160 * px, HP * 0.28 * px)
        set_text_style(ph(ct, 'ctrTitle'), size=48, bold=True, color='FFFFFF', algn='l', anchor='b')
        set_xfrm(ph(ct, 'subTitle'), 80 * px, HP * 0.61 * px, W - 160 * px, HP * 0.2 * px)
        set_text_style(ph(ct, 'subTitle'), size=20, bold=False, color='A9B0C0', algn='l', anchor='t')
    elif a.style == 'conference':
        acc = a.accent or '0B6E4F'
        add_rect(mtree, 0, 0, W, 10 * px, acc, '上の帯')
        add_rect(mtree, 0, H - 34 * px, W, 34 * px, 'F2F2F2', '脚注の帯')
        add_line(mtree, 48 * px, 98 * px, W - 96 * px, 2, acc, '見出しの下の線')
        foot(HP - 29, 24, '595959', left=48, right=48)
        set_xfrm(ph(tt, 'title'), 48 * px, 22 * px, W - 96 * px, 70 * px)
        set_text_style(ph(tt, 'title'), size=32, bold=True, color='222222', algn='l', anchor='b')
        set_xfrm(ph(ct, 'ctrTitle'), 96 * px, HP * 0.22 * px, W - 192 * px, HP * 0.3 * px)
        set_text_style(ph(ct, 'ctrTitle'), size=40, bold=True, color='222222', algn='ctr', anchor='b')
        set_xfrm(ph(ct, 'subTitle'), 96 * px, HP * 0.56 * px, W - 192 * px, HP * 0.24 * px)
        set_text_style(ph(ct, 'subTitle'), size=22, bold=False, color='404040', algn='ctr', anchor='t')
    elif a.style == 'minimal':
        foot(HP - 40, 24, 'A0A0A0', left=64, right=64)
        set_xfrm(ph(tt, 'title'), 64 * px, 36 * px, W - 128 * px, 64 * px)
        set_text_style(ph(tt, 'title'), size=28, bold=False, color='333333', algn='l', anchor='b')
        set_xfrm(ph(ct, 'ctrTitle'), 64 * px, HP * 0.34 * px, W - 128 * px, HP * 0.2 * px)
        set_text_style(ph(ct, 'ctrTitle'), size=40, bold=True, color='222222', algn='l', anchor='b')
        set_xfrm(ph(ct, 'subTitle'), 64 * px, HP * 0.58 * px, W - 128 * px, HP * 0.2 * px)
        set_text_style(ph(ct, 'subTitle'), size=18, bold=False, color='808080', algn='l', anchor='t')
    elif a.style == 'pastel':
        acc = a.accent or 'F4A261'; brown = '7A4E2D'
        set_bg(m.element.find('p:cSld', NS), 'FFF8EE')
        add_rect(mtree, 56 * px, 100 * px, 90 * px, 10 * px, acc, '見出しの下の丸い飾り', geom='roundRect')
        add_rect(mtree, W - 70 * px, H - 70 * px, 40 * px, 40 * px, 'FCE1C7', '右下の円', geom='ellipse')
        foot(HP - 36, 24, 'B08968', left=56, right=80)
        set_xfrm(ph(tt, 'title'), 56 * px, 26 * px, W - 112 * px, 70 * px)
        set_text_style(ph(tt, 'title'), size=32, bold=True, color=brown, algn='l', anchor='b')
        cover.element.set('showMasterSp', '0')
        set_bg(cover.element.find('p:cSld', NS), 'FCE8D5')
        add_rect(ct, W - 300 * px, -120 * px, 420 * px, 420 * px, 'F9D3B0', '表紙の大きな円', geom='ellipse')
        add_rect(ct, 60 * px, H - 170 * px, 110 * px, 110 * px, 'F7C59F', '表紙の小さな円', geom='ellipse')
        set_xfrm(ph(ct, 'ctrTitle'), 96 * px, HP * 0.28 * px, W - 192 * px, HP * 0.26 * px)
        set_text_style(ph(ct, 'ctrTitle'), size=44, bold=True, color=brown, algn='ctr', anchor='b')
        set_xfrm(ph(ct, 'subTitle'), 96 * px, HP * 0.58 * px, W - 192 * px, HP * 0.2 * px)
        set_text_style(ph(ct, 'subTitle'), size=22, bold=False, color='9C6644', algn='ctr', anchor='t')
    elif a.style == 'pitch':
        acc = a.accent or '6C4CF1'
        add_rect(mtree, 0, 0, W, 6 * px, acc, '上の線')
        add_rect(mtree, W - 92 * px, H - 74 * px, 48 * px, 48 * px, acc, 'ページ番号の丸', geom='ellipse')
        for typ, x, w, algn in (('dt', 56, 240, 'l'), ('ftr', WP / 2 - 260, 520, 'ctr')):
            sp = ph(mtree, typ); set_xfrm(sp, x * px, H - 62 * px, w * px, 24 * px)
            set_text_style(sp, size=11, bold=False, color='8C8C9C', algn=algn, anchor='ctr')
        sp = ph(mtree, 'sldNum'); set_xfrm(sp, W - 92 * px, H - 74 * px, 48 * px, 48 * px)
        set_text_style(sp, size=14, bold=True, color='FFFFFF', algn='ctr', anchor='ctr')
        set_xfrm(ph(tt, 'title'), 56 * px, 34 * px, W - 112 * px, 72 * px)
        set_text_style(ph(tt, 'title'), size=36, bold=True, color='1A1A2E', algn='l', anchor='b')
        cover.element.set('showMasterSp', '0')
        set_bg(cover.element.find('p:cSld', NS), acc)
        add_rect(ct, W - 520 * px, H - 380 * px, 760 * px, 760 * px, '8B72F5', '表紙の大きな円', geom='ellipse')
        set_xfrm(ph(ct, 'ctrTitle'), 80 * px, HP * 0.24 * px, W * 0.62, HP * 0.3 * px)
        set_text_style(ph(ct, 'ctrTitle'), size=48, bold=True, color='FFFFFF', algn='l', anchor='b')
        set_xfrm(ph(ct, 'subTitle'), 80 * px, HP * 0.6 * px, W * 0.6, HP * 0.2 * px)
        set_text_style(ph(ct, 'subTitle'), size=22, bold=False, color='E4DCFF', algn='l', anchor='t')
    elif a.style == 'notice':
        acc = a.accent or '2E7D32'
        add_rect(mtree, 0, 0, W, 92 * px, acc, '見出しの帯')
        add_rect(mtree, 0, H - 40 * px, W, 40 * px, 'E8F5E9', '脚注の帯')
        foot(HP - 34, 28, '2E7D32', size=14, bold=True, left=24, right=24)
        set_xfrm(ph(tt, 'title'), 24 * px, 8 * px, W - 48 * px, 76 * px)
        set_text_style(ph(tt, 'title'), size=36, bold=True, color='FFFFFF', algn='ctr', anchor='ctr')
        cover.element.set('showMasterSp', '0')
        add_rect(ct, 40 * px, 40 * px, W - 80 * px, H - 80 * px, None, '表紙の枠', geom='roundRect', line=acc, line_w=8)
        add_rect(ct, 40 * px, 40 * px, W - 80 * px, 120 * px, 'E8F5E9', '表紙の上の帯', geom='rect')
        set_xfrm(ph(ct, 'ctrTitle'), 80 * px, HP * 0.3 * px, W - 160 * px, HP * 0.26 * px)
        set_text_style(ph(ct, 'ctrTitle'), size=44, bold=True, color=acc, algn='ctr', anchor='b')
        set_xfrm(ph(ct, 'subTitle'), 80 * px, HP * 0.6 * px, W - 160 * px, HP * 0.24 * px)
        set_text_style(ph(ct, 'subTitle'), size=26, bold=True, color='333333', algn='ctr', anchor='t')
    if a.footer:
        set_footer_text(mtree, a.footer)
        for l in prs.slide_layouts: set_footer_text(l.element.find('p:cSld/p:spTree', NS), a.footer)
    cp = prs.core_properties
    cp.author = ''; cp.last_modified_by = ''; cp.title = ''; cp.comments = ''
    prs.save(a.out)
    print(f'{a.out}: {a.aspect}，{a.style}')

if __name__ == '__main__':
    main()
