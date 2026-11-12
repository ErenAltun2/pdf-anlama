import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
pid = sys.argv[1] if len(sys.argv) > 1 else "1602.03837"
r = json.loads((ROOT / "outputs" / "results" / pid / "result.json").read_text(encoding="utf-8"))

tum = {x["id"]: x for k in ("tables", "equations", "figures") for x in r[k]}
for i, id_ in enumerate(r["okuma_sirasi"], 1):
    x = tum[id_]
    kisa = (x.get("caption") or x.get("latex") or "")[:60].replace("\n", " ")
    print(f"{i:2}. sayfa {x['page']:>2} | {id_:9} | {x['status']:7} | {kisa}")