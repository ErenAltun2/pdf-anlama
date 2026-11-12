import argparse
import json
import time
from pathlib import Path
from typing import Callable

import pymupdf as fitz  # PyMuPDF

from cropping.crop_items import crop_paper
from extraction.describe_figure import describe_figure
from exporting.export import export_paper
from extraction.extract_equation import extract_equation
from extraction.extract_items import extract as extract_items
from extraction.extract_table import extract_table
from models.schemas import BBox, EquationItem, FigureItem, PaperResult, TableItem
from integrations.docling_client import convert_pdf as convert_with_docling
from integrations.vlm_client import MODEL_NAME

BASE = Path("outputs/baseline")
CROPS = Path("outputs/crops")
RESULTS = Path("outputs/results")

SECIM = {"tables": "table", "equations": "equation", "figures": "figure"}
TUR_ADI = {"table": "tablo", "equation": "formül", "figure": "figür"}
FORMATLAR = {"csv", "md", "json"}


class OkunamadiHatasi(Exception):
    pass


def pdf_kontrol(pdf: Path) -> list[str]:
    """Bozuk/şifreli/boş PDF'te hata fırlatır; taranmış PDF için uyarı döner."""
    notlar = []
    try:
        doc = fitz.open(pdf)
    except Exception as e:
        raise OkunamadiHatasi(f"PDF açılamadı (bozuk olabilir): {e}")
    try:
        if doc.needs_pass:
            raise OkunamadiHatasi("PDF şifreli, okunamadı.")
        if doc.page_count == 0:
            raise OkunamadiHatasi("PDF'te hiç sayfa yok.")
        n = min(3, doc.page_count)
        metin = sum(len(doc[i].get_text().strip()) for i in range(n))
        if metin < 50:
            notlar.append("Metin katmanı yok; taranmış PDF olabilir, sonuçlar düşük güvenilirlikli.")
    finally:
        doc.close()
    return notlar


def ogeleri_hazirla(
    pdf: Path,
    page_numbers: list[int] | None = None,
    on_docling_status: Callable[[str], None] | None = None,
) -> tuple[list[dict], str]:
    """Docling (yoksa çalıştır) -> öğe listesi -> kırpıntılar."""
    pid = pdf.stem
    if page_numbers is None:
        bj = BASE / f"{pid}.json"
    else:
        page_key = "_".join(str(page) for page in page_numbers)
        bj = BASE / f"{pid}_pages_{page_key}.json"
    docling_device = "Önceden kaydedilmiş Docling JSON'u kullanıldı; Docling çalışmadı"
    if not bj.exists():
        doc, docling_device = convert_with_docling(
            pdf, on_device_selected=on_docling_status
        )
        BASE.mkdir(parents=True, exist_ok=True)
        bj.write_text(json.dumps(doc.export_to_dict(), ensure_ascii=False), encoding="utf-8")
    elif on_docling_status:
        on_docling_status("Önceden kaydedilmiş Docling JSON'u kullanılıyor; Docling çalışmayacak")
    items = extract_items(bj)
    crop_paper(pdf, items)

    if page_numbers is not None:
        page_item_counts = {}
        for item in items:
            local_page = item["page"]
            if not 1 <= local_page <= len(page_numbers):
                raise ValueError(f"Docling geçersiz sayfa numarası döndürdü: {local_page}")
            original_page = page_numbers[local_page - 1]
            local_id = item["id"]
            prefix = {"table": "table", "equation": "eq", "figure": "fig"}[item["tip"]]
            key = (original_page, item["tip"])
            page_item_counts[key] = page_item_counts.get(key, 0) + 1
            item["id"] = f"{prefix}_p{original_page}_{page_item_counts[key]}"
            local_crop = CROPS / pid / f"p{local_page}_{local_id}.png"
            original_crop = CROPS / pid / f"p{original_page}_{item['id']}.png"
            if local_crop.exists() and local_crop != original_crop:
                local_crop.replace(original_crop)
            item["page"] = original_page

    return items, docling_device


def _alan(b):
    return max(0, b["x1"] - b["x0"]) * max(0, b["y1"] - b["y0"])


