import requests
from ai_chat_bot.core.config import OLLAMA_URL, OLLAMA_MODEL

def _list_models() -> list[str]:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=15)
        r.raise_for_status()
        data = r.json()
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []

def chat(user_text: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": user_text,
        "stream": False,
    }

    r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=120)

    # Ollama may return 404 with JSON error for missing model
    if r.status_code >= 400:
        try:
            err = r.json().get("error", r.text)
        except Exception:
            err = r.text

        if "model" in str(err).lower() and "not found" in str(err).lower():
            models = _list_models()
            if models:
                return f"Model '{OLLAMA_MODEL}' not found. Available: {', '.join(models)}"
            return f"Model '{OLLAMA_MODEL}' not found. (No model list available.)"

        return f"Ollama error {r.status_code}: {err}"

    data = r.json()
    text = (data.get("response", "") or "").strip()
    return text or "(no response from model)"
