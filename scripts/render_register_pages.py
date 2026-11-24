"""Render stock-register PDF pages to PNG for visual cross-checking."""
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT.parent / "Electronics Stock Register.pdf"
OUT = ROOT / "stock_register_pages"
OUT.mkdir(exist_ok=True)

doc = pymupdf.open(SRC)
for i, page in enumerate(doc):
    pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
    target = OUT / f"page-{i + 1:02d}.png"
    pix.save(target)
    print(target.name, pix.width, pix.height)
