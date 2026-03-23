"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type MessageRole = "user" | "assistant";

type ChatMessage = {
  role: MessageRole;
  content: string;
  summary?: string;
  webHighlights?: string[];
  sources?: string[];
};

type Conversation = {
  id: string;
  title: string;
  createdAt: number;
  messages: ChatMessage[];
};

type ApiResponse = {
  answer: string;
  summary: string;
  web_highlights: string[];
  sources: string[];
};

const STORAGE_KEY = "beamstack-rag-chat-v2";

function makeId() {
  return `chat-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

function makeTitle(text: string) {
  const trimmed = text.trim().replace(/\s+/g, " ");
  if (!trimmed) return "New chat";
  return trimmed.length > 30 ? `${trimmed.slice(0, 30)}...` : trimmed;
}

function createConversation(): Conversation {
  return {
    id: makeId(),
    title: "New chat",
    createdAt: Date.now(),
    messages: [
      {
        role: "assistant",
        content:
          "Hi! I'm ready. Ask me anything and I'll use local context plus web search.",
      },
    ],
  };
}

export default function Home() {
  const [conversations, setConversations] = useState<Conversation[]>([
    createConversation(),
  ]);
  const [activeId, setActiveId] = useState<string>("");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      try {
        const saved = JSON.parse(raw) as {
          conversations: Conversation[];
          activeId: string;
        };

        if (saved.conversations?.length) {
          setConversations(saved.conversations);
          setActiveId(saved.activeId || saved.conversations[0].id);
        }
      } catch {
        // ignore bad localStorage data
      }
    }

    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated || typeof window === "undefined") return;
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ conversations, activeId }),
    );
  }, [conversations, activeId, hydrated]);

  useEffect(() => {
    if (!activeId && conversations.length > 0) {
      setActiveId(conversations[0].id);
    }
  }, [activeId, conversations]);

  const activeConversation = useMemo(() => {
    return conversations.find((c) => c.id === activeId) ?? conversations[0];
  }, [conversations, activeId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeConversation?.messages.length, loading]);

  const createNewChat = () => {
    const conv = createConversation();
    setConversations((prev) => [conv, ...prev]);
    setActiveId(conv.id);
    setInput("");
    setLoading(false);
  };

  const selectChat = (id: string) => {
    setActiveId(id);
    setInput("");
    setLoading(false);
  };

  const updateConversation = (
    id: string,
    updater: (conv: Conversation) => Conversation,
  ) => {
    setConversations((prev) => prev.map((conv) => (conv.id === id ? updater(conv) : conv)));
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading || !activeConversation) return;

    const currentId = activeConversation.id;
    setInput("");
    setLoading(true);

    const userMessage: ChatMessage = { role: "user", content: text };

    updateConversation(currentId, (conv) => ({
      ...conv,
      title: conv.title === "New chat" ? makeTitle(text) : conv.title,
      messages: [...conv.messages, userMessage],
    }));

    try {
      const res = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });

      const data: ApiResponse = await res.json();

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: data.answer || "I could not generate a reply right now.",
        summary: data.summary || "",
        webHighlights: data.web_highlights || [],
        sources: data.sources || [],
      };

      updateConversation(currentId, (conv) => ({
        ...conv,
        messages: [...conv.messages, assistantMessage],
      }));
    } catch {
      const errorMessage: ChatMessage = {
        role: "assistant",
        content: "Sorry, the backend is not responding right now.",
      };

      updateConversation(currentId, (conv) => ({
        ...conv,
        messages: [...conv.messages, errorMessage],
      }));
    } finally {
      setLoading(false);
    }
  };

  const recentChats = [...conversations].sort((a, b) => b.createdAt - a.createdAt);

  return (
    <main className="h-screen w-screen bg-zinc-950 text-zinc-100 overflow-hidden">
      <div className="flex h-full">
        <aside className="hidden md:flex w-80 flex-col border-r border-zinc-800 bg-zinc-950">
          <div className="p-4 border-b border-zinc-800">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h1 className="text-lg font-semibold">Beamstack RAG Chat</h1>
                <p className="text-xs text-zinc-400 mt-1">Ollama + web search</p>
              </div>
            </div>

            <button
              onClick={createNewChat}
              className="mt-4 w-full rounded-2xl bg-zinc-100 px-4 py-3 text-sm font-semibold text-zinc-950 hover:bg-white transition"
            >
              + New chat
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-6">
            <section>
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">
                History
              </h2>

              <div className="space-y-2">
                {recentChats.map((chat) => {
                  const active = chat.id === activeId;
                  const firstUser =
                    chat.messages.find((m) => m.role === "user")?.content ||
                    "New chat";

                  return (
                    <button
                      key={chat.id}
                      onClick={() => selectChat(chat.id)}
                      className={`w-full rounded-2xl border px-3 py-3 text-left transition ${
                        active
                          ? "border-blue-500 bg-blue-500/15"
                          : "border-zinc-800 bg-zinc-900 hover:bg-zinc-800"
                      }`}
                    >
                      <div className="text-sm font-medium truncate">
                        {chat.title === "New chat" ? makeTitle(firstUser) : chat.title}
                      </div>
                      <div className="mt-1 text-xs text-zinc-400 truncate">
                        {chat.messages.length} messages
                      </div>
                    </button>
                  );
                })}
              </div>
            </section>

            <section>
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">
                More apps
              </h2>

              <div className="grid gap-2">
                {["Web Search", "Docs", "Model Lab", "Settings"].map((item) => (
                  <button
                    key={item}
                    className="rounded-2xl border border-zinc-800 bg-zinc-900 px-3 py-3 text-left text-sm text-zinc-200 hover:bg-zinc-800 transition"
                  >
                    {item}
                  </button>
                ))}
              </div>
            </section>
          </div>

          <div className="border-t border-zinc-800 p-4 text-xs text-zinc-500">
            Local demo mode
          </div>
        </aside>

        <section className="flex-1 flex flex-col">
          <header className="border-b border-zinc-800 bg-zinc-950/80 px-4 sm:px-6 py-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h1 className="text-xl sm:text-2xl font-semibold">
                  {activeConversation?.title || "Beamstack RAG Chat"}
                </h1>
                <p className="text-sm text-zinc-400 mt-1">
                  Chat-style UI with history, new chat, and app shortcuts
                </p>
              </div>

              <button
                onClick={createNewChat}
                className="md:hidden rounded-2xl bg-zinc-100 px-4 py-2 text-sm font-semibold text-zinc-950"
              >
                New chat
              </button>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-5">
            <div className="mx-auto max-w-4xl space-y-4">
              {activeConversation?.messages.map((m, idx) => (
                <div
                  key={idx}
                  className={`flex ${
                    m.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-[85%] rounded-3xl px-4 py-3 text-sm leading-6 shadow-lg ${
                      m.role === "user"
                        ? "bg-blue-600 text-white rounded-br-md"
                        : "bg-zinc-900 text-zinc-100 border border-zinc-800 rounded-bl-md"
                    }`}
                  >
                    {m.role === "assistant" ? (
                      <div className="space-y-4">
                        <div className="whitespace-pre-wrap">{m.content}</div>

                        {(m.summary || m.webHighlights?.length || m.sources?.length) && (
                          <div className="space-y-3 border-t border-zinc-800 pt-3 text-sm">
                            {m.summary ? (
                              <div>
                                <div className="text-xs uppercase tracking-wider text-zinc-500 mb-1">
                                  Summary
                                </div>
                                <div className="text-zinc-300 whitespace-pre-wrap">
                                  {m.summary}
                                </div>
                              </div>
                            ) : null}

                            {m.webHighlights?.length ? (
                              <div>
                                <div className="text-xs uppercase tracking-wider text-zinc-500 mb-1">
                                  Web highlights
                                </div>
                                <ul className="list-disc pl-5 space-y-1 text-zinc-300">
                                  {m.webHighlights.map((item, i) => (
                                    <li key={i}>{item}</li>
                                  ))}
                                </ul>
                              </div>
                            ) : null}

                            {m.sources?.length ? (
                              <div>
                                <div className="text-xs uppercase tracking-wider text-zinc-500 mb-1">
                                  Sources
                                </div>
                                <div className="flex flex-wrap gap-2">
                                  {m.sources.map((src, i) => (
                                    <span
                                      key={i}
                                      className="rounded-full border border-zinc-700 bg-zinc-950 px-3 py-1 text-xs text-zinc-300"
                                    >
                                      {src}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            ) : null}
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="whitespace-pre-wrap">{m.content}</div>
                    )}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div className="rounded-3xl rounded-bl-md border border-zinc-800 bg-zinc-900 px-4 py-3 text-sm text-zinc-300 shadow-lg">
                    Thinking...
                  </div>
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          </div>

          <footer className="border-t border-zinc-800 bg-zinc-950/90 p-4 sm:p-6">
            <div className="mx-auto max-w-4xl flex gap-3 items-end">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                  }
                }}
                placeholder="Type your message..."
                rows={1}
                className="min-h-[56px] flex-1 resize-none rounded-2xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-sm outline-none focus:border-blue-500"
              />

              <button
                onClick={sendMessage}
                disabled={loading || !input.trim()}
                className="rounded-2xl bg-green-500 px-5 py-3 text-sm font-semibold text-black hover:bg-green-400 disabled:opacity-50 disabled:cursor-not-allowed transition"
              >
                Send
              </button>
            </div>
          </footer>
        </section>
      </div>
    </main>
  );
}
