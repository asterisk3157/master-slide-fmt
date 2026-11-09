// build が HTML の最後に埋め込むスクリプト．飾り・見出し・本文の領域・脚注は build が HTML に書き込んであるので，
// ここでは「開いた日の日付」「書き出しのときの見た目」「1 枚ずつの表示（めくる・枚数・一覧）」「はみ出したときの図の縮小」だけを行う
// （スクリプトが動かない表示でも，体裁は崩れない．そのときは枚を縦に並べる）
(() => {
  const DATA = JSON.parse(document.getElementById('msf-data').textContent);
  const EXPORT = new URLSearchParams(location.search).get('export');   // build が ?export=pdf / ?export=pptx を付けて開く
  if (EXPORT) document.body.classList.add('export');
  if (EXPORT === 'pptx') document.body.classList.add('nomaster');      // パワポ用: 飾りと脚注はマスターの側にあるので消す

  // 日付（開いた日）．書式は設定の footer.date_format
  const d = new Date();
  const fmt = DATA.footer.date_format;
  const today = fmt === 'ymd' ? `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
              : fmt === 'iso' ? d.toISOString().slice(0, 10)
              : d.toLocaleDateString('en-US', { month: 'long' }) + ' ' + d.getDate() + ', ' + d.getFullYear();
  // field（開いた日）のときだけ書き換える．fixed・date_value のときは build が書いた日付のまま
  if (DATA.footer.date === 'field' && !DATA.footer.date_value)
    document.querySelectorAll('section.slide > .foot .date').forEach(e => { e.textContent = today; });

  // はみ出したら図を小さくする．文字は縮めない．それでも入らない枚は data-over を付けて中身を縮める
  const slides = [...document.querySelectorAll('section.slide')];
  function fitSlides() {
    slides.forEach(sl => {
      const inner = sl.querySelector(':scope > .inner');
      if (!inner) return;
      inner.style.transform = 'none';
      const refs = sl.querySelector(':scope > .refs');
      const avail = DATA.box_h - (refs ? refs.offsetHeight + 8 : 0);
      const imgs = [...inner.querySelectorAll('img:not(.eq)')];
      imgs.forEach(im => { im.style.maxHeight = ''; });
      const used = () => inner.scrollHeight;
      let over = used() - avail;
      if (over > 0 && imgs.length) {
        imgs.forEach(im => { im.style.maxHeight = Math.max(110, im.offsetHeight - over / imgs.length - 2) + 'px'; });   // offsetHeight は main の zoom を掛ける前の高さ（getBoundingClientRect は zoom 後なので，窓の幅で図の比率が変わってしまう．11/3）
        over = used() - avail;
      }
      sl.removeAttribute('data-over');
      if (over > 0.5) { sl.setAttribute('data-over', Math.round(over)); inner.style.transform = 'scale(' + (avail / used()).toFixed(3) + ')'; }
    });
  }

  // ---------- 1 枚ずつの表示 ----------
  // マスターの大きさの枠に 1 枚だけ出し，画面に収まるように縮める．矢印キー・クリック・スワイプ・下のボタンでめくる．
  // URL の #5 で 5 枚目を開く（#s3 のように枚や要素の id でもよい）．「一覧」で全部の枚を小さく並べる．
  // 書き出し（?export=pdf / pptx）では使わない（縦に並べたまま，1 枚 1 ページで書き出す）．
  // ほかの部品（review_overlay.js）は window.msfDeck と，枚が変わったときの 'msf-slide' のイベントで合わせる
  const main = document.querySelector('main');
  let cur = 0, grid = false, nav = null;
  function layout() {
    if (!main) return;
    if (EXPORT || !nav) { main.style.zoom = EXPORT ? 1 : Math.min(1, (document.documentElement.clientWidth - 32) / DATA.W); return; }
    main.style.zoom = 1;
    const vw = document.documentElement.clientWidth, vh = document.documentElement.clientHeight;
    if (grid) {
      main.style.transform = '';
      const cols = vw < 700 ? 1 : vw < 1100 ? 2 : vw < 1600 ? 3 : 4;
      main.style.setProperty('--thumb', Math.min(0.5, (vw - 60 - 20 * (cols - 1)) / cols / DATA.W).toFixed(4));   // 60: 左右の余白とスクロールバー
      return;
    }
    const ex = document.getElementById('export');
    const exb = ex && getComputedStyle(ex).display !== 'none' ? ex.getBoundingClientRect().bottom : 0;   // 右上の書き出しボタンの下から（fixed なので offsetParent では見分けられない）
    const top = Math.max(parseFloat(getComputedStyle(document.body).paddingTop) || 0, exb) + 10;
    const bottom = nav.offsetHeight + 24;
    const s = Math.min((vw - 24) / DATA.W, (vh - top - bottom) / DATA.H);
    main.style.transform = `translate(${((vw - DATA.W * s) / 2).toFixed(1)}px, ${(top + Math.max(0, vh - top - bottom - DATA.H * s) / 2).toFixed(1)}px) scale(${s.toFixed(4)})`;
  }
  function show(i, why) {
    if (!slides.length) return;
    cur = Math.max(0, Math.min(slides.length - 1, i));
    slides.forEach((sl, k) => sl.classList.toggle('current', k === cur));
    if (nav) {
      nav.querySelector('.count').textContent = `${cur + 1} / ${slides.length}`;
      nav.querySelector('.prev').disabled = cur === 0;
      nav.querySelector('.next').disabled = cur === slides.length - 1;
    }
    if (why !== 'hash') try { history.replaceState(null, '', '#' + (cur + 1)); } catch (e) {}
    dispatchEvent(new CustomEvent('msf-slide', { detail: { index: cur } }));
  }
  function setGrid(v) {
    grid = v;
    document.body.classList.toggle('grid', v);
    if (nav) nav.querySelector('.grid').textContent = v ? '1 枚ずつ' : '一覧';
    layout();
    if (v) slides[cur].scrollIntoView({ block: 'center' }); else scrollTo(0, 0);
    dispatchEvent(new CustomEvent('msf-slide', { detail: { index: cur } }));
  }
  function fromHash() {
    const h = decodeURIComponent(location.hash.slice(1));
    if (!h) return null;
    if (/^\d+$/.test(h)) return parseInt(h, 10) - 1;
    const el = document.getElementById(h), sl = el && el.closest('section.slide');
    return sl ? slides.indexOf(sl) : null;
  }
  const typing = t => t && t.closest && t.closest('input, textarea, select, [contenteditable=""], [contenteditable="true"]');
  const reviewing = () => !!document.querySelector('.msf-rv-bar');     // レビュー画面: クリックはコメントに使う
  if (!EXPORT && main && slides.length) {
    nav = document.createElement('div'); nav.id = 'deck-nav';
    nav.innerHTML = '<button class="prev" title="前へ（←）">‹ 前へ</button><span class="count"></span><button class="next" title="次へ（→）">次へ ›</button>'
                  + '<span class="sep"></span><button class="grid" title="一覧（G）">一覧</button>';
    document.body.appendChild(nav);
    document.body.classList.add('deck');
    nav.querySelector('.prev').onclick = () => show(cur - 1);
    nav.querySelector('.next').onclick = () => show(cur + 1);
    nav.querySelector('.grid').onclick = () => setGrid(!grid);
    document.addEventListener('keydown', e => {
      if (typing(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key;
      if (k === 'g' || k === 'G') { setGrid(!grid); return; }
      if (grid) { if (k === 'Escape' || k === 'Enter') setGrid(false); return; }
      if (k === 'ArrowRight' || k === 'ArrowDown' || k === 'PageDown' || (k === ' ' && !e.shiftKey)) show(cur + 1);
      else if (k === 'ArrowLeft' || k === 'ArrowUp' || k === 'PageUp' || (k === ' ' && e.shiftKey)) show(cur - 1);
      else if (k === 'Home') show(0);
      else if (k === 'End') show(slides.length - 1);
      else return;
      e.preventDefault();
    });
    main.addEventListener('click', e => {
      const sl = e.target.closest('section.slide');
      if (!sl || e.target.closest('a, button, input, textarea, video, audio')) return;
      if (grid) { e.stopPropagation(); show(slides.indexOf(sl)); setGrid(false); return; }   // 一覧で押した枚を開く（レビュー画面のコメントは出さない）
      if (reviewing() || !getSelection().isCollapsed) return;
      const r = sl.getBoundingClientRect();
      show(cur + (e.clientX < r.left + r.width / 4 ? -1 : 1));   // 左の 4 分の 1 で前へ，ほかは次へ
    });
    let t0 = null;
    addEventListener('touchstart', e => { t0 = e.touches.length === 1 ? { x: e.touches[0].clientX, y: e.touches[0].clientY } : null; }, { passive: true });
    addEventListener('touchend', e => {
      if (!t0 || grid) return;
      const dx = e.changedTouches[0].clientX - t0.x, dy = e.changedTouches[0].clientY - t0.y; t0 = null;
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) show(cur + (dx < 0 ? 1 : -1));
    });
    addEventListener('hashchange', () => { const i = fromHash(); if (i != null && i !== cur) show(i, 'hash'); });
    const i0 = fromHash();
    show(i0 == null ? 0 : i0, 'hash');
    window.msfDeck = {
      get index() { return cur; }, get count() { return slides.length; }, get grid() { return grid; },
      go: i => { if (grid) setGrid(false); show(i); },
      shown: sl => grid || slides.indexOf(sl) === cur,              // その枚がいま画面に出ているか
      layout,
    };
  }

  // 書き出しボタン．Artifact（claude.ai のページ）の中では，ふつうのリンクでは保存できない．
  // downloads の機能で，公開用の HTML に埋め込んだ PDF・パワポを渡す（artifact_html.py が埋め込む）
  document.querySelectorAll('#export a[data-kind]').forEach(a => a.addEventListener('click', async ev => {
    if (!(window.claude && window.claude.use)) return;             // ふつうのブラウザ: リンクのまま
    ev.preventDefault();
    const dl = await window.claude.use('downloads');
    const src = document.getElementById('msf-file-' + a.dataset.kind);
    if (!dl || !src) { a.style.opacity = 0.4; return; }
    const bin = Uint8Array.from(atob(src.textContent.trim()), c => c.charCodeAt(0));
    try { await dl.save({ filename: a.getAttribute('href'), data: new Blob([bin]) }); }
    catch (e) { if (!e || e.code !== 'declined') a.style.opacity = 0.4; }   // 断られたときは何もしない
  }));

  const fit = () => { fitSlides(); layout(); };
  window.addEventListener('load', () => { fit(); setTimeout(fit, 1500); setTimeout(fit, 4000); });
  window.addEventListener('resize', fit);
  fit();
})();
