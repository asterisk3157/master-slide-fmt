"""
README のスクリーンショットを作る（見本のプロファイルと見本の資料だけを使う．個人のプロファイルは使わない）．

使い方: uv run --with playwright --with pymupdf --with pillow python docs/make_images.py
  1. 見本の資料を全部作る（examples/decks/build_all.sh）
  2. 研究の見本（research）を 4 つの形でも作る（tools/try_profiles.sh．出力は一時フォルダ）
  3. docs/images/ に置く:
       preview.png  … HTML のプレビュー（ブラウザで開いたところ）
       pdf.png / pptx.png … 研究の見本の全部の枚（PDF / パワポを LibreOffice で表示）
       profiles.png … 同じ src を 4 つの形で作ったもの
       decks.png / decks_casual.png … 見本の資料ごとの表紙と 2 枚（研究・勉強・技術の資料 / それ以外の資料）
"""
import io, os, subprocess, tempfile
from pathlib import Path
import pymupdf
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DECKS = ROOT / 'examples' / 'decks'
OUT = ROOT / 'docs' / 'images'; OUT.mkdir(parents=True, exist_ok=True)
PROFILES = ['research-lab', 'seminar-4x3', 'club', 'lt-dark']
ORDER = [('research', [1, 3]), ('seminar-bayes', [2, 3]), ('conference-co2', [2, 3]), ('lt-build', [1, 3]), ('parts', [2, 5])]
CASUAL = [('club-welcome', [1, 2]), ('travel-kyoto', [1, 3]), ('pitch-wallet', [1, 3]), ('festival-notice', [1, 2]),
          ('monthly-report', [1, 4]), ('self-intro', [1, 2])]
BG = '#2b2f38'
env = dict(os.environ, MASTER_SLIDE_PROFILES=str(ROOT / 'examples'))   # 見本のプロファイルを先に探す
tmp = Path(tempfile.mkdtemp(prefix='msf-readme-'))
subprocess.run([str(DECKS / 'build_all.sh')], check=True, env=env, stdout=subprocess.DEVNULL)
subprocess.run([str(ROOT / 'tools' / 'try_profiles.sh'), str(tmp), *PROFILES], check=True, env=env, stdout=subprocess.DEVNULL)

def font(size):
    for f in ('/System/Library/Fonts/Helvetica.ttc', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(f).exists(): return ImageFont.truetype(f, size)
    return ImageFont.load_default()

def pages(pdf, height):
    d = pymupdf.open(pdf)
    return [Image.open(io.BytesIO(p.get_pixmap(matrix=pymupdf.Matrix(height / p.rect.height, height / p.rect.height), alpha=False).tobytes('png'))).convert('RGB') for p in d]

def grid(ims, cols, gap=20):
    w, h = ims[0].size; rows = (len(ims) + cols - 1) // cols
    c = Image.new('RGB', (cols * (w + gap) + gap, rows * (h + gap) + gap), BG)
    for i, im in enumerate(ims): c.paste(im, (gap + (i % cols) * (w + gap), gap + (i // cols) * (h + gap)))
    return c

def rows(items, h, label_size=26):
    """[(ラベル, [画像…])] を 1 行ずつ並べる"""
    f = font(label_size); out = []
    for label, ims in items:
        ims = [im.resize((int(im.width * h / im.height), h)) for im in ims]
        r = Image.new('RGB', (sum(i.width for i in ims) + 20 * (len(ims) + 1), h + 60), BG); d = ImageDraw.Draw(r)
        d.text((20, 14), label, fill='#ffcc00', font=f); x = 20
        for im in ims: r.paste(im, (x, 50)); x += im.width + 20
        out.append(r)
    W = max(r.width for r in out); c = Image.new('RGB', (W, sum(r.height for r in out) + 10), BG); y = 0
    for r in out: c.paste(r, (0, y)); y += r.height
    return c

# 1. HTML のプレビュー（右上に書き出しボタン）
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome')
    pg = b.new_page(viewport={'width': 1440, 'height': 900})
    pg.goto((DECKS / 'research' / 'research.html').as_uri()); pg.wait_for_timeout(2500)
    pg.screenshot(path=str(OUT / 'preview.png'))
    b.close()

# 2. PDF とパワポの全部の枚（研究の見本）
grid(pages(DECKS / 'research' / 'research.pdf', 315), 3).save(OUT / 'pdf.png')
soffice = next((s for s in ('/Applications/LibreOffice.app/Contents/MacOS/soffice', 'soffice', 'libreoffice')
                if Path(s).exists() or subprocess.run(['which', s], capture_output=True).returncode == 0), None)
subprocess.run([soffice, '--headless', '--convert-to', 'pdf', '--outdir', str(tmp / 'pptx'), str(DECKS / 'research' / 'research.pptx')],
               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
grid(pages(tmp / 'pptx' / 'research.pdf', 315), 3).save(OUT / 'pptx.png')

# 3. 同じ src を 4 つの形で（表紙・2 枚目・4 枚目）
rows([(n, [pages(tmp / n / 'sample.pdf', 290)[i] for i in (0, 1, 3)]) for n in PROFILES], 290).save(OUT / 'profiles.png')

# 4. 見本の資料ごとに（表紙と 2 枚）．研究・勉強・技術の資料と，それ以外の資料に分ける
for out, order in (('decks.png', ORDER), ('decks_casual.png', CASUAL)):
    items = []
    for name, picks in order:
        prof = (DECKS / name / 'slides.config.json').read_text(encoding='utf-8').split('"profile"')[1].split('"')[1]
        ps = pages(DECKS / name / f'{name}.pdf', 230)
        items.append((f'{name}  ({prof})', [ps[0]] + [ps[i] for i in picks if i < len(ps)]))
    rows(items, 230, 24).save(OUT / out)
for k in ('preview', 'pdf', 'pptx', 'profiles', 'decks', 'decks_casual'): print(OUT / f'{k}.png', Image.open(OUT / f'{k}.png').size)
