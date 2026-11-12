import os
from dotenv import load_dotenv

load_dotenv()
prov = os.getenv("VLM_PROVIDER", "gemini")

if prov == "gemini":
    from google import genai
    c = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    r = c.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        contents="Sadece 'calisiyor' yaz.")
    print(r.text)
else:
    import ollama
    r = ollama.chat(model=os.getenv("OLLAMA_MODEL"),
        messages=[{"role": "user", "content": "Sadece 'calisiyor' yaz."}])
    print(r["message"]["content"])