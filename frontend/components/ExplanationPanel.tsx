"use client";
import { useState, useEffect, useRef, FormEvent } from "react";
import ReactMarkdown from "react-markdown";

interface Props {
  questionId: string;
  visible: boolean;
  onClose: () => void;
}

interface Message {
  role: "assistant" | "user";
  content: string;
}

function useSSEStream(url: string, opts: RequestInit, onToken: (t: string) => void, onDone: () => void, onError: () => void) {
  const controller = new AbortController();
  fetch(url, { ...opts, signal: controller.signal })
    .then(async (res) => {
      if (!res.ok) { onError(); return; }
      const reader = res.body?.getReader();
      if (!reader) return;
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const chunk = line.slice(6);
            if (chunk === "[DONE]") { onDone(); return; }
            try {
              const parsed = JSON.parse(chunk);
              if (parsed.error) { onError(); return; }
              if (parsed.token) onToken(parsed.token);
            } catch { onToken(chunk); }
          }
        }
      }
      onDone();
    })
    .catch((err) => { if (err.name !== "AbortError") onError(); });
  return controller;
}

export default function ExplanationPanel({ questionId, visible, onClose }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Scroll to bottom on new content
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streaming]);

  // Load initial explanation
  useEffect(() => {
    if (!visible || !questionId) return;
    setMessages([]);
    setError(false);
    setSuggestions([]);
    setInput("");
    setStreaming(true);

    const token = localStorage.getItem("access_token");
    let accumulated = "";

    const ctrl = useSSEStream(
      `/api/questions/${questionId}/explain`,
      { headers: { Authorization: `Bearer ${token}` } },
      (t) => {
        accumulated += t;
        setMessages([{ role: "assistant", content: accumulated }]);
      },
      () => {
        setStreaming(false);
        loadSuggestions();
      },
      () => { setError(true); setStreaming(false); }
    );
    abortRef.current = ctrl;

    return () => ctrl.abort();
  }, [visible, questionId]);

  function loadSuggestions() {
    const token = localStorage.getItem("access_token");
    fetch(`/api/questions/${questionId}/suggestions`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((d) => setSuggestions(d.suggestions || []))
      .catch(() => {});
  }

  function askFollowup(question: string) {
    if (!question.trim() || streaming) return;
    const token = localStorage.getItem("access_token");
    const newMessages: Message[] = [...messages, { role: "user", content: question }];
    setMessages(newMessages);
    setInput("");
    setSuggestions([]);
    setStreaming(true);

    let accumulated = "";
    const ctrl = useSSEStream(
      `/api/questions/${questionId}/followup`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ question, history: newMessages }),
      },
      (t) => {
        accumulated += t;
        setMessages([...newMessages, { role: "assistant", content: accumulated }]);
      },
      () => setStreaming(false),
      () => { setError(true); setStreaming(false); }
    );
    abortRef.current = ctrl;
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    askFollowup(input);
  }

  if (!visible) return null;

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end max-w-md mx-auto" onClick={onClose}>
      <div className="bg-black/30 absolute inset-0" />
      <div className="relative bg-white rounded-t-2xl shadow-2xl max-h-[70vh] flex flex-col animate-slide-up"
        onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex justify-between items-center px-5 py-3 border-b border-slate-100 shrink-0">
          <h3 className="text-sm font-bold text-slate-700">AI Explanation</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-lg" aria-label="Close explanation">✕</button>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {error && messages.length === 0 ? (
            <p className="text-red-500 text-sm">Explanation unavailable. Tap to try again.</p>
          ) : messages.length === 0 && streaming ? (
            <span className="animate-pulse text-slate-400 text-sm">Thinking...</span>
          ) : (
            messages.map((m, i) => (
              <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
                {m.role === "user" ? (
                  <div className="bg-brand/10 text-brand rounded-2xl rounded-br-sm px-4 py-2 text-sm max-w-[85%]">
                    {m.content}
                  </div>
                ) : (
                  <div className="text-sm text-slate-600 leading-relaxed prose prose-sm prose-slate max-w-none">
                    <ReactMarkdown>{m.content}</ReactMarkdown>
                  </div>
                )}
              </div>
            ))
          )}
          {streaming && messages.length > 0 && messages[messages.length - 1].role === "user" && (
            <span className="animate-pulse text-slate-400 text-sm">Thinking...</span>
          )}
        </div>

        {/* Suggestions */}
        {suggestions.length > 0 && !streaming && (
          <div className="px-5 pb-2 flex gap-2 flex-wrap shrink-0">
            {suggestions.map((s, i) => (
              <button key={i} onClick={() => askFollowup(s)}
                className="text-xs bg-slate-100 hover:bg-brand/10 hover:text-brand text-slate-600 rounded-full px-3 py-1.5 transition text-left">
                {s}
              </button>
            ))}
          </div>
        )}

        {/* Input + Got it */}
        <div className="px-5 pb-4 pt-2 border-t border-slate-100 shrink-0">
          {!streaming && messages.length > 0 && (
            <form onSubmit={handleSubmit} className="flex gap-2 mb-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a follow-up..."
                className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand"
              />
              <button type="submit" disabled={!input.trim()}
                className="bg-brand text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-green-700 disabled:opacity-40 transition">
                Ask
              </button>
            </form>
          )}
          <button onClick={onClose}
            className="w-full bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg py-2.5 text-sm font-semibold transition">
            Got it
          </button>
        </div>
      </div>
    </div>
  );
}