def _icinde(a, b) -> bool:
    """a öğesi, b'nin içinde mi kalıyor? (çok satırlı formülün parçalarını bulmak için)"""
    ab, bb = a["bbox"], b["bbox"]
    ix = max(0, min(ab["x1"], bb["x1"]) - max(ab["x0"], bb["x0"]))
    iy = max(0, min(ab["y1"], bb["y1"]) - max(ab["y0"], bb["y0"]))
    aa, ba = _alan(ab), _alan(bb)
    if aa == 0:
        return False
    return ix * iy / aa > 0.8 and (aa < ba or (aa == ba and a["sira"] > b["sira"]))


def cakisan_formuller(items: list[dict]) -> set[str]:
    eqs = [i for i in items if i["tip"] == "equation"]
    atla = set()
    for a in eqs:
        for b in eqs:
            if a is not b and a["page"] == b["page"] and _icinde(a, b):
                atla.add(a["id"])
                break
    return atla


def isle(it: dict, pid: str, atlanacak: set[str], secilen: set[str]):
    tip = it["tip"]
    sinif = {"table": TableItem, "equation": EquationItem, "figure": FigureItem}[tip]
    ortak = dict(id=it["id"], sira=it["sira"], page=it["page"], bbox=BBox(**it["bbox"]))

    if tip not in secilen:
        return sinif(**ortak, status="skipped", warning="kullanıcı bu türü seçmedi")
    if it["id"] in atlanacak:
        return sinif(**ortak, status="skipped",
                     warning="başka bir formülün içinde kalıyor (çakışan kırpıntı)")

    crop = CROPS / pid / f"p{it['page']}_{it['id']}.png"
    try:  # her öğe ayrı: biri patlarsa sıradakine geçilir
        if not crop.exists():
            raise FileNotFoundError(f"kırpıntı bulunamadı: {crop.name}")
        if tip == "table":
            r = extract_table(crop)
            return TableItem(**ortak, caption=it["caption"], markdown=r["markdown"],
                             status=r["status"], warning=r["warning"])
        if tip == "equation":
            r = extract_equation(crop)
            return EquationItem(**ortak, latex=r["latex"],
                                status=r["status"], warning=r["warning"])
        r = describe_figure(crop, it["caption"] or None)
        return FigureItem(**ortak, caption=it["caption"], description=r["description"],
                          status=r["status"], warning=r["warning"],
                          error=r["warning"] if r["status"] == "failed" else None)
    except Exception as e:
        return sinif(**ortak, status="failed", error=f"{type(e).__name__}: {e}")


def kaydet(res: PaperResult, t0: float) -> PaperResult:
    res.sure_sn = round(time.time() - t0, 1)
    out = RESULTS / res.paper_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(res.model_dump_json(indent=2), encoding="utf-8")
    return res


def processed_page_types(paper_id: str) -> dict[int, set[str]]:
    path = RESULTS / paper_id / "processed_pages.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {int(page): set(types) for page, types in data.items()}


def _merge_results(existing: PaperResult, current: PaperResult) -> PaperResult:
    for field in ("tables", "equations", "figures"):
        previous = {item.id: item for item in getattr(existing, field)}
        for item in getattr(current, field):
            old = previous.get(item.id)
            if old is None or item.status != "skipped" or old.status == "skipped":
                previous[item.id] = item
        setattr(existing, field, list(previous.values()))

    all_items = existing.tables + existing.equations + existing.figures
    ordered = sorted(all_items, key=lambda item: (item.page, item.sira, item.id))
    for index, item in enumerate(ordered, 1):
        item.sira = index
    existing.okuma_sirasi = [item.id for item in ordered]
    existing.messages = list(dict.fromkeys(existing.messages + current.messages))
    existing.sure_sn = round(existing.sure_sn + current.sure_sn, 1)
    if current.docling_device:
        existing.docling_device = current.docling_device
    if current.model:
        existing.model = current.model
    return existing


