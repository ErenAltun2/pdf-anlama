import time
from pathlib import Path

from integrations.vlm_client import ask

crop = sorted(Path("outputs/crops/1602.03837").glob("*.png"))[4]
print("Görüntü:", crop)

prompt = "Bu görüntüde ne var? Tek cümleyle yaz."

t = time.time()
print("1. çağrı:", ask(crop, prompt))
print(f"  süre: {time.time() - t:.1f} sn")

t = time.time()
print("2. çağrı:", ask(crop, prompt))
print(f"  süre: {time.time() - t:.2f} sn")