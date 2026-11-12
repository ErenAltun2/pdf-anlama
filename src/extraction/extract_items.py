import json


def resolve(doc, ref):
    """'#/texts/3' -> ('texts', doc['texts'][3])"""
    _, kind, idx = ref.split("/")
    return kind, doc[kind][int(idx)]


def walk(doc, node, order):
    """Docling'in belge (okuma) sırasını düz bir referans listesine çevirir."""
    for ch in node.get("children", []):
        ref = ch["$ref"]
        order.append(ref)
        _, child = resolve(doc, ref)
        walk(doc, child, order)


def caption_of(doc, node):
    parts = []
    for c in node.get("captions", []):
        _, cn = resolve(doc, c["$ref"])
        parts.append(cn.get("text", ""))
    return " ".join(parts).strip()


def to_topleft(bbox, page_h):
    """Docling bbox (genelde sol-alt orijin) -> sol-üst orijin, PDF punto biriminde."""
    if bbox.get("coord_origin", "BOTTOMLEFT") == "BOTTOMLEFT":
        y0, y1 = page_h - bbox["t"], page_h - bbox["b"]
    else:
        y0, y1 = bbox["t"], bbox["b"]
    return {"x0": bbox["l"], "y0": y0, "x1": bbox["r"], "y1": y1}


def extract(json_yol):
    doc = json.loads(json_yol.read_text(encoding="utf-8"))
    order = []
    walk(doc, doc["body"], order)

    sayac = {"table": 0, "equation": 0, "figure": 0}
    prefix = {"table": "table", "equation": "eq", "figure": "fig"}
    items = []

    for ref in order:
        kind, node = resolve(doc, ref)
        if kind == "tables":
            tip = "table"
        elif kind == "pictures":
            tip = "figure"
        elif kind == "texts" and node.get("label") == "formula":
            tip = "equation"
        else:
            continue

        if not node.get("prov"):
            continue
        p = node["prov"][0]
        page = p["page_no"]
        page_h = doc["pages"][str(page)]["size"]["height"]

        sayac[tip] += 1
        items.append({
            "sira": len(items) + 1,
            "id": f"{prefix[tip]}_{sayac[tip]}",
            "tip": tip,
            "page": page,
            "bbox": to_topleft(p["bbox"], page_h),
            "caption": caption_of(doc, node) if tip != "equation" else "",
            "docling_text": node.get("text", "") if tip == "equation" else "",
        })
    return items