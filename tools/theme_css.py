"""
マスターから読んだ体裁（read_master.py の JSON）と設定から，HTML の CSS と飾りを作る．

  theme(master, cfg) → {'css', 'deco': {'content', 'cover'}, 'data', 'resolved', 'warnings'}
    css      … :root の変数（大きさ・色・書体・記号）と，タイトル・本文の領域・脚注・表紙の位置
    deco     … 飾り（四角・線・画像・文字）の HTML．runtime.js が各スライドの先頭に写す
    data     … runtime.js に渡す値（脚注の名前・日付の書式）
    resolved … "auto" を解決した後の値（パワポの書き出しも同じ値を使う）
"""
import html, json

PT = 4 / 3          # 1 pt = 1.333 px（96 px/inch）
ALIGN = {'l': 'left', 'ctr': 'center', 'r': 'right', 'just': 'left', 'dist': 'center'}
JUSTIFY = {'l': 'flex-start', 'ctr': 'center', 'r': 'flex-end', 'just': 'flex-start', 'dist': 'center'}
ANCHOR = {'t': 'flex-start', 'ctr': 'center', 'b': 'flex-end'}
ASCII_BULLETS = set('–-•·»*>+')


def layout(master, name):
    for l in master['layouts']:
        if l['name'] == name: return l
    raise SystemExit('レイアウト「%s」がマスターに無い．あるもの: %s' % (name, ', '.join(l['name'] for l in master['layouts'])))

def ph(l, *types):
    for t in types:
        for p in l['placeholders']:
            if p['type'] == t and p.get('rect'): return p
    return None

def font_stack(*names, fallback=()):
    out = []
    for n in list(names) + list(fallback):
        if n and n not in out: out.append(n)
    return ', '.join(n if n in ('sans-serif', 'serif') else "'%s'" % n for n in out)

def auto(v, default): return default if v in (None, 'auto', '') else v
def hexc(c): return '#' + c.lstrip('#')
def box(r): return 'left:%.2fpx;top:%.2fpx;width:%.2fpx;height:%.2fpx;' % (r['x'], r['y'], r['w'], r['h'])


def content_box(master, l, cfg):
    """本文の領域．タイトルの下（タイトルの帯にある飾りの下）から，脚注の帯の上まで"""
    cb = cfg.get('content_box')
    if isinstance(cb, dict): return cb
    W, H = master['size']['w'], master['size']['h']
    t = ph(l, 'title')
    top = (t['rect']['y'] + t['rect']['h']) if t else H * 0.15
    x0, x1 = None, None
    for d in l['deco']:
        r = d['rect']
        if r['y'] < H * 0.3 and r['y'] + r['h'] <= H * 0.3:            # タイトルの帯にある飾り（線・帯）
            bottom = r['y'] + r['h'] + (d.get('width', 0) / 2 if d['kind'] == 'line' else 0)
            top = max(top, bottom)
            if d['kind'] == 'line' and r['w'] > W * 0.5: x0, x1 = r['x'], r['x'] + r['w']
    bottom = H
    for d in l['deco']:
        r = d['rect']
        if r['y'] > H * 0.8: bottom = min(bottom, r['y'] - (d.get('width', 0) / 2 if d['kind'] == 'line' else 0))
    for p in l['placeholders']:
        if p['type'] in ('dt', 'ftr', 'sldNum') and p.get('rect') and p['rect']['y'] > H * 0.75: bottom = min(bottom, p['rect']['y'])
    if x0 is None:
        b = ph(l, 'body', 'obj') or {'rect': master.get('master_body_rect')}
        r = b['rect'] if b and b.get('rect') else None
        if r: x0, x1 = r['x'], r['x'] + r['w']
        else: x0, x1 = W * 0.05, W * 0.95
    return {'x': round(x0, 2), 'y': round(top, 2), 'w': round(x1 - x0, 2), 'h': round(bottom - 10 - top, 2)}   # 上の空きは本文の段落の上の余白（.lead の 10px）に任せる


def text_css(st, size=None, color=None, bold=None, fallback=()):
    s = 'font-size:%.2fpx;' % ((size or st.get('size', 18)) * PT)
    s += 'font-weight:%s;' % ('bold' if (st.get('bold') if bold is None else bold) else 'normal')
    s += 'color:%s;' % hexc(color or st.get('color', '000000'))
    s += 'font-family:%s;' % font_stack(st.get('latin'), st.get('ea'), fallback=fallback)
    s += 'text-align:%s;' % ALIGN.get(st.get('algn', 'l'), 'left')
    return s

def pad_css(st):
    return 'padding:%.2fpx %.2fpx %.2fpx %.2fpx;' % (st.get('pad_t', 4.8), st.get('pad_r', 9.6), st.get('pad_b', 4.8), st.get('pad_l', 9.6))


