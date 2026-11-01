"""
PDF の全部の枚を 1 枚の画像に並べる（直したあとに全部の枚を目で確かめるため）．

使い方: uv run --with pymupdf --with pillow python contact_sheet.py <名前>.pdf <出力.png> [列の数=4] [1 枚の幅 px=480]
"""
import io, sys
import pymupdf
from PIL import Image, ImageDraw

pdf, out = sys.argv[1], sys.argv[2]
cols = int(sys.argv[3]) if len(sys.argv) > 3 else 4
tw = int(sys.argv[4]) if len(sys.argv) > 4 else 480
doc = pymupdf.open(pdf)
pages = []
for p in doc:
    z = tw / p.rect.width
    pages.append(Image.open(io.BytesIO(p.get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=False).tobytes('png'))).convert('RGB'))
th = max(im.height for im in pages); gap = 24
rows = (len(pages) + cols - 1) // cols
sheet = Image.new('RGB', (cols * (tw + gap) + gap, rows * (th + gap) + gap), '#2f3b52')
d = ImageDraw.Draw(sheet)
for i, im in enumerate(pages):
    x, y = gap + (i % cols) * (tw + gap), gap + (i // cols) * (th + gap)
    sheet.paste(im, (x, y)); d.text((x + 4, y - 16), str(i + 1), fill='#ffffff')
sheet.save(out); print(f'{out}: {len(pages)} 枚')
