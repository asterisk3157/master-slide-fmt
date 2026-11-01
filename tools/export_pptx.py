"""
予備: PDF の各ページを画像にして，マスターの上に 1 枚ずつ貼ったパワポを作る（編集できる版が作れなかったときだけ使う）．
スライドの中身は画像なので，パワポ上で文字や式は編集できない．

使い方: uv run --with python-pptx --with pymupdf python export_pptx.py <名前>.pdf <出力.pptx> <master.pptx> [レイアウト名]
"""
import io, sys
import fitz                                   # pymupdf
from pptx import Presentation

src, out, master = sys.argv[1], sys.argv[2], sys.argv[3]
lname = sys.argv[4] if len(sys.argv) > 4 else None
prs = Presentation(master)
for s in list(prs.slides._sldIdLst):          # マスターに入っているスライドは外す
    prs.part.drop_rel(s.rId); prs.slides._sldIdLst.remove(s)
lay = next((l for l in prs.slide_layouts if l.name == lname), prs.slide_layouts[len(prs.slide_layouts) - 1])
W, H = prs.slide_width, prs.slide_height
doc = fitz.open(src)
for page in doc:
    s = prs.slides.add_slide(lay)
    for ph in list(s.placeholders): ph._element.getparent().remove(ph._element)
    z = 2000 / page.rect.width
    png = page.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False).tobytes('png')
    s.shapes.add_picture(io.BytesIO(png), 0, 0, W, H)
prs.save(out); print('saved', out, len(doc), '枚（中身は画像）')
