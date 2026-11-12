import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from integrations.docling_client import convert_pdf

PDF_DIR = ROOT / "data" / "pdf"
OUT_DIR = ROOT / "outputs" / "baseline"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    pdfler = sorted(PDF_DIR.glob("*.pdf"))
    if "--tek" in sys.argv:
        pdfler = pdfler[:1]  # sadece ilk PDF ile dene
    print(f"{len(pdfler)} PDF islenecek. Ilk calistirmada Docling modelleri indirir, bekle.\n")

    for i, pdf in enumerate(pdfler, 1):
        json_yol = OUT_DIR / f"{pdf.stem}.json"
        if json_yol.exists():
            print(f"[{i}/{len(pdfler)}] {pdf.name}: zaten var, atlandi")
            continue
        t0 = time.time()
        try:
            doc, docling_device = convert_pdf(pdf)
            json_yol.write_text(
                json.dumps(doc.export_to_dict(), ensure_ascii=False), encoding="utf-8")
            sure = time.time() - t0
            print(
                f"[{i}/{len(pdfler)}] {pdf.name}: Docling {docling_device} "
                f"({sure:.1f} sn)"
            )
        except Exception as e:
            sure = time.time() - t0
            print(f"[{i}/{len(pdfler)}] {pdf.name}: HATA -> {e}")
            traceback.print_exc()

    print("\nBitti.")


if __name__ == "__main__":
    main()