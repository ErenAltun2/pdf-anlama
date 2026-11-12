from pathlib import Path

import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[2]
CROP_DIR = ROOT / "outputs" / "crops"
DPI = 150
PAD = 6  # kenarlardan pay (PDF punto)


def crop_paper(pdf_path: Path, items: list) -> int:
    if not pdf_path.is_absolute():
        pdf_path = ROOT / pdf_path
    out = CROP_DIR / pdf_path.stem
    out.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    n = 0
    for it in items:
        try:
            page = doc[it["page"] - 1]
            b = it["bbox"]
            rect = fitz.Rect(b["x0"] - PAD, b["y0"] - PAD,
                             b["x1"] + PAD, b["y1"] + PAD) & page.rect
            if rect.is_empty or rect.width < 5 or rect.height < 5:
                continue
            pix = page.get_pixmap(dpi=DPI, clip=rect)
            pix.save(out / f"p{it['page']}_{it['id']}.png")
            n += 1
        except Exception as e:
            print(f"  {it['id']}: kırpma hatası -> {e}")
    doc.close()
    return n