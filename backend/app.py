from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from mcp_client import check_mcp_connection
from rag import chat

app = FastAPI(title="RAG Chat Demo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


@app.on_event("startup")
def startup_event():
    app.state.mcp_status = check_mcp_connection()


@app.get("/health")
def health():
    return {"ok": True, "mcp": getattr(app.state, "mcp_status", {"ok": False})}


@app.post("/chat")
def chat_endpoint(payload: ChatRequest):
    return chat(payload.message)