// build が HTML の最後に埋め込むスクリプト．飾り・見出し・本文の領域・脚注は build が HTML に書き込んであるので，
// ここでは「開いた日の日付」「書き出しのときの見た目」「画面の幅に合わせた縮小」「はみ出したときの図の縮小」だけを行う
// （スクリプトが動かない表示でも，体裁は崩れない）
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
  document.querySelectorAll('section.slide > .foot .date').forEach(e => { e.textContent = today; });

  // はみ出したら図を小さくする．文字は縮めない．それでも入らない枚は data-over を付けて中身を縮める
  const slides = [...document.querySelectorAll('section.slide')];
  function fitSlides() {
    document.querySelector('main').style.zoom = EXPORT ? 1 : Math.min(1, (document.documentElement.clientWidth - 32) / DATA.W);
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

  window.addEventListener('load', () => { fitSlides(); setTimeout(fitSlides, 1500); setTimeout(fitSlides, 4000); });
  window.addEventListener('resize', fitSlides);
  fitSlides();
})();
