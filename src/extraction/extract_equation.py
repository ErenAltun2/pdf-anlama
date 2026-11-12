import re
from pathlib import Path

from integrations.vlm_client import ask

PROMPT = (
    r"Bu görüntüdeki formülü yalnızca LaTeX olarak yaz. "
    r"$ işareti, \[ \], \begin{equation} ve açıklama kullanma. "
    r"Görüntüde yazanı olduğu gibi aktar, sadeleştirme. "
    r"Denklem numarasını (\tag veya (8) gibi) ve boşluk komutlarını (\hspace, \quad) yazma. "
    r"Fonksiyon adlarını (softmax, MultiHead gibi) \text{} veya \mathrm{} ile yaz. "
    r"Sadece LaTeX kodunu yaz."
    r"Formülün yanındaki düz metin sözcükleri (where, for gibi) yazma. "
)


def clean_latex(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
    t = re.sub(r"\n?```$", "", t).strip()
    t = re.sub(r"^\\\[|\\\]$", "", t).strip()
    t = re.sub(r"^\$\$|\$\$$", "", t).strip()
    t = re.sub(r"^\$|\$$", "", t).strip()
    t = re.sub(r"\\begin\{(equation\*?)\}|\\end\{(equation\*?)\}", "", t).strip()
    t = re.sub(r"\\tag\*?\{[^}]*\}", "", t).strip()
    t = re.sub(r"\\hspace\*?\{[^}]*\}", " ", t)
    t = re.sub(r"\(\d+\)\s*$", "", t).strip()   # sondaki (8) gibi numara
    t = re.sub(r"(\\[a-zA-Z]+)(?=[A-Z])", r"\1 ", t)  # \timesD -> \times D
    t = re.sub(r"(?:\s+|\\q?quad\s*)\(\d+\)\s*$", "", t).strip()
    t = re.sub(r"^(?:where)\s+", "", t, flags=re.IGNORECASE).strip()
    return t    


def validate(latex: str) -> str | None:
    """Sorun yoksa None, varsa hata mesajı."""
    if not latex:
        return "Boş çıktı."
    if latex.count("{") != latex.count("}"):
        return "Süslü parantezler dengesiz."
    if len(re.findall(r"\\left\b", latex)) != len(re.findall(r"\\right\b", latex)):
        return r"\left ve \right sayısı eşit değil."
    if len(re.findall(r"(?<!\\)\|", latex)) % 2:
        return "Tek sayıda | (mutlak değer/norm) var."
    begins = re.findall(r"\\begin\{(\w+\*?)\}", latex)
    ends = re.findall(r"\\end\{(\w+\*?)\}", latex)
    if sorted(begins) != sorted(ends):
        return "begin/end ortamları eşleşmiyor."
    return None


def mathtext_check(latex: str) -> str | None:
    """matplotlib ile derleme denemesi. Desteklemediği komutlar olabilir,
    bu yüzden başarısızlık yalnızca uyarıdır."""
    try:
        from matplotlib.mathtext import MathTextParser
        MathTextParser("path").parse(f"${latex}$")
        return None
    except Exception as e:
        return str(e).splitlines()[0][:150]


def extract_equation(crop: Path) -> dict:
    latex = clean_latex(ask(crop, PROMPT))
    err = validate(latex)
    if err:  # 2.7: hata mesajıyla bir kez yeniden iste
        latex = clean_latex(ask(crop, PROMPT + f"\nÖnceki cevabında sorun vardı: {err} Düzelt."))
        err = validate(latex)

    warning = None
    if err:
        warning = f"düşük güvenilirlik: {err}"
    else:
        m = mathtext_check(latex)
        if m:
            warning = f"mathtext derleyemedi (yanlış olmayabilir): {m}"
    return {"status": "ok", "latex": latex, "warning": warning}


if __name__ == "__main__":
    import sys
    paper = sys.argv[1] if len(sys.argv) > 1 else "1706.03762"
    for crop in sorted(Path("outputs/crops", paper).glob("*_eq_*.png")):
        res = extract_equation(crop)
        print(f"\n{crop.name} | uyarı: {res['warning']}")
        print(res["latex"])