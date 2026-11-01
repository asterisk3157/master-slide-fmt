"""
HTML の PDF（<名前>.pdf）と，PowerPoint が書き出した PDF を同じ枚で左右に並べた画像を作る（HTML とパワポが 1 対 1 かの確認用）
使い方: uv run --with pymupdf --with pillow python compare.py <html の pdf> <PowerPoint の pdf> <出力の接頭辞> [枚の番号,...]
"""
import sys, io
import pymupdf
from PIL import Image
a, b, pre = pymupdf.open(sys.argv[1]), pymupdf.open(sys.argv[2]), sys.argv[3]
want = [int(x) for x in sys.argv[4].split(',')] if len(sys.argv) > 4 else list(range(1, len(a) + 1))
img = lambda d, i: Image.open(io.BytesIO(d[i - 1].get_pixmap(matrix=pymupdf.Matrix(640 / d[i - 1].rect.width, 640 / d[i - 1].rect.width)).tobytes('png'))).convert('RGB')
print('pages', len(a), len(b))
for k in range(0, len(want), 3):
    part = want[k:k + 3]; c = Image.new('RGB', (1290, len(part) * 490), '#2f3b52')
    for r, n in enumerate(part):
        c.paste(img(a, n), (0, r * 490)); c.paste(img(b, n), (650, r * 490))
    c.save(f'{pre}{k // 3 + 1}.png')
