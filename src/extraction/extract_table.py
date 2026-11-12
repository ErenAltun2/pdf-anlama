import csv
import io
import re
from pathlib import Path

from integrations.vlm_client import ask

PROMPT = (
    "Bu görüntüdeki tabloyu Markdown tablo olarak ver. "
    "Metinleri görüntüde yazdığı gibi bırak, çevirme. "
    "Görüntüde olmayan başlık satırı veya sütun ekleme. "
    "Hücrelerdeki matematik ifadelerini Excel'de okunabilir sade metin olarak yaz: "
    "LaTeX komutları, ters eğik çizgi ve $ sınırlayıcıları kullanma; alt simgelerde "
    "mümkünse Unicode karakterleri kullan. Örneğin b_t yerine bₜ, 115\\text{ px} "
    "yerine 115 px yaz. Birleşik hücre varsa HTML tablo kullan. Sadece tabloyu yaz."
)


def clean_output(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


def parse_markdown_table(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(rows) <= 1 and all(re.fullmatch(r":?-+:?", c) for c in cells):
            continue  # ayraç satırı (yalnızca başlığın hemen altında)
        if not any(cells):
            continue  # tamamen boş satır (başlıksız tabloda sahte başlık)
        rows.append(cells)
    return rows


def validate(rows: list[list[str]]) -> str | None:
    """Sorun yoksa None, varsa hata mesajı döner."""
    if not rows:
        return "Hiç satır ayrıştırılamadı."
    widths = {len(r) for r in rows}
    if len(widths) > 1:
        return f"Satırların sütun sayısı eşit değil: {sorted(widths)}"
    return None


def extract_table(crop: Path) -> dict:
    raw = clean_output(ask(crop, PROMPT))
    if "<table" in raw.lower():
        return {"status": "ok", "markdown": raw, "rows": None,
                "warning": "HTML tablo; CSV dönüşümü 2.10'da yapılacak"}

    rows = parse_markdown_table(raw)
    err = validate(rows)
    if err:  # 2.7: hata mesajıyla bir kez yeniden iste
        retry_prompt = PROMPT + f"\nÖnceki cevabında sorun vardı: {err} Düzelt."
        raw = clean_output(ask(crop, retry_prompt))
        rows = parse_markdown_table(raw)
        err = validate(rows)

    return {
        "status": "ok",
        "markdown": raw,
        "rows": rows,
        "warning": f"düşük güvenilirlik: {err}" if err else None,
    }


def rows_to_csv(rows: list[list[str]], delimiter: str = ",") -> str:
    buf = io.StringIO()
    csv.writer(buf, delimiter=delimiter).writerows(rows)
    return buf.getvalue()


_GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ",
    "epsilon": "ε", "theta": "θ", "lambda": "λ", "mu": "μ",
    "pi": "π", "sigma": "σ", "phi": "φ", "psi": "ψ", "omega": "ω",
}
_SUBSCRIPT = str.maketrans({
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎",
    "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ",
    "k": "ₖ", "l": "ₗ", "m": "ₘ", "n": "ₙ", "o": "ₒ",
    "p": "ₚ", "r": "ᵣ", "s": "ₛ", "t": "ₜ", "u": "ᵤ",
    "v": "ᵥ", "x": "ₓ",
})
_SUBSCRIPT_CHARS = "0123456789+-=()aehijklmnoprstuvx"


def readable_cell(value: str) -> str:
    """Turn common inline LaTeX in table cells into spreadsheet-friendly text."""
    text = value.replace(r"\_", "\uFFF0")
    text = re.sub(r"\\(?:text|mathrm|operatorname)\{([^{}]*)\}", r"\1", text)
    text = re.sub(
        r"\\dot\{([^{}]*)\}",
        lambda match: match.group(1) + "\u0307",
        text,
    )
    text = re.sub(r"\\([A-Za-z]+)", lambda match: _GREEK.get(match.group(1), match.group(1)), text)
    text = text.replace("$", "")
    text = re.sub(r"\\[,;!]", " ", text)
    text = re.sub(r"\\(?:quad|qquad)\b", " ", text)
    text = re.sub(
        r"_\{([^{}]+)\}",
        lambda match: (
            match.group(1).translate(_SUBSCRIPT)
            if len(match.group(1)) == 1 and match.group(1) in _SUBSCRIPT_CHARS
            else f"_({match.group(1)})"
        ),
        text,
    )
    text = re.sub(r"(?<!\\)_([A-Za-z0-9])\b", lambda match: match.group(1).translate(_SUBSCRIPT), text)
    text = re.sub(r"_([A-Za-z][A-Za-z0-9]*)", r"_(\1)", text)
    text = re.sub(r"\\([{}])", r"\1", text)
    text = text.replace("{", "").replace("}", "")
    text = text.replace("\uFFF0", "_")
    return re.sub(r"\s+", " ", text).strip()


def readable_rows(rows: list[list[str]]) -> list[list[str]]:
    return [[readable_cell(cell) for cell in row] for row in rows]


if __name__ == "__main__":
    import sys
    paper = sys.argv[1] if len(sys.argv) > 1 else "1602.03837"
    for crop in sorted(Path("outputs/crops", paper).glob("*table*.png")):
        res = extract_table(crop)
        print("\n", crop.name, "| uyarı:", res["warning"])
        print(res["markdown"])
        if res["rows"]:
            print("\nCSV önizleme:\n" + rows_to_csv(res["rows"]))