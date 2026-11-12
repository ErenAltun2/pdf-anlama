from pathlib import Path
from extraction import extract_table as et

cases = {
    "normal":       ("| Model | Acc |\n|---|---|\n| BERT | 91.2 |", 2),
    "kod_blogu":    ("```markdown\n| A | B |\n|---|---|\n| 1 | 2 |\n```", 2),
    "tek_tire":     ("| A | B |\n|-|-|\n| 1 | 2 |", 2),
    "bos_baslik":   ("| | |\n|---|---|\n| x | 1 |", 1),
    "eksik_deger":  ("| A | B |\n|---|---|\n| 1 | 2 |\n| - | - |", 3),
}
for name, (text, expected) in cases.items():
    rows = et.parse_markdown_table(et.clean_output(text))
    print("PASS" if len(rows) == expected else "FAIL", name, len(rows), "satır")

# 2.7 testi: bozuk çıktı verince döngü yakalıyor mu?
bozuk = "| A | B |\n|---|---|\n| 1 | 2 | 3 |"
duzgun = "| A | B |\n|---|---|\n| 1 | 2 |"
calls = []
def sahte_ask(img, prompt):
    calls.append(prompt)
    return bozuk if len(calls) == 1 else duzgun
et.ask = sahte_ask
res = et.extract_table(Path("x.png"))
print("PASS" if len(calls) == 2 and res["warning"] is None else "FAIL", "yeniden deneme")