def deco_html(items):
    out = []
    for d in items:
        r = d['rect']; rot = 'transform:rotate(%.2fdeg);' % r['rot'] if r.get('rot') else ''
        if d['kind'] == 'line':
            w = max(d['width'], 0.75)
            if r['h'] < 0.5: st = 'left:%.2fpx;top:%.2fpx;width:%.2fpx;height:%.2fpx;' % (r['x'], r['y'] - w / 2, r['w'], w)
            else: st = 'left:%.2fpx;top:%.2fpx;width:%.2fpx;height:%.2fpx;' % (r['x'] - w / 2, r['y'], w, r['h'])
            out.append('<div style="%sbackground:%s;%s"></div>' % (st, hexc(d['color']), rot))
        elif d['kind'] == 'img':
            out.append('<img alt="" style="%smargin:0;max-width:none;%s" src="data:%s;base64,%s">' % (box(r), rot, d['mime'], d['data']))
        else:
            st = box(r) + rot
            if d.get('fill'): st += 'background:%s;' % hexc(d['fill'])
            if d.get('line'): st += 'border:%.2fpx solid %s;' % (d['line_w'], hexc(d['line']))
            if d['geom'] == 'ellipse': st += 'border-radius:50%;'
            elif d['geom'] in ('roundRect', 'round2SameRect', 'round1Rect'): st += 'border-radius:%.2fpx;' % (min(r['w'], r['h']) * 0.1667)
            inner = ''
            if d.get('text'):
                ts = d['text_style']
                st += 'display:flex;flex-direction:column;justify-content:%s;%s' % (ANCHOR.get(ts.get('anchor', 'ctr'), 'center'), pad_css(ts))
                st += 'font-size:%.2fpx;font-weight:%s;color:%s;text-align:%s;line-height:1.2;' % (
                    ts.get('size', 18) * PT, 'bold' if ts.get('bold') else 'normal', hexc(ts.get('color', '000000')), ALIGN.get(ts.get('algn', 'l'), 'left'))
                inner = '<br>'.join(html.escape(t) for t in d['text'])
            out.append('<div style="%s">%s</div>' % (st, inner))
    return '\n'.join(out)


def foot_css(l, scope, fallback):
    css = []
    for typ, cls in (('dt', 'date'), ('ftr', 'ftr'), ('sldNum', 'num')):
        p = ph(l, typ)
        if not p: css.append('%s .foot .%s{display:none}' % (scope, cls)); continue
        st = p['style']
        css.append('%s .foot .%s{%s%sjustify-content:%s;padding:0 %.2fpx 0 %.2fpx;}' % (
            scope, cls, box(p['rect']), text_css(st, fallback=fallback), JUSTIFY.get(st.get('algn', 'l')), st.get('pad_r', 0), st.get('pad_l', 0)))
    return '\n'.join(css)


