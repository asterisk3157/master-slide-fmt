// review_overlay.js — review.py が資料（<名前>.html）に差し込む部品．資料の上でコメントを書き，AI に送る
//   要素に乗ると枠で塗られ，押すとその要素への吹き出しが出る．文を選んで「コメント」を押してもよい
//   書いたコメントは要素の右上にピン（番号）で出る．ピンを押すと，やりとり・続き・解決の吹き出しが出る
//   下のツールバー: 下書きをまとめて送信，前・次のコメント，コメントの入・切，解決済みの表示，コピーして貼る（AI に届かないとき），PDF・パワポ
//   資料が build されると読み直す（見ていた枚と位置は保つ．書きかけがあるときは閉じるまで待つ）
//   資料の DOM は変えない（枠・ピン・吹き出しは body の上に重ねるだけ．選んだ文は CSS Highlight で塗る）
(() => {
  const NAME = (document.currentScript && document.currentScript.dataset.name) || document.title;
  const KEY = s => `msf-rv-${s}-${NAME}`;
  const ls = { get: (k, d) => { try { const v = localStorage.getItem(KEY(k)); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
               set: (k, v) => { try { localStorage.setItem(KEY(k), JSON.stringify(v)); } catch (e) {} } };
  const api = (path, body) => fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {})
    .then(r => r.ok ? r.json() : r.text().then(t => { throw new Error(t); }));
  const h = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const slides = () => [...document.querySelectorAll('section.slide')];
  const UI = '.msf-rv';                                  // 重ねた部品（これの上ではコメントの操作をしない）

  // ---------- 見た目 ----------
  const css = h('style');
  css.textContent = `
    body > header, #export, #top { display: none !important; }
    ::highlight(msf-rv) { background: rgba(255, 196, 0, .4); }
    ::highlight(msf-rv-on) { background: rgba(255, 140, 0, .55); }
    .msf-rv { font: 13px/1.5 -apple-system, 'Hiragino Sans', 'Segoe UI', sans-serif; color: #1f2328; letter-spacing: 0; text-align: left; }
    .msf-rv button { font: inherit; font-size: 12px; padding: 4px 10px; border: 1px solid #d0d7de; border-radius: 6px; background: #f6f8fa; color: #1f2328; cursor: pointer; }
    .msf-rv button.pri { background: #1f6feb; border-color: #1f6feb; color: #fff; font-weight: 600; }
    .msf-rv button.lnk { border: 0; background: none; color: #1f6feb; padding: 2px 4px; }
    .msf-rv-hl { position: absolute; z-index: 2147482000; pointer-events: none; border: 2px solid #1f6feb; border-radius: 4px;
                 background: rgba(31,111,235,.06); display: none; }
    .msf-rv-hl.on { border-color: #ff8c00; background: rgba(255,140,0,.08); display: block; }
    .msf-rv-sel { position: absolute; z-index: 2147483000; display: none; }
    .msf-rv-pin { position: absolute; z-index: 2147482500; width: 20px; height: 20px; margin: -10px 0 0 -10px; border-radius: 10px 10px 10px 2px;
                  border: 2px solid #fff; box-sizing: border-box; cursor: pointer; box-shadow: 0 1px 4px rgba(0,0,0,.35); }
    .msf-rv-pin.draft { background: #9a6700; } .msf-rv-pin.sent { background: #1f6feb; } .msf-rv-pin.work { background: #8250df; }
    .msf-rv-pin.ai { background: #1a7f37; } .msf-rv-pin.done { background: #8c959f; }
    .msf-rv-pin.new::after { content: ''; position: absolute; right: -3px; top: -3px; width: 9px; height: 9px; border-radius: 5px; background: #cf222e; border: 2px solid #fff; }
    .msf-rv-pop { position: absolute; z-index: 2147483200; width: 330px; max-width: calc(100vw - 24px); box-sizing: border-box; background: #fff;
                  border: 1px solid #d0d7de; border-radius: 10px; box-shadow: 0 8px 28px rgba(0,0,0,.28); padding: 10px 12px; }
    .msf-rv-pop .where { font-size: 11px; color: #59636e; display: flex; justify-content: space-between; gap: 8px; align-items: baseline; }
    .msf-rv-pop .where > span:first-child { flex: 1; }
    .msf-rv-pop .x { cursor: pointer; font-size: 16px; line-height: 1; color: #59636e; }
    .msf-rv-pop blockquote { margin: 6px 0; padding: 3px 8px; border-left: 3px solid #e3b341; background: #fff8e1; max-height: 4.6em; overflow: auto; font-size: 12px; }
    .msf-rv-pop .el { margin: 6px 0; font-size: 11px; color: #59636e; font-family: ui-monospace, Menlo, monospace; word-break: break-all; }
    .msf-rv-pop .msgs { max-height: 40vh; overflow: auto; }
    .msf-rv-pop .msg { margin: 6px 0 0; padding: 6px 8px; border-radius: 6px; background: #f6f8fa; white-space: pre-wrap; word-break: break-word; }
    .msf-rv-pop .msg.ai { background: #eef8f0; border-left: 3px solid #1a7f37; }
    .msf-rv-pop .who { display: block; font-size: 11px; color: #59636e; }
    .msf-rv-pop textarea { width: 100%; box-sizing: border-box; min-height: 64px; margin-top: 8px; resize: vertical; font: inherit; padding: 6px 8px;
                           border: 1px solid #d0d7de; border-radius: 6px; }
    .msf-rv-pop .row { display: flex; gap: 6px; margin-top: 6px; flex-wrap: wrap; align-items: center; }
    .msf-rv-pop .tag { font-size: 11px; font-weight: 600; padding: 0 7px; border-radius: 9px; color: #fff; }
    .msf-rv-bar { position: fixed; z-index: 2147483300; left: 50%; bottom: 14px; transform: translateX(-50%); display: flex; gap: 6px; align-items: center;
                  background: #24292f; color: #fff; padding: 6px 8px 6px 12px; border-radius: 999px; box-shadow: 0 4px 16px rgba(0,0,0,.35); white-space: nowrap;
                  max-width: calc(100vw - 16px); overflow-x: auto; box-sizing: border-box; }
    .msf-rv-bar button { background: #32383f; border-color: #444c56; color: #fff; padding: 3px 9px; }
    .msf-rv-bar button.pri { background: #1f6feb; border-color: #1f6feb; }
    .msf-rv-bar button.off { color: #8c959f; }
    .msf-rv-bar a { color: #9ecbff; text-decoration: none; font-size: 12px; }
    .msf-rv-bar .dot { width: 8px; height: 8px; border-radius: 4px; background: #3fb950; flex: none; }
    .msf-rv-bar .dot.off { background: #f85149; }
    .msf-rv-bar .sep { width: 1px; height: 16px; background: #444c56; flex: none; }
    .msf-rv-toast { position: fixed; z-index: 2147483400; left: 50%; bottom: 58px; transform: translateX(-50%); background: #24292f; color: #fff;
                    padding: 6px 12px; border-radius: 6px; opacity: 0; transition: opacity .3s; pointer-events: none; }
    .msf-rv-toast.on { opacity: .92; }`;
  document.head.appendChild(css);

  const hl = h('div', 'msf-rv msf-rv-hl'); document.body.appendChild(hl);
  const selBtn = h('div', 'msf-rv msf-rv-sel'); const sb = h('button', 'pri', 'コメント'); selBtn.appendChild(sb); document.body.appendChild(selBtn);
  const toastEl = h('div', 'msf-rv msf-rv-toast'); document.body.appendChild(toastEl);
  const toast = t => { toastEl.textContent = t; toastEl.classList.add('on'); clearTimeout(toast.t); toast.t = setTimeout(() => toastEl.classList.remove('on'), 2200); };

  // ---------- 何を指しているか ----------
  const BLOCK = 'li, p, h2, h3, td, th, img, svg, table, blockquote, .box, .cap, .refs, .cover-title, .cover-sub, .figcap';
  function pickEl(t) {                                   // 乗った所の要素（文の段落・図・表・枠．無ければ枚）
    const sl = t.closest && t.closest('section.slide');
    if (!sl) return null;
    const el = t.closest(BLOCK);
    return el && sl.contains(el) ? el : sl;
  }
  const info = sl => {
    const hh = sl.querySelector('h2') || sl.querySelector('.cover-title');
    return { slide: sl.id || '', index: slides().indexOf(sl) + 1, title: hh ? hh.textContent.trim().replace(/\s+/g, ' ') : '' };
  };
  function pathOf(el, sl) {                              // 枚から見た CSS の道筋（#s6 > h2 のように）
    const parts = [];
    for (let e = el; e && e !== sl; e = e.parentElement) {
      const tag = e.tagName.toLowerCase();
      const sib = [...e.parentElement.children].filter(c => c.tagName === e.tagName);
      parts.unshift(sib.length > 1 ? `${tag}:nth-of-type(${sib.indexOf(e) + 1})` : tag);
    }
    return (sl.id ? '#' + sl.id : 'section.slide') + (parts.length ? ' > ' + parts.join(' > ') : '');
  }
  const label = el => {
    if (el.matches('section.slide')) return '枚ごと';
    if (el.matches('img, svg')) return '図';
    if (el.matches('table, td, th')) return '表';
    if (el.matches('h2, .cover-title')) return '見出し';
    if (el.matches('.box')) return '枠・式';
    const t = el.textContent.trim().replace(/\s+/g, ' ');
    return t.length > 30 ? t.slice(0, 30) + '…' : t;
  };
  function rangeOf(sl, quote) {                          // 選んだ文を，空白を無視して枚の文から探す
    const want = (quote || '').replace(/\s+/g, '');
    if (!want) return null;
    const map = []; let text = '';
    const w = document.createTreeWalker(sl, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) {
      const v = n.nodeValue;
      for (let i = 0; i < v.length; i++) if (!/\s/.test(v[i])) { map.push([n, i]); text += v[i]; }
    }
    const k = text.indexOf(want);
    if (k < 0) return null;
    const r = document.createRange();
    r.setStart(map[k][0], map[k][1]);
    const [en, ei] = map[k + want.length - 1];
    r.setEnd(en, ei + 1);
    return r;
  }
  function anchorOf(t) {                                 // コメントの付いた所 {sl, el, range, rect}
    const sl = (t.slide && document.getElementById(t.slide)) || slides()[t.index - 1];
    if (!sl) return null;
    let el = null;
    try { el = t.path ? document.querySelector(t.path) : null; } catch (e) {}
    if (!el || !sl.contains(el)) el = sl;
    const range = t.quote ? rangeOf(sl, t.quote) : null;
    const rects = range ? [...range.getClientRects()] : [];
    const rect = rects.length ? rects[rects.length - 1] : el.getBoundingClientRect();
    return { sl, el, range, rect };
  }
  const docRect = r => ({ left: r.left + scrollX, top: r.top + scrollY, right: r.right + scrollX, bottom: r.bottom + scrollY, width: r.width, height: r.height });

  // ---------- 状態 ----------
  let threads = [], version = 0, mode = ls.get('mode', true), showDone = ls.get('done', false), seen = ls.get('seen', {});
  let pop = null;                                        // 開いている吹き出し {kind: 'new'|'thread', id, box}
  let pendingReload = false;
  function stage(t) {
    if (t.state === 'resolved') return ['done', '解決'];
    const last = t.messages[t.messages.length - 1];
    if (!last) return ['done', ''];
    if (last.who === 'ai') return ['ai', 'AI の返信あり'];
    if (last.status === 'draft') return ['draft', '下書き'];
    if (last.status === 'sent') return ['sent', '送信済み（AI 待ち）'];
    return ['work', 'AI が対応中'];
  }
  const unseen = t => t.messages.filter(m => m.who === 'ai').length > (seen[t.id] || 0);
  const visible = () => threads.filter(t => t.state !== 'resolved' || showDone || unseen(t));
  const drafts = () => threads.reduce((n, t) => n + t.messages.filter(m => m.who === 'user' && m.status === 'draft').length, 0);

  // ---------- 要素に乗る・押す・文を選ぶ ----------
  function showBox(el) {
    const r = docRect(el.getBoundingClientRect());
    Object.assign(hl.style, { left: r.left - 3 + 'px', top: r.top - 3 + 'px', width: r.width + 6 + 'px', height: r.height + 6 + 'px', display: 'block' });
  }
  document.addEventListener('mousemove', e => {
    if (hl.classList.contains('on')) return;             // 吹き出しの所を示しているときは動かさない
    if (!mode || e.target.closest(UI)) { hl.style.display = 'none'; return; }
    const el = pickEl(e.target);
    if (!el) { hl.style.display = 'none'; return; }
    showBox(el); hl.style.display = 'block';
  });
  document.addEventListener('click', e => {
    if (e.target.closest(UI)) return;
    if (!mode) return;
    const sel = getSelection();
    if (sel && !sel.isCollapsed) return;                 // 文を選んだときは「コメント」のボタンから
    const el = pickEl(e.target);
    if (!el) { closePop(); return; }
    e.preventDefault(); e.stopPropagation();
    const sl = el.closest('section.slide');
    const pt = { left: e.clientX, right: e.clientX, top: e.clientY, bottom: e.clientY };   // 吹き出しは押した所に出す
    openNew(Object.assign(info(sl), { quote: '', path: pathOf(el, sl), what: label(el) }), el, pt);
  }, true);
  let pick = null, pickRect = null;
  function onSelect() {
    const s = getSelection();
    selBtn.style.display = 'none'; pick = null;
    if (!s || s.isCollapsed || !s.rangeCount) return;
    const r = s.getRangeAt(0);
    const node = n => (n.nodeType === 1 ? n : n.parentElement);
    const sl = node(r.startContainer).closest('section.slide');
    if (!sl || sl !== node(r.endContainer).closest('section.slide')) return;
    const quote = s.toString().replace(/\s+/g, ' ').trim();
    if (!quote) return;
    const c = node(r.commonAncestorContainer);
    const el = c === sl ? sl : (c.closest(BLOCK) || c);
    pick = Object.assign(info(sl), { quote, path: pathOf(sl.contains(el) ? el : sl, sl), what: '選んだ文' });
    pickRect = r.getBoundingClientRect();
    const rc = docRect(pickRect);
    Object.assign(selBtn.style, { left: Math.max(scrollX + 4, rc.right - 70) + 'px', top: rc.bottom + 6 + 'px', display: 'block' });
  }
  document.addEventListener('mouseup', e => { if (!e.target.closest(UI)) setTimeout(onSelect, 0); });
  sb.addEventListener('mousedown', e => e.preventDefault());   // 押しても選択を消さない
  sb.addEventListener('click', () => { if (pick) { selBtn.style.display = 'none'; openNew(pick, null, pickRect); } });

  // ---------- 吹き出し ----------
  function place(box, rect) {                            // 指す所の下（入らなければ上）に置く
    const r = docRect(rect);
    const w = box.offsetWidth, hh = box.offsetHeight;
    const left = Math.min(Math.max(scrollX + 8, r.left), scrollX + innerWidth - w - 12);
    let top = r.bottom + 8;
    if (top + hh > scrollY + innerHeight - 64 && r.top - hh - 8 > scrollY) top = r.top - hh - 8;
    Object.assign(box.style, { left: left + 'px', top: top + 'px' });
  }
  function closePop(force) {
    if (!pop) return true;
    const ta = pop.box.querySelector('textarea');
    if (!force && ta && ta.value.trim() && !confirm('書きかけのコメントを捨てる？')) return false;
    pop.box.remove(); pop = null;
    hl.classList.remove('on'); hl.style.display = 'none';
    paint();
    if (pendingReload) reloadNow();
    return true;
  }
  function header(text) {
    const w = h('div', 'where'); w.append(h('span', null, text));
    const x = h('span', 'x', '×'); x.title = '閉じる（Esc）'; x.onclick = () => closePop(); w.append(x);
    return w;
  }
  const keys = (ta, go) => { ta.onkeydown = e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) go(true); if (e.key === 'Escape') closePop(); }; };
  function openNew(target, el, rect) {
    if (!closePop()) return;
    const box = h('div', 'msf-rv msf-rv-pop');
    box.append(header(`${target.index} 枚目` + (target.title ? `「${target.title}」` : '') + '　' + (target.what || '')));
    if (target.quote) box.append(h('blockquote', null, target.quote));
    const ta = h('textarea'); ta.placeholder = 'コメント（⌘/Ctrl + Enter で送信，Esc で閉じる）';
    const row = h('div', 'row');
    const send = h('button', 'pri', '送信'), draft = h('button', null, '下書きに置く');
    row.append(send, draft);
    box.append(ta, row);
    document.body.appendChild(box);
    pop = { kind: 'new', box };
    if (el) { showBox(el); hl.classList.add('on'); }
    place(box, rect || (el || document.getElementById(target.slide) || document.body).getBoundingClientRect());
    const go = s => {
      const text = ta.value.trim(); if (!text) { ta.focus(); return; }
      api('/__review/new', Object.assign({}, target, { text, send: s })).then(r => {
        const at = box.style.cssText;                    // 送った後のやりとりの吹き出しも，同じ場所に出す
        ta.value = ''; closePop(true); toast(s ? '送信した' : '下書きに置いた');
        return load().then(() => openThread(r.id, '', at));
      }).catch(err => toast('送れなかった: ' + err.message));
    };
    send.onclick = () => go(true); draft.onclick = () => go(false); keys(ta, go);
    ta.focus({ preventScroll: true });
  }
  function openThread(id, keepText, at) {
    const t = threads.find(x => x.id === id);
    if (!t) return;
    const same = pop && pop.kind === 'thread' && pop.id === id;
    if (pop && !same && !closePop()) return;
    const old = same ? pop.box : null;
    const box = h('div', 'msf-rv msf-rv-pop');
    const [cls, lab] = stage(t);
    const where = header(`${t.index} 枚目` + (t.title ? `「${t.title}」` : ''));
    const tag = h('span', 'tag', lab);
    tag.style.background = { draft: '#9a6700', sent: '#1f6feb', work: '#8250df', ai: '#1a7f37', done: '#8c959f' }[cls];
    where.insertBefore(tag, where.lastChild);
    box.append(where);
    if (t.quote) box.append(h('blockquote', null, t.quote));
    const msgs = h('div', 'msgs');
    t.messages.forEach((m, i) => {
      const d = h('div', 'msg' + (m.who === 'ai' ? ' ai' : ''));
      d.append(h('span', 'who', (m.who === 'ai' ? 'AI' : 'あなた') + (m.status === 'draft' ? '（下書き）' : '') + '　' + (m.at || '').slice(5, 16).replace('T', ' ')),
               document.createTextNode(m.text));
      if (m.status === 'draft') {
        const del = h('button', 'lnk', '消す');
        del.onclick = () => api('/__review/edit', { id: t.id, msg: i, text: '' }).then(() => { closePop(true); load(); });
        d.append(del);
      }
      msgs.append(d);
    });
    box.append(msgs);
    const ta = h('textarea'); ta.placeholder = '続けて書く（⌘/Ctrl + Enter で送信）'; ta.value = keepText || '';
    const row = h('div', 'row');
    const send = h('button', 'pri', '送信'), draft = h('button', null, '下書きに置く');
    const res = h('button', null, t.state === 'resolved' ? '開き直す' : '解決にする');
    row.append(send, draft, res);
    box.append(ta, row);
    if (old) { box.style.cssText = old.style.cssText; old.replaceWith(box); }
    else { document.body.appendChild(box); if (at) box.style.cssText = at; }
    pop = { kind: 'thread', id, box };
    seen[t.id] = t.messages.filter(m => m.who === 'ai').length; ls.set('seen', seen);
    const a = anchorOf(t);
    if (a) {
      if (!t.quote) { showBox(a.el); hl.classList.add('on'); } else { hl.classList.remove('on'); hl.style.display = 'none'; }
      if (!old && !at) {                                 // ピンを押したときは，ピンのすぐ下に出す
        const pin = pins.find(p => p.dataset.id === t.id);
        place(box, pin ? pin.getBoundingClientRect() : a.rect);
      }
    }
    paint(t.id); renderPins();
    const go = s => {
      const v = ta.value.trim(); if (!v) { ta.focus(); return; }
      api('/__review/reply', { id: t.id, text: v, send: s }).then(() => { ta.value = ''; toast(s ? '送信した' : '下書きに置いた'); load(); })
        .catch(err => toast('送れなかった: ' + err.message));
    };
    send.onclick = () => go(true); draft.onclick = () => go(false); keys(ta, go);
    res.onclick = () => api('/__review/state', { id: t.id, state: t.state === 'resolved' ? 'open' : 'resolved' }).then(load);
  }
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && pop && !e.target.closest('textarea')) closePop(); });

  // ---------- ピンと塗り ----------
  const pins = [];
  function renderPins() {
    pins.splice(0).forEach(p => p.remove());
    const used = {};
    visible().forEach(t => {
      const a = anchorOf(t);
      if (!a) return;
      const r = docRect(a.rect);
      const k = Math.round(r.right / 24) + ':' + Math.round(r.top / 24);
      const n = used[k] = (used[k] || 0) + 1;
      const [cls, lab] = stage(t);
      const p = h('div', `msf-rv msf-rv-pin ${cls}` + (unseen(t) ? ' new' : '') + (pop && pop.id === t.id ? ' on' : ''));
      p.dataset.id = t.id; p.title = lab;
      Object.assign(p.style, { left: r.right + 6 + (n - 1) * 22 + 'px', top: r.top + 'px' });
      p.onclick = e => { e.stopPropagation(); openThread(t.id); };
      document.body.appendChild(p); pins.push(p);
    });
  }
  function paint(active) {
    if (!window.CSS || !CSS.highlights) return;
    const all = new Highlight(), on = new Highlight();
    visible().forEach(t => {
      if (!t.quote) return;
      const a = anchorOf(t);
      if (a && a.range) (t.id === active ? on : all).add(a.range);
    });
    CSS.highlights.set('msf-rv', all); CSS.highlights.set('msf-rv-on', on);
  }
  function relayout() {
    renderPins(); paint(pop && pop.id);
    if (pop && pop.kind === 'thread') { const t = threads.find(x => x.id === pop.id); const a = t && anchorOf(t); if (a && !t.quote) showBox(a.el); }
  }
  addEventListener('resize', relayout);
  [600, 1800, 4500].forEach(ms => setTimeout(relayout, ms));    // 図の縮小（runtime.js）が済んでから置き直す

  // ---------- 下のツールバー ----------
  const bar = h('div', 'msf-rv msf-rv-bar');
  const dot = h('span', 'dot'), stat = h('span', null, '');
  const sendAll = h('button', 'pri', '');
  const prev = h('button', null, '‹'), next = h('button', null, '›'), cnt = h('span', null, '');
  const modeB = h('button', null, ''), doneB = h('button', null, '');
  const copy = h('button', null, 'コピー'); copy.title = 'AI に届かないときは，これでコピーしてチャットに貼る';
  const pdf = h('a', null, 'PDF'); pdf.href = NAME + '.pdf'; pdf.target = '_blank';
  const ppt = h('a', null, 'パワポ'); ppt.href = NAME + '.pptx'; ppt.download = '';
  prev.title = '前のコメント'; next.title = '次のコメント';
  bar.append(dot, stat, sendAll, h('span', 'sep'), prev, cnt, next, h('span', 'sep'), modeB, doneB, copy, h('span', 'sep'), pdf, ppt);
  document.body.appendChild(bar);
  function renderBar() {
    const d = drafts();
    sendAll.style.display = d ? '' : 'none'; sendAll.textContent = `下書きを送信（${d}）`;
    cnt.textContent = `${threads.filter(t => t.state !== 'resolved').length} 件`;
    modeB.textContent = mode ? 'コメント：入' : 'コメント：切'; modeB.className = mode ? '' : 'off';
    modeB.title = '入のとき，要素に乗ると塗られ，押すと吹き出しが出る（C キーでも切り替え）';
    doneB.textContent = showDone ? '解決済み：出す' : '解決済み：隠す';
  }
  sendAll.onclick = () => api('/__review/send', {}).then(() => { toast('下書きを送信した'); load(); });
  copy.onclick = () => api('/__review/copy', {}).then(r => {
    if (!r.text) { toast('送るコメントが無い'); return; }
    navigator.clipboard.writeText(r.text).then(() => toast('コピーした．チャットに貼る'), () => prompt('コピーしてチャットに貼る', r.text));
    load();
  });
  const setMode = v => { mode = v; ls.set('mode', v); if (!v && !hl.classList.contains('on')) hl.style.display = 'none'; renderBar(); };
  modeB.onclick = () => setMode(!mode);
  doneB.onclick = () => { showDone = !showDone; ls.set('done', showDone); renderBar(); relayout(); };
  document.addEventListener('keydown', e => {
    if (e.target.closest('textarea, input') || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === 'c' || e.key === 'C') setMode(!mode);
  });
  function step(dir) {
    const vs = visible().sort((a, b) => (a.index - b.index) || a.id.localeCompare(b.id, undefined, { numeric: true }));
    if (!vs.length) return;
    let i = pop && pop.kind === 'thread' ? vs.findIndex(t => t.id === pop.id) : (dir > 0 ? -1 : 0);
    i = (i + dir + vs.length) % vs.length;
    const t = vs[i];
    if (!closePop()) return;
    const a = anchorOf(t);
    if (a) a.el.scrollIntoView({ block: 'center' });
    setTimeout(() => openThread(t.id), 60);
  }
  prev.onclick = () => step(-1); next.onclick = () => step(1);

  // ---------- サーバーとのやりとり ----------
  function load() {
    return api('/__review/state').then(s => {
      threads = s.threads;
      if (version && s.version !== version) { reloadSoon(); return; }
      version = s.version;
      renderBar(); relayout();
      if (pop && pop.kind === 'thread') { const ta = pop.box.querySelector('textarea'); openThread(pop.id, ta ? ta.value : ''); }
    });
  }
  function reloadNow() {
    const ss = slides(); const sl = ss.find(s => s.getBoundingClientRect().bottom > 40) || ss[0];
    if (sl) {
      const rc = sl.getBoundingClientRect();
      try { sessionStorage.setItem(KEY('pos'), JSON.stringify({ i: ss.indexOf(sl), off: -rc.top / Math.max(1, rc.height), open: pop && pop.kind === 'thread' ? pop.id : null })); } catch (e) {}
    }
    location.reload();
  }
  function reloadSoon() {
    const ta = pop && pop.box.querySelector('textarea');
    if (ta && ta.value.trim()) { pendingReload = true; toast('資料が更新された．書きかけを閉じると読み直す'); return; }
    reloadNow();
  }
  function restore() {
    let p = null;
    try { p = JSON.parse(sessionStorage.getItem(KEY('pos')) || 'null'); sessionStorage.removeItem(KEY('pos')); } catch (e) {}
    if (!p) return;
    const sl = slides()[p.i];
    if (!sl) return;
    const go = () => { const rc = sl.getBoundingClientRect(); scrollBy(0, rc.top + rc.height * (p.off || 0)); };
    go(); setTimeout(go, 300);
    setTimeout(() => { go(); relayout(); if (p.open) openThread(p.open); toast('資料を読み直した'); }, 1600);
  }
  function connect() {
    const es = new EventSource('/__review/events');
    es.onopen = () => { dot.className = 'dot'; stat.textContent = ''; bar.title = 'review.py とつながっている．build すると自動で読み直す'; };
    es.addEventListener('html', () => load());
    es.addEventListener('comments', () => load());
    es.onerror = () => { dot.className = 'dot off'; stat.textContent = '切れた'; bar.title = 'review.py のサーバーとつながっていない（review.py open で開き直す）'; };
  }
  renderBar();
  load().then(() => { restore(); connect(); }).catch(() => { dot.className = 'dot off'; stat.textContent = 'サーバー無し'; });
})();
