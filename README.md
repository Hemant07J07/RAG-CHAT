# RAG-CHAT

RAG-CHAT is a full-stack retrieval-augmented chatbot project with:

- FastAPI backend
- Next.js frontend
- Ollama for local LLM generation and embeddings
- MCP-based retrieval tools (local docs + web search)

## Project Structure

- `backend/`
	- `app.py`: FastAPI app and API routes (`/health`, `/chat`)
	- `rag.py`: Chat orchestration and Ollama answer generation
	- `ingest.py`: Builds local vector index in `data/index.json`
	- `mcp_server.py`: MCP tool server (stdio transport)
	- `mcp_client.py`: MCP client bridge with local fallback
	- `retrieval_tools.py`: Shared retrieval/search tool implementations
	- `.env`: Backend environment configuration
	- `docs/`: Local source documents (example: `sample.md`)
	- `data/`: Generated local index storage (`index.json`)
- `frontend/`
	- `src/app/page.tsx`: Chat UI with sidebar/history/localStorage persistence
	- `next.config.js`: Next.js config (includes Turbopack root)

## How It Works

Flow:

1. Frontend sends a user message to backend `/chat`.
2. Backend calls MCP tools (or local fallback) for:
	 - local doc retrieval from `data/index.json`
	 - web search results
3. Backend sends combined context to Ollama.
4. Backend returns structured JSON:
	 - `answer`
	 - `summary`
	 - `web_highlights`
	 - `sources`
5. Frontend renders answer and metadata in chat view.

## Requirements

- Python 3.10+
- Node.js 18+
- Ollama installed and running on `http://localhost:11434`

## Backend Setup

From project root:

```bash
cd backend
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure `.env` in `backend/`:

```env
OLLAMA_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=llama3.2:1b
OLLAMA_EMBED_MODEL=embeddinggemma
MCP_ENABLED=true
MCP_SERVER_PATH=mcp_server.py
```

Pull required models:

```bash
ollama pull llama3.2:1b
ollama pull embeddinggemma
```

Build local index:

```bash
python ingest.py
```

Run backend:

```bash
uvicorn app:app --reload --port 8000
```

## Frontend Setup

From project root:

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:3000` and calls backend on `http://localhost:8000`.

## API

- `GET /health`
	- Returns backend status and MCP status.
- `POST /chat`
	- Request:
		```json
		{ "message": "Tell me about India" }
		```
	- Response:
		```json
		{
			"answer": "...",
			"summary": "...",
			"web_highlights": ["..."],
			"sources": ["..."]
		}
		```

## Notes on MCP

- MCP server is `backend/mcp_server.py`.
- Backend uses `mcp_client.py` to call MCP tools over stdio.
- If MCP is unavailable, backend falls back to local implementations in `retrieval_tools.py`.

## Troubleshooting

### 1) `data/index.json` is missing

- Ensure `ollama pull embeddinggemma` completed.
- Re-run `python ingest.py` from `backend/`.

### 2) Chat says model server unavailable

- Check Ollama is running.
- Verify `.env` model names exist in `ollama list`.

### 3) MCP or ddgs import errors

- Reinstall backend dependencies:
	```bash
	pip install -r requirements.txt
	```

### 4) Frontend/Backend connection issues

- Confirm backend runs on port `8000`.
- Confirm frontend runs on port `3000`.

## Current Stack

- Backend: FastAPI + Requests + NumPy + MCP Python SDK
- Frontend: Next.js 16 + React 19 + TypeScript
- Retrieval: Local embedding search + web search
- Generation: Ollama chat API
