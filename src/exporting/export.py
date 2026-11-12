import argparse
import shutil
from html.parser import HTMLParser
from pathlib import Path

from extraction.extract_table import parse_markdown_table, rows_to_csv
from models.schemas import EquationItem, FigureItem, PaperResult, TableItem

RESULTS = Path("outputs/results")
CROPS = Path("outputs/crops")


class _TabloParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self._row, self._cell, self._span = [], None, None, (1, 1)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            try:
                self._span = (int(a.get("colspan") or 1), int(a.get("rowspan") or 1))
            except ValueError:
                self._span = (1, 1)

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self._row.append(("".join(self._cell).strip(), *self._span))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


def html_to_rows(text: str) -> list[list[str]]:
    """HTML tabloyu düz satırlara çevirir; birleşik hücrelerin değerini tekrarlar."""
    p = _TabloParser()
    p.feed(text)
    grid, pending = [], {}
    for r, cells in enumerate(p.rows):
        out = []
        for val, cs, rs in cells:
            while (r, len(out)) in pending:
                out.append(pending.pop((r, len(out))))
            for _ in range(cs):
                for dr in range(1, rs):
                    pending[(r + dr, len(out))] = val
                out.append(val)
        while (r, len(out)) in pending:
            out.append(pending.pop((r, len(out))))
        grid.append(out)
    genislik = max((len(g) for g in grid), default=0)
    return [g + [""] * (genislik - len(g)) for g in grid]


def tex_blok(latex: str) -> str:
    if "\\\\" in latex and "\\begin" not in latex:
        env = "aligned" if "&" in latex else "gathered"
        return f"\\begin{{{env}}}\n{latex}\n\\end{{{env}}}"
    return latex


def export_paper(res: PaperResult, fmts: set[str]):
    out = RESULTS / res.paper_id
    out.mkdir(parents=True, exist_ok=True)

    # --- tablolar
    for t in (x for x in res.tables if x.status == "ok"):
        (out / "tables").mkdir(exist_ok=True)
        html_mi = "<table" in t.markdown.lower()
        if "md" in fmts or html_mi:  # birleşik hücreli HTML hali her zaman saklanır
            ext = "html" if html_mi else "md"
            (out / "tables" / f"{t.id}.{ext}").write_text(t.markdown, encoding="utf-8")
        if "csv" in fmts:
            rows = html_to_rows(t.markdown) if html_mi else parse_markdown_table(t.markdown)
            if rows:  # utf-8-sig: Excel Türkçe karakterleri doğru açsın
                (out / "tables" / f"{t.id}.csv").write_text(
                    rows_to_csv(rows), encoding="utf-8-sig", newline="")

    # --- formüller
    eqs = sorted((x for x in res.equations if x.status == "ok"), key=lambda x: x.sira)
    if eqs:
        (out / "equations").mkdir(exist_ok=True)
        parca = ["% Gerekli paketler: \\usepackage{amsmath,amssymb}\n"]
        for e in eqs:
            uyari = f"  % {e.warning}".replace("\n", " ") if e.warning else ""
            parca.append(f"% {e.id} (sayfa {e.page}){uyari}\n"
                         f"\\begin{{equation*}}\n{tex_blok(e.latex)}\n\\end{{equation*}}\n")
        (out / "equations" / "equations.tex").write_text("\n".join(parca), encoding="utf-8")

    # --- figürler
    for f in (x for x in res.figures if x.status == "ok"):
        (out / "figures").mkdir(exist_ok=True)
        kaynak = CROPS / res.paper_id / f"p{f.page}_{f.id}.png"
        if kaynak.exists():
            shutil.copy(kaynak, out / "figures" / f"{f.id}.png")
        metin = (f"{f.caption}\n\n" if f.caption else "") + f.description
        (out / "figures" / f"{f.id}.txt").write_text(metin, encoding="utf-8")

    # --- okuma sırasıyla tek dosya
    tum = {x.id: x for x in res.tables + res.equations + res.figures}
    md = [f"# {res.paper_id}\n"]
    md += [f"> {m}\n" for m in res.messages]
    for id_ in res.okuma_sirasi:
        x = tum.get(id_)
        if x is None or x.status != "ok":
            continue
        if isinstance(x, TableItem):
            md.append(f"**{x.caption or x.id}** *(sayfa {x.page})*\n\n{x.markdown}\n")
        elif isinstance(x, EquationItem):
            md.append(f"$$\n{tex_blok(x.latex)}\n$$ *({x.id}, sayfa {x.page})*\n")
        elif isinstance(x, FigureItem):
            md.append(f"![{x.id}](figures/{x.id}.png)\n\n**{x.caption or x.id}** "
                      f"*(sayfa {x.page})*\n\n{x.description}\n")
    (out / "makale_sirali.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("paper_id")
    ap.add_argument("--format", default="csv,md")
    a = ap.parse_args()
    jp = RESULTS / a.paper_id / "result.json"
    r = PaperResult.model_validate_json(jp.read_text(encoding="utf-8"))
    export_paper(r, {s.strip() for s in a.format.split(",")})
    print("Hazır:", RESULTS / a.paper_id)