import Image from "next/image";

export default function Home() {
  return (
    <div className="flex flex-col flex-1 items-center justify-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex flex-1 w-full max-w-3xl flex-col items-center justify-between py-32 px-16 bg-white dark:bg-black sm:items-start">
        "use client";

        import { useEffect, useRef, useState } from "react";

        type Message = {
          role: "user" | "assistant";
          content: string;
        };

        type ApiResponse = {
          answer: string;
          summary: string;
          web_highlights: string[];
          sources: string[];
        };

        export default function Home() {
          const [messages, setMessages] = useState<Message[]>([
            {
              role: "assistant",
              content: "Hi! Ask me anything and I’ll search local notes plus the web.",
            },
          ]);
          const [input, setInput] = useState("");
          const [loading, setLoading] = useState(false);
          const bottomRef = useRef<HTMLDivElement | null>(null);

          useEffect(() => {
            bottomRef.current?.scrollIntoView({ behavior: "smooth" });
          }, [messages, loading]);

          const sendMessage = async () => {
            const text = input.trim();
            if (!text || loading) return;

            setInput("");
            setMessages((prev) => [...prev, { role: "user", content: text }]);
            setLoading(true);

            try {
              const res = await fetch("http://localhost:8000/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text }),
              });

              const data: ApiResponse = await res.json();

              const assistantText =
                `Answer:\n${data.answer}\n\n` +
                `Summary:\n${data.summary}\n\n` +
                `Web highlights:\n${data.web_highlights?.map((x) => `- ${x}`).join("\n") || "- None"}\n\n` +
                `Sources:\n${data.sources?.map((x) => `- ${x}`).join("\n") || "- None"}`;

              setMessages((prev) => [...prev, { role: "assistant", content: assistantText }]);
            } catch (err) {
              setMessages((prev) => [
                ...prev,
                {
                  role: "assistant",
                  content: "Sorry, the backend is not responding right now.",
                },
              ]);
            } finally {
              setLoading(false);
            }
          };

          return (
            <main style={styles.page}>
              <div style={styles.shell}>
                <header style={styles.header}>
                  <div>
                    <h1 style={styles.title}>Beamstack RAG Chat</h1>
                    <p style={styles.subtitle}>Ollama + web search + local context</p>
                  </div>
                </header>

                <section style={styles.chat}>
                  {messages.map((m, idx) => (
                    <div
                      key={idx}
                      style={{
                        ...styles.bubbleRow,
                        justifyContent: m.role === "user" ? "flex-end" : "flex-start",
                      }}
                    >
                      <div
                        style={{
                          ...styles.bubble,
                          ...(m.role === "user" ? styles.userBubble : styles.assistantBubble),
                        }}
                      >
                        <pre style={styles.pre}>{m.content}</pre>
                      </div>
                    </div>
                  ))}

                  {loading && (
                    <div style={styles.bubbleRow}>
                      <div style={{ ...styles.bubble, ...styles.assistantBubble }}>
                        <pre style={styles.pre}>Thinking...</pre>
                      </div>
                    </div>
                  )}

                  <div ref={bottomRef} />
                </section>

                <footer style={styles.footer}>
                  <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                    placeholder="Type your message..."
                    style={styles.input}
                  />
                  <button onClick={sendMessage} style={styles.button}>
                    Send
                  </button>
                </footer>
              </div>
            </main>
          );
        }

        const styles: Record<string, React.CSSProperties> = {
          page: {
            minHeight: "100vh",
            background: "#0b0f19",
            color: "#e5e7eb",
            display: "flex",
            justifyContent: "center",
            padding: "24px",
            boxSizing: "border-box",
          },
          shell: {
            width: "100%",
            maxWidth: "980px",
            height: "calc(100vh - 48px)",
            display: "flex",
            flexDirection: "column",
            background: "#111827",
            border: "1px solid #243044",
            borderRadius: "20px",
            overflow: "hidden",
          },
          header: {
            padding: "20px 24px",
            borderBottom: "1px solid #243044",
            background: "#0f172a",
          },
          title: {
            margin: 0,
            fontSize: "22px",
            fontWeight: 700,
          },
          subtitle: {
            margin: "6px 0 0",
            fontSize: "14px",
            color: "#94a3b8",
          },
          chat: {
            flex: 1,
            overflowY: "auto",
            padding: "20px",
            display: "flex",
            flexDirection: "column",
            gap: "14px",
          },
          bubbleRow: {
            display: "flex",
          },
          bubble: {
            maxWidth: "78%",
            borderRadius: "18px",
            padding: "14px 16px",
            whiteSpace: "normal",
            lineHeight: 1.5,
            boxShadow: "0 8px 24px rgba(0,0,0,0.18)",
          },
          userBubble: {
            background: "#2563eb",
            color: "#fff",
            borderBottomRightRadius: "6px",
          },
          assistantBubble: {
            background: "#1f2937",
            color: "#e5e7eb",
            borderBottomLeftRadius: "6px",
            border: "1px solid #334155",
          },
          pre: {
            margin: 0,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            fontFamily: "inherit",
            fontSize: "14px",
          },
          footer: {
            padding: "16px",
            borderTop: "1px solid #243044",
            display: "flex",
            gap: "12px",
            background: "#0f172a",
          },
          input: {
            flex: 1,
            borderRadius: "12px",
            border: "1px solid #334155",
            background: "#111827",
            color: "#e5e7eb",
            padding: "14px 16px",
            outline: "none",
            fontSize: "14px",
          },
          button: {
            borderRadius: "12px",
            border: "none",
            padding: "14px 18px",
            background: "#22c55e",
            color: "#052e16",
            fontWeight: 700,
            cursor: "pointer",
          },
        };
