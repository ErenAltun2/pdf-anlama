from pathlib import Path

import fitz

T = Path("data/test")
T.mkdir(parents=True, exist_ok=True)

# 1) bozuk PDF
(T / "bozuk.pdf").write_bytes(b"bu bir pdf degil")

# 2) tablosuz, yalnızca düz metin
d = fitz.open()
p = d.new_page()
for i in range(10):
    p.insert_text((72, 72 + i * 20), "Bu sayfada yalnizca duz metin var, tablo veya formul yok.")
d.save(T / "tablosuz.pdf")

# 3) fotoğraflı (metin yok, sadece görsel)
d = fitz.open()
p = d.new_page()
p.insert_image(fitz.Rect(72, 72, 400, 300), filename="outputs/crops/1602.03837/p3_fig_2.png")
d.save(T / "fotografli.pdf")

print("Hazır:", [f.name for f in T.glob("*.pdf")])