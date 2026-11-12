from pathlib import Path

from PIL import Image

from integrations.vlm_client import ask

MIN_SIDE = 80  # bunun altındaki kırpıntı figür sayılmaz (p14_fig_5 boyutuna bakıp ayarla)

PROMPT = (
    "Bu görüntü bilimsel bir makaleden kırpılmış bir figürdür. "
    "Türkçe, en fazla 4-5 cümleyle şunları anlat: "
    "1) Figürün türü (çizgi grafik, bar grafik, dağılım, şema/mimari, fotoğraf vb.). "
    "2) Grafikse eksenlerin adları ve birimleri, serilerin/çizgilerin neyi temsil ettiği. "
    "3) Ana çıkarım: figür neyi gösteriyor ya da hangi sonuca işaret ediyor. "
    "Görüntüde olmayan sayı veya bilgi uydurma; okuyamadığın yeri 'okunamadı' diye belirt. "
    "Görüntü bir figür değilse (yalnızca bir cümle, etiket, tarih, sayfa üstbilgisi, "
    "logo, süs ya da boş alan) başka hiçbir şey yazmadan yalnızca ATLA yaz."
)


def is_skip(text: str) -> bool:
    return text.lstrip(" *_`#>\"'").upper().startswith("ATLA")


def describe_figure(crop: Path, caption: str | None = None) -> dict:
    try:
        with Image.open(crop) as im:
            w, h = im.size
        if min(w, h) < MIN_SIDE:
            return {"status": "skipped", "description": "", "caption": caption,
                    "warning": f"çok küçük kırpıntı ({w}x{h}), figür değil"}

        prompt = PROMPT
        if caption:
            prompt += f"\nFigürün makaledeki başlığı (bağlam için): {caption}"
        text = ask(crop, prompt).strip()
    except Exception as e:  # tek öğe sistemi çökertmesin
        return {"status": "failed", "description": "", "caption": caption,
                "warning": f"VLM hatası: {e}"}

    if is_skip(text):
        return {"status": "skipped", "description": "", "caption": caption,
                "warning": "figür değil (süs/etiket/logo) olarak değerlendirildi"}

    warning = "düşük güvenilirlik: açıklama çok kısa" if len(text) < 30 else None
    return {"status": "ok", "description": text, "caption": caption, "warning": warning}


if __name__ == "__main__":
    import sys
    paper = sys.argv[1] if len(sys.argv) > 1 else "1602.03837"
    for crop in sorted(Path("outputs/crops", paper).glob("*fig*.png")):
        res = describe_figure(crop)
        print(f"\n{crop.name} | durum: {res['status']} | uyarı: {res['warning']}")
        print(res["description"])