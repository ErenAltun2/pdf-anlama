import hashlib
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.getenv("VLM_PROVIDER", "gemini")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5vl:3b")
MODEL_NAME = GEMINI_MODEL if PROVIDER == "gemini" else OLLAMA_MODEL

CACHE_DIR = Path("outputs/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MIN_GAP_SN = (
    float(os.getenv("VLM_MIN_GAP_SECONDS", "4.0")) if PROVIDER == "gemini" else 0.0
)
MAX_RETRY = 5
_last_call = 0.0
_client = None


def _image_bytes(image) -> bytes:
    if isinstance(image, (str, Path)):
        return Path(image).read_bytes()
    return image


def _cache_key(img: bytes, prompt: str) -> str:
    h = hashlib.sha256()
    h.update(PROVIDER.encode())
    h.update(MODEL_NAME.encode())
    h.update(prompt.encode("utf-8"))
    h.update(img)
    return h.hexdigest()


def _retryable(e: Exception) -> bool:
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    if code in (429, 500, 503, 504):
        return True
    s = str(e)
    return any(k in s for k in ("429", "503", "UNAVAILABLE", "RESOURCE_EXHAUSTED"))


def _call_gemini(img: bytes, prompt: str):
    global _client
    from google import genai
    from google.genai import types
    if _client is None:
        _client = genai.Client(
            api_key=os.environ["GEMINI_API_KEY"],
            http_options=types.HttpOptions(timeout=60_000),  # 60 sn (ms cinsinden)
        )
    r = _client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[types.Part.from_bytes(data=img, mime_type="image/png"), prompt],
    )
    return (r.text or "").strip()


def _call_ollama(img: bytes, prompt: str):
    import ollama
    r = ollama.chat(model=OLLAMA_MODEL,
                    messages=[{"role": "user", "content": prompt, "images": [img]}])
    return r["message"]["content"].strip()


def ask(image, prompt: str) -> str:
    """Görüntü (yol veya bytes) + prompt -> yanıt metni. Cache'li, yeniden denemeli."""
    global _last_call
    img = _image_bytes(image)
    key = _cache_key(img, prompt)
    cache_file = CACHE_DIR / f"{key}.json"

    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))["text"]

    for deneme in range(MAX_RETRY):
        gap = time.time() - _last_call
        if gap < MIN_GAP_SN:
            time.sleep(MIN_GAP_SN - gap)
        try:
            if PROVIDER == "gemini":
                text = _call_gemini(img, prompt)
            else:
                text = _call_ollama(img, prompt)
            _last_call = time.time()
            cache_file.write_text(json.dumps(
                {"text": text, "model": MODEL_NAME}, ensure_ascii=False), encoding="utf-8")
            return text
        except Exception as e:
            _last_call = time.time()
            if _retryable(e) and deneme < MAX_RETRY - 1:
                bekle = 10 * (2 ** deneme)   # 10, 20, 40, 80 sn
                print(f"  [vlm] geçici hata ({type(e).__name__}), {bekle} sn sonra tekrar...")
                time.sleep(bekle)
                continue
            raise