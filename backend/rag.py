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
- Write `answer` in warm, natural conversation style.
- Keep `summary` to 1-2 concise lines.
- Keep `web_highlights` short and factual.
- Include only real sources you used in `used_sources`.

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
                "content": (
                    "You are Beamstack RAG Chat, a helpful assistant. "
                    "Respond in natural conversational language for the `answer` field, "
                    "and return valid JSON only."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "format": "json",
        "stream": False,
        "keep_alive": "10m",
    }

    base_url = (OLLAMA_URL or "").rstrip("/")
    attempts = []
    content = None

    # 1) Ollama native chat endpoint
    try:
        r = requests.post(f"{base_url}/api/chat", json=payload, timeout=300)
        if r.ok:
            data = r.json()
            if isinstance(data, dict) and isinstance(data.get("message"), dict):
                content = data["message"].get("content", "")
        if content is None:
            attempts.append(("/api/chat", r.status_code, r.text[:300]))
    except Exception as e:
        attempts.append(("/api/chat", "error", str(e)[:300]))

    # 2) OpenAI-compatible chat endpoint
    if content is None:
        try:
            v1_payload = {
                "model": CHAT_MODEL,
                "messages": payload["messages"],
                "stream": False,
            }
            r = requests.post(f"{base_url}/v1/chat/completions", json=v1_payload, timeout=300)
            if r.ok:
                data = r.json()
                choices = data.get("choices", []) if isinstance(data, dict) else []
                if choices and isinstance(choices[0], dict):
                    msg = choices[0].get("message", {})
                    if isinstance(msg, dict):
                        content = msg.get("content", "")
            if content is None:
                attempts.append(("/v1/chat/completions", r.status_code, r.text[:300]))
        except Exception as e:
            attempts.append(("/v1/chat/completions", "error", str(e)[:300]))

    # 3) Ollama generate endpoint fallback
    if content is None:
        try:
            generate_payload = {
                "model": CHAT_MODEL,
                "prompt": prompt,
                "stream": False,
                "keep_alive": "10m",
            }
            r = requests.post(f"{base_url}/api/generate", json=generate_payload, timeout=300)
            if r.ok:
                data = r.json()
                if isinstance(data, dict):
                    content = data.get("response", "")
            if content is None:
                attempts.append(("/api/generate", r.status_code, r.text[:300]))
        except Exception as e:
            attempts.append(("/api/generate", "error", str(e)[:300]))

    if content is None:
        detail = "\n".join([f"- {p}: {code} {msg}" for p, code, msg in attempts])
        raise RuntimeError(
            "Failed to get chat completion from the configured server. "
            "Tried /api/chat, /v1/chat/completions, and /api/generate.\n" + detail
        )

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {
            "answer": content,
            "summary": "",
            "web_highlights": [],
            "used_sources": [],
        }

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
    try:
        result = ask_ollama(question, local_chunks, web_results)
    except Exception as e:
        result = {
            "answer": (
                "I could not reach the local model server right now. "
                "Please check Ollama and model availability, then try again."
            ),
            "summary": str(e),
            "web_highlights": [],
            "sources": [],
        }

    if not result["sources"]:
        result["sources"] = [x["source"] for x in local_chunks] + [x["url"] for x in web_results]

    return result