def theme(master, cfg):
    warn = list(master.get('warnings', []))
    W, H = master['size']['w'], master['size']['h']
    names = master['auto']
    lname = auto(cfg['layouts'].get('content'), names['content'])
    cname = auto(cfg['layouts'].get('cover'), names['cover'])
    L = layout(master, lname)
    C = layout(master, cname) if cname else None
    if C is None: warn.append('表紙のレイアウトが無いので，表紙（section.slide.cover）は本文のレイアウトで出す')
    lv = master['body_levels'] + [{}] * 3
    fb = cfg['fonts'].get('fallback', [])
    f_lat = auto(cfg['fonts'].get('latin'), lv[0].get('latin') or master['fonts']['minor']['latin'])
    f_ea = auto(cfg['fonts'].get('ea'), lv[0].get('ea') or master['fonts']['minor']['ea'])
    sz = cfg['sizes_pt']
    sizes = {'lead': float(auto(sz.get('lead'), lv[0].get('size', 28))), 'body': float(auto(sz.get('body'), lv[1].get('size', 24))),
             'sub': float(auto(sz.get('sub'), lv[2].get('size', 20))), 'small': float(auto(sz.get('small'), 12))}
    bu = cfg['bullets']
    pick = lambda v, d: d if v in (None, 'auto') else v          # "" は「記号なし」
    bullets = {'lead': pick(bu.get('lead'), lv[0].get('bullet', '•')), 'body': pick(bu.get('body'), lv[1].get('bullet', '–')),
               'sub': pick(bu.get('sub'), lv[2].get('bullet', '•'))}
    co = cfg['colors']
    text_c = auto(co.get('text'), master.get('text_color') or '000000')
    t = ph(L, 'title')
    if not t: raise SystemExit('本文のレイアウト「%s」にタイトルのプレースホルダーが無い' % lname)
    tst = dict(t['style'])
    tc = cfg.get('title', {})
    tst['size'] = float(auto(tc.get('size'), tst.get('size', 32))); tst['color'] = auto(tc.get('color'), tst.get('color', text_c))
    tst['bold'] = auto(tc.get('bold'), tst.get('bold', False))
    cb = content_box(master, L, cfg)
    bg = (L.get('background') or {})
    ftr = ph(L, 'ftr')
    footer_text = auto(cfg['footer'].get('text'), (ftr or {}).get('text', ''))

    def bw(ch, em):
        return '0em' if not ch else ('%.1fem' % em)
    v = {
        '--slide-w': '%.2fpx' % W, '--slide-h': '%.2fpx' % H,
        '--slide-bg': hexc(bg['color']) if bg.get('color') else ('url(data:%s;base64,%s) center/cover' % (bg['mime'], bg['image']) if bg.get('image') else '#fff'),
        '--font-body': font_stack(f_lat, f_ea, fallback=fb),
        '--font-title': font_stack(tst.get('latin'), tst.get('ea'), fallback=fb),
        '--fs-lead': '%.3fpx' % (sizes['lead'] * PT), '--fs-body': '%.3fpx' % (sizes['body'] * PT),
        '--fs-sub': '%.3fpx' % (sizes['sub'] * PT), '--fs-small': '%.3fpx' % (sizes['small'] * PT),
        '--bu-lead': json.dumps(bullets['lead'], ensure_ascii=False), '--bu-body': json.dumps(bullets['body'], ensure_ascii=False), '--bu-sub': json.dumps(bullets['sub'], ensure_ascii=False),
        '--bw-lead': bw(bullets['lead'], 1.5), '--bw-body': bw(bullets['body'], 1.4), '--bw-sub': bw(bullets['sub'], 1.2),
        '--c-text': hexc(text_c), '--c-good': hexc(co['good']), '--c-bad': hexc(co['bad']), '--c-th': hexc(co['table_head']),
        '--c-table-border': hexc(co['table_border']), '--c-box': hexc(co['box_border']), '--c-page': hexc(co['page_bg']),
    }
    css = [':root{' + ''.join('%s:%s;' % kv for kv in v.items()) + '}',
           '@page{size:%.2fpx %.2fpx;margin:0}' % (W, H),
           '.slide{color:var(--c-text)}',
           '.slide > h2{%s%s%salign-items:%s;justify-content:%s;}' % (box(t['rect']), text_css(tst, fallback=fb), pad_css(tst),
                                                                     ANCHOR.get(tst.get('anchor', 'ctr'), 'center'), JUSTIFY.get(tst.get('algn', 'ctr'), 'center')),
           '.slide > .inner{left:%.2fpx;top:%.2fpx;width:%.2fpx}' % (cb['x'], cb['y'], cb['w']),   # 高さは中身なり（はみ出しは runtime.js が box_h と比べる）
           '.slide > .refs{left:%.2fpx;width:%.2fpx;bottom:%.2fpx}' % (cb['x'], cb['w'], H - cb['y'] - cb['h'] - 5),   # 出典は脚注の帯のすぐ上
           foot_css(L, '.slide', fb)]
    cover = None
    if C is not None:
        ct, cs = ph(C, 'ctrTitle', 'title'), ph(C, 'subTitle', 'body')
        cbg = C.get('background') or {}
        if cbg.get('color'): css.append('.slide.cover{background:%s}' % hexc(cbg['color']))
        for p, cls in ((ct, 'cover-title'), (cs, 'cover-sub')):
            if not p: css.append('.slide.cover .%s{display:none}' % cls); continue
            st = p['style']
            css.append('.slide.cover .%s{%s%s%sjustify-content:%s;}' % (cls, box(p['rect']), text_css(st, fallback=fb), pad_css(st), ANCHOR.get(st.get('anchor', 't'), 'flex-start')))
        css.append(foot_css(C, '.slide.cover', fb))
        cover = {'layout': cname, 'title': ct['style'] if ct else None, 'sub': cs['style'] if cs else None}
    resolved = {'W': W, 'H': H, 'layout': lname, 'cover_layout': cname, 'fonts': {'latin': f_lat, 'ea': f_ea}, 'sizes': sizes,
                'bullets': bullets, 'colors': {'text': text_c, **{k: co[k] for k in ('good', 'bad', 'table_head', 'box_border')}},
                'title': tst, 'content_box': cb, 'footer': dict(cfg['footer'], text=footer_text), 'cover': cover,
                'foot_ph': {l['name']: {p['type']: p for p in l['placeholders'] if p['type'] in ('dt', 'ftr', 'sldNum')} for l in ([L] + ([C] if C else []))}}
    data = {'footer': resolved['footer'], 'W': W, 'H': H, 'box_h': cb['h']}
    return {'css': '\n'.join(css), 'deco': {'content': deco_html(L['deco']), 'cover': deco_html(C['deco']) if C else deco_html(L['deco'])},
            'data': data, 'resolved': resolved, 'warnings': warn}


def bullet_font(ch, latin, ea):
    """パワポの箇条書きの記号の書体．– • などは英字の書体，◆ ● ■ などは和文の書体"""
    return latin if ch in ASCII_BULLETS else ea