def run_paper(
    pdf: Path,
    secilen: set[str],
    fmts: set[str],
    page_numbers: list[int] | None = None,
    on_docling_status: Callable[[str], None] | None = None,
) -> PaperResult:
    t0 = time.time()
    res = PaperResult(paper_id=pdf.stem, model=MODEL_NAME)
    try:
        res.messages += pdf_kontrol(pdf)
        items, res.docling_device = ogeleri_hazirla(
            pdf, page_numbers, on_docling_status=on_docling_status
        )
    except Exception as e:
        res.messages.append(f"Okunamadı: {e}")
        if page_numbers is not None:
            result_path = RESULTS / res.paper_id / "result.json"
            if result_path.is_file():
                previous = PaperResult.model_validate_json(
                    result_path.read_text(encoding="utf-8")
                )
                res = _merge_results(previous, res)
        return kaydet(res, t0)

    atlanacak = cakisan_formuller(items)
    sonuc = [isle(it, pdf.stem, atlanacak, secilen) for it in items]

    res.tables = [x for x in sonuc if isinstance(x, TableItem)]
    res.equations = [x for x in sonuc if isinstance(x, EquationItem)]
    res.figures = [x for x in sonuc if isinstance(x, FigureItem)]
    res.okuma_sirasi = [x.id for x in sorted(sonuc, key=lambda x: x.sira)]

    for tip in sorted(secilen):
        if not any(it["tip"] == tip for it in items):
            res.messages.append(f"Bu makalede {TUR_ADI[tip]} bulunamadı.")

    page_types_path = None
    page_types_data = None
    if page_numbers is not None:
        result_path = RESULTS / res.paper_id / "result.json"
        if result_path.is_file():
            previous = PaperResult.model_validate_json(result_path.read_text(encoding="utf-8"))
            res = _merge_results(previous, res)

        page_types = processed_page_types(res.paper_id)
        for page in page_numbers:
            page_items = [item for item in sonuc if item.page == page]
            failed_types = set()
            for item in page_items:
                if item.status != "failed":
                    continue
                if isinstance(item, TableItem):
                    failed_types.add("table")
                elif isinstance(item, EquationItem):
                    failed_types.add("equation")
                elif isinstance(item, FigureItem):
                    failed_types.add("figure")
            page_types.setdefault(page, set()).update(set(secilen) - failed_types)
        page_types_path = RESULTS / res.paper_id / "processed_pages.json"
        page_types_data = json.dumps(
            {str(page): sorted(types) for page, types in sorted(page_types.items())},
            ensure_ascii=False,
            indent=2,
        )

    res = kaydet(res, t0)
    if page_types_path is not None and page_types_data is not None:
        page_types_path.write_text(
            page_types_data,
            encoding="utf-8",
        )

    try:  # dışa aktarma patlarsa sistem çökmesin, result.json zaten kayıtlı
        export_paper(res, fmts)
    except Exception as e:
        res.messages.append(f"Dışa aktarma hatası: {type(e).__name__}: {e}")
        kaydet(res, t0)
    return res


def ozet(res: PaperResult):
    tum = res.tables + res.equations + res.figures
    say = {s: sum(x.status == s for x in tum) for s in ("ok", "failed", "skipped")}
    print(f"{res.paper_id}: ok={say['ok']} failed={say['failed']} skipped={say['skipped']} "
          f"| {res.sure_sn} sn")
    if res.docling_device:
        print(f"  Docling: {res.docling_device}")
    for m in res.messages:
        print("  mesaj:", m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdfler", nargs="+")
    ap.add_argument("--extract", default="tables,equations,figures")
    ap.add_argument("--format", default="csv,md")
    ap.add_argument("--limit", type=int, default=0, help="ilk N PDF'i işle (0 = hepsi)")
    args = ap.parse_args()

    istenen = [s.strip() for s in args.extract.split(",") if s.strip()]
    bilinmeyen = [s for s in istenen if s not in SECIM]
    if bilinmeyen:
        raise SystemExit(f"Bilinmeyen tür: {bilinmeyen}. Seçenekler: {list(SECIM)}")
    secilen = {SECIM[s] for s in istenen}

    fmts = {s.strip() for s in args.format.split(",") if s.strip()}
    if fmts - FORMATLAR:
        raise SystemExit(f"Bilinmeyen format: {sorted(fmts - FORMATLAR)}. Seçenekler: {sorted(FORMATLAR)}")

    
    import glob 
    pdfler = []
    for p in args.pdfler:
        pdfler.extend(sorted(glob.glob(p)) or [p])
    if args.limit:
        pdfler = pdfler[:args.limit]

    for p in pdfler:
        try:
            ozet(run_paper(Path(p), secilen, fmts))
        except Exception as e:  # son güvenlik ağı
            print(f"{p}: beklenmeyen hata -> {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()