import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
PDF_DIR = ROOT / "data" / "pdf"
LATEX_DIR = ROOT / "data" / "latex"
PDF_DIR.mkdir(parents=True, exist_ok=True)
LATEX_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "pdf-anlama-ogrenci-projesi/1.0"}
BEKLEME = 3  # arXiv nazik kullanim kurali

# Sabit ID'ler: 8 makine ogrenmesi + 4 fizik
SABIT = [
    ("1706.03762", "ml"), ("1810.04805", "ml"), ("1512.03385", "ml"),
    ("2010.11929", "ml"), ("1907.11692", "ml"), ("2106.09685", "ml"),
    ("1412.6980", "ml"), ("2005.14165", "ml"),
    ("1207.7214", "fizik"), ("1602.03837", "fizik"),
    ("1207.7235", "fizik"), ("1807.06209", "fizik"),
]

# API ile secilecekler: (kategori, adet, grup)
KATEGORILER = [
    ("q-bio.GN", 2, "biyoloji"), ("q-bio.PE", 2, "biyoloji"),
    ("math.OC", 2, "matematik"), ("math.NA", 2, "matematik"),
]


def api_idleri(kategori, adet):
    url = "https://export.arxiv.org/api/query"
    params = {
        "search_query": f"cat:{kategori}",
        "start": 0,
        "max_results": adet,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    r = requests.get(url, params=params, headers=HEADERS, timeout=60)
    r.raise_for_status()
    ns = {"a": "http://www.w3.org/2005/Atom"}
    idler = []
    for e in ET.fromstring(r.text).findall("a:entry", ns):
        tam = e.find("a:id", ns).text  # http://arxiv.org/abs/2401.12345v2
        arx_id = tam.split("/abs/")[-1]
        if "v" in arx_id.split(".")[-1]:
            arx_id = arx_id.rsplit("v", 1)[0]
        idler.append(arx_id)
    return idler


def indir(url, hedef, pdf_mi):
    if hedef.exists() and hedef.stat().st_size > 0:
        return "var"
    for deneme in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=120)
            if r.status_code == 200 and len(r.content) > 1000:
                if pdf_mi and not r.content.startswith(b"%PDF"):
                    return "pdf-degil"
                hedef.write_bytes(r.content)
                return "ok"
            time.sleep(BEKLEME * (deneme + 2))
        except requests.RequestException:
            time.sleep(BEKLEME * (deneme + 2))
    return "hata"


def main():
    liste = list(SABIT)
    for kat, adet, grup in KATEGORILER:
        print(f"API: {kat} icin {adet} makale araniyor...")
        for arx_id in api_idleri(kat, adet):
            liste.append((arx_id, grup))
        time.sleep(BEKLEME)

    print(f"\nToplam {len(liste)} makale indirilecek.\n")
    for i, (arx_id, grup) in enumerate(liste, 1):
        dosya_adi = arx_id.replace("/", "_")
        p = indir(f"https://arxiv.org/pdf/{arx_id}", PDF_DIR / f"{dosya_adi}.pdf", True)
        time.sleep(BEKLEME)
        l = indir(f"https://arxiv.org/e-print/{arx_id}", LATEX_DIR / f"{dosya_adi}.tar.gz", False)
        time.sleep(BEKLEME)
        print(f"[{i}/{len(liste)}] {arx_id} ({grup})  pdf: {p}  latex: {l}")

    print("\nBitti. PDF sayisi:", len(list(PDF_DIR.glob('*.pdf'))),
          "| LaTeX arsiv sayisi:", len(list(LATEX_DIR.glob('*.tar.gz'))))


if __name__ == "__main__":
    main()