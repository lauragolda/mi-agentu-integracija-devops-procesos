import requests, json, time

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:3b"

def ask_ollama(prompt, system=""):
    start = time.time()
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"temperature": 0.1}
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
        resp.raise_for_status()
        text = resp.json().get("response", "").strip()
    except Exception as e:
        text = f"ERROR: {e}"
    elapsed = time.time() - start
    return text, round(elapsed, 3)

def parse_json_response(text):
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except:
        pass
    return {"raw": text}