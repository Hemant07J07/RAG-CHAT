from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/chat")
def chat_endpoint(payload: ChatRequest):
    return chat(payload.message)