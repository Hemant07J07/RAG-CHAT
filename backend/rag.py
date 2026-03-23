import json
import os
from pathlib import Path

import numpy as np
import requests
from duckduckgo_search import DDGS
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "gemma3")
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


def retrieve_local(question: str, top_k: int = 4):
    index = load_index()
    if not index:
        return []

    qvec = embed_text(question)
    scored = []
    for item in index:
        score = cosine_similarity(qvec, item["embedding"])
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in scored[:top_k] if score > 0]


def search_web(question: str, max_results: int = 3):
    results = []
    try:
        with DDGS() as ddgs:
            for row in ddgs.text(question, max_results=max_results):
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


def ask_ollama(question: str, local_chunks, web_results):
    local_context = "\n\n".join(
        [f"[LOCAL {i+1}] {x['source']}\n{x['chunk']}" for i, x in enumerate(local_chunks)]
    )

    web_context = "\n\n".join(
        [f"[WEB {i+1}] {x['title']}\n{x['snippet']}\n{x['url']}" for i, x in enumerate(web_results)]
    )

    prompt = f"""
You are a helpful assistant for a chatbot demo.

Return VALID JSON only with this schema:
{{
  "answer": "main answer in friendly chat style",
  "summary": "short 2-3 line summary",
  "web_highlights": ["short bullet 1", "short bullet 2"],
  "used_sources": ["source names or URLs"]
}}

Rules:
- Use the local context first.
- Use web context for freshness.
- If the answer is weak or uncertain, say that clearly.
- Do not add markdown fences.

Question:
{question}

Local context:
{local_context if local_context else "No local context found."}

Web context:
{web_context if web_context else "No web results found."}
""".strip()

    payload = {
        "model": CHAT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You answer strictly from the provided context and return JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        "format": "json",
        "stream": False,
    }

    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=300)
    r.raise_for_status()

    content = r.json()["message"]["content"]
    data = json.loads(content)

    if "used_sources" not in data:
        data["used_sources"] = []

    return {
        "answer": data.get("answer", ""),
        "summary": data.get("summary", ""),
        "web_highlights": data.get("web_highlights", []),
        "sources": list(dict.fromkeys(data.get("used_sources", []))),
    }


def chat(question: str):
    local_chunks = retrieve_local(question)
    web_results = search_web(question)
    result = ask_ollama(question, local_chunks, web_results)

    if not result["sources"]:
        result["sources"] = [x["source"] for x in local_chunks] + [x["url"] for x in web_results]

    return result