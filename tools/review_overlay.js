// review_overlay.js — review.py が資料（<名前>.html）に差し込む部品．窓（review_shell.html）の iframe の中で動く
//   範囲を選ぶと「コメント」のボタン，枚に乗ると「この枚にコメント」のボタンを出し，押されたら窓に知らせる
//   窓から受け取ったコメントの選んだ文を，CSS Highlight で塗る（資料の DOM は変えない）
//   読み直しの前後で，今見ている枚と位置を窓に預けて戻す
(() => {
  if (window.parent === window) return;                  // 窓の外で開いたときは何もしない
  const post = m => window.parent.postMessage(Object.assign({ from: 'msf-review' }, m), '*');
  const slides = () => [...document.querySelectorAll('section.slide')];
  const info = sl => {
    const i = slides().indexOf(sl);
    const h = sl.querySelector('h2') || sl.querySelector('.cover-title');
    return { slide: sl.id || '', index: i + 1, title: h ? h.textContent.trim().replace(/\s+/g, ' ') : '' };
  };
  // 選んだ所の要素を，枚から見た CSS の道筋で書く（#s6 > h2:nth-of-type(1) のように）
  function pathOf(el, sl) {
    const parts = [];
    for (let e = el; e && e !== sl; e = e.parentElement) {
      const tag = e.tagName.toLowerCase();
      const sib = [...e.parentElement.children].filter(c => c.tagName === e.tagName);
      parts.unshift(sib.length > 1 ? `${tag}:nth-of-type(${sib.indexOf(e) + 1})` : tag);
    }
    return (sl.id ? '#' + sl.id : 'section.slide') + (parts.length ? ' > ' + parts.join(' > ') : '');
  }

  const css = document.createElement('style');
  css.textContent = `
    ::highlight(msf-review) { background: rgba(255, 196, 0, .45); }
    ::highlight(msf-review-on) { background: rgba(255, 120, 0, .6); }
    .msf-rv-btn { position: fixed; z-index: 2147483000; font: 600 13px/1 -apple-system, 'Hiragino Sans', sans-serif;
      padding: 7px 11px; border: 0; border-radius: 6px; background: #1f6feb; color: #fff; cursor: pointer;
      box-shadow: 0 2px 8px rgba(0,0,0,.3); display: none; }
    .msf-rv-btn.msf-rv-whole { background: rgba(31,111,235,.85); font-weight: 500; }
    .msf-rv-flash { outline: 4px solid #1f6feb !important; outline-offset: 2px; transition: outline-color 1.2s; }
    /* 窓では資料の頭の見出し・書き出しボタン・トップへ戻るを出さない（書き出しはコメントの欄の上にある） */
    body > header, #export, #top { display: none !important; }`;
  document.head.appendChild(css);
  const mk = (cls, label) => { const b = document.createElement('button'); b.className = 'msf-rv-btn ' + cls; b.textContent = label; document.body.appendChild(b); return b; };
  const selBtn = mk('', 'コメント');
  const slideBtn = mk('msf-rv-whole', 'この枚にコメント');

  // ---- 範囲を選んだとき ----
  let pick = null;
  function onSelect() {
    const s = window.getSelection();
    selBtn.style.display = 'none'; pick = null;
    if (!s || s.isCollapsed || !s.rangeCount) return;
    const r = s.getRangeAt(0);
    const node = n => (n.nodeType === 1 ? n : n.parentElement);
    const sl = node(r.startContainer).closest('section.slide');
    if (!sl || sl !== node(r.endContainer).closest('section.slide')) return;
    const quote = s.toString().replace(/\s+/g, ' ').trim();
    if (!quote) return;
    pick = Object.assign(info(sl), { quote, path: pathOf(node(r.commonAncestorContainer), sl) });
    const rc = r.getBoundingClientRect();
    selBtn.style.left = Math.min(innerWidth - 90, rc.right) + 'px';
    selBtn.style.top = Math.min(innerHeight - 36, rc.bottom + 6) + 'px';
    selBtn.style.display = 'block';
  }
  document.addEventListener('mouseup', () => setTimeout(onSelect, 0));
  document.addEventListener('keyup', e => { if (e.shiftKey) onSelect(); });
  selBtn.addEventListener('mousedown', e => e.preventDefault());   // 押しても選択を消さない
  selBtn.addEventListener('click', () => { if (pick) post(Object.assign({ type: 'compose' }, pick)); selBtn.style.display = 'none'; });

  // ---- 枚ごとのコメント（枚に乗ると右上にボタン） ----
  let hover = null;
  document.addEventListener('mousemove', e => {
    const sl = e.target.closest && e.target.closest('section.slide');
    if (e.target === slideBtn) return;
    hover = sl;
    if (!sl) { slideBtn.style.display = 'none'; return; }
    const rc = sl.getBoundingClientRect();
    slideBtn.style.left = (rc.right - 130) + 'px';
    slideBtn.style.top = Math.max(4, rc.top + 6) + 'px';
    slideBtn.style.display = 'block';
  });
  slideBtn.addEventListener('click', () => { if (hover) post(Object.assign({ type: 'compose', quote: '', path: hover.id ? '#' + hover.id : '' }, info(hover))); });

  // ---- 選んだ文を塗る（空白を無視して枚の文から探す） ----
  function rangeOf(sl, quote) {
    const want = quote.replace(/\s+/g, '');
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
  let threads = [];
  function paint(active) {
    if (!window.CSS || !CSS.highlights) return;
    const all = new Highlight(), on = new Highlight();
    for (const t of threads) {
      if (t.state !== 'open' || !t.quote) continue;
      const sl = t.slide ? document.getElementById(t.slide) : slides()[t.index - 1];
      const r = sl && rangeOf(sl, t.quote);
      if (r) (t.id === active ? on : all).add(r);
    }
    CSS.highlights.set('msf-review', all);
    CSS.highlights.set('msf-review-on', on);
  }

  // ---- 今見ている位置を窓に預ける・戻す ----
  function where() {
    const ss = slides();
    const sl = ss.find(s => s.getBoundingClientRect().bottom > 40) || ss[0];
    if (!sl) return null;
    const rc = sl.getBoundingClientRect();
    return { slide: sl.id, index: ss.indexOf(sl), offset: -rc.top / Math.max(1, rc.height) };
  }
  let tm = null;
  addEventListener('scroll', () => { clearTimeout(tm); tm = setTimeout(() => post(Object.assign({ type: 'scroll' }, where())), 200); });
  function restore(p) {
    const ss = slides();
    const sl = (p.slide && document.getElementById(p.slide)) || ss[p.index] || null;
    if (!sl) return;
    const go = () => { const rc = sl.getBoundingClientRect(); scrollBy(0, rc.top + rc.height * (p.offset || 0)); };
    go(); setTimeout(go, 300); setTimeout(go, 1600);     // 図の縮小（runtime.js）が済んでから合わせ直す
  }
  function goto(slideId, index) {
    const sl = (slideId && document.getElementById(slideId)) || slides()[index - 1];
    if (!sl) return;
    sl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    sl.classList.add('msf-rv-flash');
    setTimeout(() => sl.classList.remove('msf-rv-flash'), 1200);
  }

  addEventListener('message', e => {
    const m = e.data || {};
    if (m.from !== 'msf-review-shell') return;
    if (m.type === 'threads') { threads = m.threads || []; paint(m.active); }
    if (m.type === 'restore') restore(m);
    if (m.type === 'goto') { goto(m.slide, m.index); paint(m.active); }
  });
  post({ type: 'ready' });
})();
