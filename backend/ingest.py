import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "embeddinggemma")

DOCS_DIR = Path("docs")
OUT_FILE = Path("data/index.json")


def chunk_text(text: str, max_chars: int = 700, overlap: int = 120):
    text = " ".join(text.split())
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


def embed_text(text: str):
    base_url = (OLLAMA_URL or "").rstrip("/")
    if not base_url:
        raise RuntimeError("OLLAMA_URL is empty")

    attempts = []

    # 1) Ollama newer/alternate endpoint: /api/embed
    try:
        r = requests.post(
            f"{base_url}/api/embed",
            json={"model": EMBED_MODEL, "input": text},
            timeout=120,
        )
        if r.ok:
            data = r.json()
            if isinstance(data, dict) and "embeddings" in data and data["embeddings"]:
                return data["embeddings"][0]
        attempts.append(("/api/embed", r.status_code, r.text[:300]))
    except Exception as e:
        attempts.append(("/api/embed", "error", str(e)[:300]))

    # 2) Ollama classic endpoint: /api/embeddings
    try:
        r = requests.post(
            f"{base_url}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
            timeout=120,
        )
        if r.ok:
            data = r.json()
            if isinstance(data, dict) and "embedding" in data:
                return data["embedding"]
        attempts.append(("/api/embeddings", r.status_code, r.text[:300]))
    except Exception as e:
        attempts.append(("/api/embeddings", "error", str(e)[:300]))

    # 3) OpenAI-compatible endpoint (Ollama supports this on some versions): /v1/embeddings
    try:
        r = requests.post(
            f"{base_url}/v1/embeddings",
            json={"model": EMBED_MODEL, "input": text},
            timeout=120,
        )
        if r.ok:
            data = r.json()
            if (
                isinstance(data, dict)
                and isinstance(data.get("data"), list)
                and data["data"]
                and isinstance(data["data"][0], dict)
                and "embedding" in data["data"][0]
            ):
                return data["data"][0]["embedding"]
        attempts.append(("/v1/embeddings", r.status_code, r.text[:300]))
    except Exception as e:
        attempts.append(("/v1/embeddings", "error", str(e)[:300]))

    detail = "\n".join([f"- {p}: {code} {msg}" for p, code, msg in attempts])
    raise RuntimeError(
        "Failed to get embeddings from the configured server. "
        "Tried /api/embed, /api/embeddings, and /v1/embeddings.\n" + detail
    )


def main():
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    items = []
    for path in DOCS_DIR.glob("**/*"):
        if path.suffix.lower() not in {".txt", ".md"}:
            continue

        raw = path.read_text(encoding="utf-8", errors="ignore")
        for i, chunk in enumerate(chunk_text(raw)):
            items.append(
                {
                    "id": f"{path.stem}-{i}",
                    "source": str(path),
                    "chunk": chunk,
                    "embedding": embed_text(chunk),
                }
            )

    OUT_FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")
    print(f"Saved {len(items)} chunks to {OUT_FILE}")


if __name__ == "__main__":
    main()