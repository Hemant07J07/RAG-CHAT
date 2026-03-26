import json
import os
from pathlib import Path

import numpy as np
import requests
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "embeddinggemma")
INDEX_FILE = Path("data/index.json")


def load_index():
    if not INDEX_FILE.exists():
        return []
    return json.loads(INDEX_FILE.read_text(encoding="utf-8"))


def cosine_similarity(a, b):
    a = np.array(a, dtype=np.float32)
    b = np.array(b, dtype=np.float32)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def embed_text(text: str):
    base_url = (OLLAMA_URL or "").rstrip("/")
    if not base_url:
        raise RuntimeError("OLLAMA_URL is empty")

    attempts = []

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


def search_local_docs(query: str, top_k: int = 4):
    index = load_index()
    if not index:
        return []

    qvec = embed_text(query)
    scored = []
    for item in index:
        score = cosine_similarity(qvec, item["embedding"])
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in scored[:top_k] if score > 0]


def search_web(query: str, max_results: int = 3):
    results = []
    try:
        with DDGS() as ddgs:
            for row in ddgs.text(query, max_results=max_results):
                results.append(
                    {
                        "title": row.get("title", ""),
                        "url": row.get("href", ""),
                        "snippet": row.get("body", ""),
                    }
                )
    except Exception:
        pass
    return results
