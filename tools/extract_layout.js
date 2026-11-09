// スライドの HTML（?export=pptx で開いたもの）から，各要素の位置・文字・式を測って返す．
// 単位は px（スライドの左上が原点．4:3 なら 960×720，16:9 なら 1280×720）．export_pptx_editable.py が Playwright で実行する
// 飾り（.deco）と脚注（.foot）はマスターの側にあるので測らない
() => {
  const texOf = new Map();
  for (const m of (window.MathJax && MathJax.startup && MathJax.startup.document ? MathJax.startup.document.math : [])) texOf.set(m.typesetRoot, { tex: m.math, display: m.display });
  const hex = c => { const m = c.match(/\d+(\.\d+)?/g).map(Number); return m.slice(0, 3).map(v => Math.round(v).toString(16).padStart(2, '0')).join('').toUpperCase(); };
  const slides = [];
  document.querySelectorAll('section.slide').forEach((sl, si) => {
    const R = sl.getBoundingClientRect();
    const rel = r => ({ x: r.left - R.left, y: r.top - R.top, w: r.width, h: r.height });
    const inner = sl.querySelector(':scope > .inner');
    const tf = inner ? getComputedStyle(inner).transform : 'none';
    const sc = tf && tf !== 'none' ? new DOMMatrix(tf).a : 1;
    let mathId = 0;

    // 要素の中身を「行」ごとの断片（文字・式）に分ける．skip に当たる子は飛ばす（li の中の入れ子の ul）
    function lines(el, skip) {
      const frags = [];
      const walk = n => {
        if (n.nodeType === 3) {
          const cs = getComputedStyle(n.parentElement);
          const ss = n.parentElement.closest('sub, sup');                       // 上付き・下付きは，元の大きさ + 上下の指定でパワポに渡す
          const st = { color: hex(cs.color), bold: parseInt(cs.fontWeight) >= 600, italic: cs.fontStyle === 'italic',
                       mono: /monospace|Consolas|Menlo|Courier/i.test(cs.fontFamily),   // コードの等幅の字（パワポでは等幅の書体にする）
                       jp: /ゴシック|Gothic|Hiragino|Meiryo|明朝|Mincho/i.test(cs.fontFamily.split(',')[0]),   // 和文の書体を先頭に指定した字（○×△ など．パワポでも和文の書体にする）
                       script: ss ? (ss.tagName === 'SUB' ? '_' : '^') : null, fs: parseFloat(getComputedStyle(ss ? ss.parentElement : n.parentElement).fontSize) };
          const s = n.textContent;
          for (let i = 0; i < s.length; i++) {
            const rg = document.createRange(); rg.setStart(n, i); rg.setEnd(n, i + 1);
            const rs = rg.getClientRects(); if (!rs.length || rs[0].width === 0) continue;
            const ch = /[ \t\n\r]/.test(s[i]) ? ' ' : s[i];   // 全角の空白はそのまま残す
            frags.push({ t: ch, cy: rs[0].top + rs[0].height / 2, x: rs[0].left, right: rs[0].right, ...st });
          }
        } else if (n.nodeType === 1) {
          if (skip && n.matches(skip)) return;
          if (n.tagName === 'IMG' && n.classList.contains('eq')) {            // LaTeX で描いた式（build.sh が埋め込む）
            const r = n.getBoundingClientRect(); const id = 'm' + si + '_' + (mathId++); n.setAttribute('data-mid', id);
            frags.push({ math: n.dataset.tex, id, rect: rel(r), cy: r.top + r.height / 2, x: r.left, right: r.right, color: hex(getComputedStyle(n.parentElement).color), fs: parseFloat(getComputedStyle(n.parentElement).fontSize), eq: !!n.closest('.eqbody') });
            return;
          }
          if (texOf.has(n)) {
            const svg = n.querySelector('svg') || n;                       // 外枠は行の高さしか無いので，式本体（SVG）の範囲で測る
            const r = svg.getBoundingClientRect(); const cs = getComputedStyle(n);
            const id = 'm' + si + '_' + (mathId++); svg.setAttribute('data-mid', id);
            frags.push({ math: texOf.get(n).tex, id, rect: rel(r), cy: r.top + r.height / 2, x: r.left, right: r.right, color: hex(cs.color), fs: parseFloat(getComputedStyle(n.parentElement).fontSize), eq: !!n.closest('.eqbody') });
            return;
          }
          n.childNodes.forEach(walk);
        }
      };
      el.childNodes.forEach(walk);
      const lh = parseFloat(getComputedStyle(el).lineHeight) * sc || 20;
      const out = []; let cur = null;
      for (const f of frags) {
        if (!cur || f.cy > cur.cy + 0.6 * lh) { cur = { cy: f.cy, frags: [] }; out.push(cur); }
        cur.frags.push(f);
      }
      // 同じ書式の文字をまとめる．行頭・行末の空白は落とす
      return out.map(L => {
        const runs = []; let prevRight = null;
        for (const f of L.frags) {
          // 文の途中の大きな空き（flex の右寄せの式の番号など）は，パワポでも同じ幅の空白にする
          if (prevRight !== null && f.x - prevRight > f.fs * 1.2) runs.push({ gap: f.x - prevRight, x: f.x - R.left, fs: f.fs, color: f.color });
          prevRight = Math.max(prevRight === null ? f.right : prevRight, f.right);
          const last = runs[runs.length - 1];
          if (f.math !== undefined) runs.push({ math: f.math, id: f.id, rect: f.rect, color: f.color, fs: f.fs, eq: f.eq });
          else if (last && last.t !== undefined && last.color === f.color && last.bold === f.bold && last.italic === f.italic && last.script === f.script && last.fs === f.fs && last.mono === f.mono && last.jp === f.jp) last.t += f.t;
          else runs.push({ t: f.t, color: f.color, bold: f.bold, italic: f.italic, script: f.script, fs: f.fs, mono: f.mono, jp: f.jp });
        }
        if (runs.length && runs[0].t !== undefined) runs[0].t = runs[0].t.replace(/^ +/, '');
        if (runs.length && runs[runs.length - 1].t !== undefined) runs[runs.length - 1].t = runs[runs.length - 1].t.replace(/ +$/, '');
        return { y: L.cy - R.top, right: Math.max(...L.frags.map(f => f.right || 0)) - R.left, runs: runs.filter(r => r.math !== undefined || r.gap !== undefined || r.t.length) };
      }).filter(L => L.runs.length);
    }
    if (sl.classList.contains('cover')) {                                    // 表紙（マスターの表紙のレイアウトに置く）．HTML と同じ位置で改行する
      const tx = q => { const e = sl.querySelector(q); return e ? lines(e).map(L => L.runs.map(r => r.t || '').join('')) : []; };
      slides.push({ cover: true, title: tx('.cover-title'), sub: tx('.cover-sub'), scale: sc, items: [], over: 0 });
      return;
    }
    const para = (el, kind, level, skip) => {
      const cs = getComputedStyle(el);
      return { kind, level, rect: rel(el.getBoundingClientRect()), fs: parseFloat(cs.fontSize) * sc, lh: parseFloat(cs.lineHeight) * sc,
               padL: parseFloat(cs.paddingLeft) * sc, align: cs.textAlign, lines: lines(el, skip) };
    };
    const items = [];
    function block(el) {
      if (el.classList.contains('foot') || el.classList.contains('deco')) return;
      const tag = el.tagName;
      if (tag === 'H2') return;
      if (tag === 'IMG') { el.setAttribute('data-iid', 'i' + si + '_' + items.length); items.push({ type: 'img', rect: rel(el.getBoundingClientRect()), iid: el.getAttribute('data-iid') }); return; }
      if (tag === 'P') { items.push({ type: 'para', ...para(el, el.classList.contains('lead') ? 'lead' : (el.classList.contains('cap') ? 'cap' : 'plain'), 0) }); return; }
      if (tag === 'UL') {
        const paras = [];
        const li = (ul, level) => ul.querySelectorAll(':scope > li').forEach(x => { paras.push(para(x, 'li', level, 'ul')); x.querySelectorAll(':scope > ul').forEach(u => li(u, level + 1)); });
        li(el, 0); items.push({ type: 'list', rect: rel(el.getBoundingClientRect()), paras }); return;
      }
      if (tag === 'TABLE') {
        const rows = [...el.rows].map(tr => [...tr.cells].map(td => {
          const cs = getComputedStyle(td);
          return { ...para(td, 'cell', 0), th: td.tagName === 'TH', fill: hex(cs.backgroundColor), hasFill: cs.backgroundColor !== 'rgba(0, 0, 0, 0)',
                   border: parseFloat(cs.borderTopWidth) > 0, bold: parseInt(cs.fontWeight) >= 600 };
        }));
        items.push({ type: 'table', rect: rel(el.getBoundingClientRect()), rows }); return;
      }
      if (tag === 'DIV' && el.classList.contains('box')) {                   // 背景色（コードの枠など）と枠の色もパワポに渡す
        const cs = getComputedStyle(el);
        items.push({ type: 'box', ...para(el, 'box', 0), fill: hex(cs.backgroundColor), hasFill: cs.backgroundColor !== 'rgba(0, 0, 0, 0)', borderColor: hex(cs.borderTopColor) });
        return;
      }
      if (tag === 'DIV') { [...el.children].forEach(block); return; }
    }
    [...(inner || sl).children].forEach(block);
    sl.querySelectorAll(':scope > .refs').forEach(block);                   // 下端の出典（本文の領域の外に置いてある）
    const h2 = sl.querySelector(':scope > h2') || sl.querySelector('h2');
    slides.push({ title: h2 ? h2.textContent.trim() : '', scale: sc, items, over: parseInt(sl.getAttribute('data-over') || '0') });
  });
  return slides;
}
