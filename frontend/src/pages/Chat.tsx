import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useChart } from "../lib/chart-context";
import { useI18n } from "../lib/i18n";
import type { Lang } from "../lib/i18n";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  reasoning?: string;
}

declare global {
  interface Window {
    marked?: { parse: (text: string) => string };
    DOMPurify?: { sanitize: (html: string) => string };
  }
}

const REPLY_LANGUAGE: Record<Lang, string | null> = {
  en: "English",
  hi: "Hindi",
  hinglish: "Hinglish",
};

function mdToHtml(text: string): string {
  if (window.marked && window.DOMPurify) {
    try {
      return window.DOMPurify.sanitize(window.marked.parse(text || ""));
    } catch {
      // fall through to plain text
    }
  }
  return (text || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/\n/g, "<br>");
}

interface SseEvent {
  type: string;
  text?: string;
  channel?: string;
  content?: string;
  message?: string;
  session_id?: string;
}

async function readSse(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: SseEvent) => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let index = buffer.indexOf("\n\n");
    while (index >= 0) {
      const chunk = buffer.slice(0, index);
      buffer = buffer.slice(index + 2);
      for (const line of chunk.split("\n")) {
        if (!line.startsWith("data:")) continue;
        const raw = line.slice(5).trim();
        if (!raw) continue;
        try {
          onEvent(JSON.parse(raw) as SseEvent);
        } catch {
          // ignore malformed frames
        }
      }
      index = buffer.indexOf("\n\n");
    }
  }
}

export default function Chat() {
  const { chart } = useChart();
  const { t, lang } = useI18n();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const sessionRef = useRef<string | null>(localStorage.getItem("sweetastro_chat_session"));
  const controllerRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, status]);

  function patchLast(patch: Partial<ChatMessage>) {
    setMessages((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (last && last.role === "assistant") next[next.length - 1] = { ...last, ...patch };
      return next;
    });
  }

  async function send(text: string) {
    const message = text.trim();
    if (!message || streaming) return;
    setError("");
    setInput("");
    setMessages((prev) => [
      ...prev,
      { role: "user", content: message },
      { role: "assistant", content: "" },
    ]);
    setStreaming(true);
    setStatus(t("chat.thinking"));
    controllerRef.current = new AbortController();

    let content = "";
    let reasoning = "";
    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionRef.current,
          message,
          language: REPLY_LANGUAGE[lang],
        }),
        signal: controllerRef.current.signal,
      });
      if (response.status === 429) {
        setError("Rate limit reached — please wait a minute and try again.");
        return;
      }
      if (!response.ok || !response.body) throw new Error(`Server responded ${response.status}`);

      await readSse(response.body, (event) => {
        if (event.session_id) {
          sessionRef.current = event.session_id;
          localStorage.setItem("sweetastro_chat_session", event.session_id);
        }
        if (event.type === "status" && event.text) setStatus(event.text);
        if (event.type === "meta") setStatus(t("chat.writing"));
        if (event.type === "delta") {
          if (event.channel === "reasoning") {
            reasoning += event.text || "";
            patchLast({ reasoning });
          } else {
            content += event.text || "";
            patchLast({ content });
          }
        }
        if (event.type === "done") {
          if (event.content) content = event.content;
          patchLast({ content });
        }
        if (event.type === "error" && event.message) setError(event.message);
      });
      if (!content) {
        patchLast({
          content: "_No answer text was produced — the reasoning phase may have used the full budget. "
            + "Please retry or ask a shorter question._",
        });
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        if (!content) patchLast({ content: "_Stopped._" });
      } else {
        setError(t("chat.error"));
        if (!content) {
          patchLast({ content: "_Connection interrupted before an answer arrived. Please retry._" });
        }
      }
    } finally {
      setStreaming(false);
      setStatus("");
      controllerRef.current = null;
    }
  }

  function newChat() {
    if (controllerRef.current) controllerRef.current.abort();
    sessionRef.current = null;
    localStorage.removeItem("sweetastro_chat_session");
    setMessages([]);
    setError("");
  }

  return (
    <div className="space-y-4">
      <section className="card card-gold p-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-bold text-white">{t("chat.title")}</h1>
          <p className="text-[11px] text-slate-400 mt-0.5">
            {chart
              ? `${chart.birth.name} · ${chart.chart.ascendant_sign} lagna · ${chart.birth.place}`
              : t("home.form.title")}
          </p>
        </div>
        <div className="flex gap-2">
          {!chart && (
            <Link to="/" className="text-xs font-semibold text-slate-950 bg-amber-500 hover:bg-amber-400 px-3.5 py-2 rounded-lg transition">
              {t("home.openChart")}
            </Link>
          )}
          <button
            onClick={newChat}
            className="text-xs font-medium text-slate-300 border border-slate-700 hover:border-amber-500/50 px-3.5 py-2 rounded-lg transition"
          >
            {t("chat.new")}
          </button>
        </div>
      </section>

      <section className="card p-4 min-h-[420px] flex flex-col gap-4">
        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto max-h-[60vh] pr-1" role="log" aria-live="polite">
          {messages.length === 0 && (
            <div className="text-center text-xs text-slate-400 max-w-md mx-auto py-10 space-y-3">
              <div className="text-3xl">🪐</div>
              <p>{t("chat.empty")}</p>
            </div>
          )}
          {messages.map((message, index) => (
            <div key={index} className={message.role === "user" ? "flex justify-end" : "flex gap-3"}>
              {message.role === "user" ? (
                <div className="max-w-[85%] bg-amber-500/15 border border-amber-500/25 text-amber-50 rounded-2xl rounded-br-md px-4 py-2.5 text-sm whitespace-pre-wrap">
                  {message.content}
                </div>
              ) : (
                <>
                  <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-amber-600 via-amber-400 to-amber-200 flex items-center justify-center text-slate-950 text-sm shrink-0 mt-1">
                    🔮
                  </div>
                  <div className="flex-1 min-w-0 space-y-2">
                    {message.reasoning && (
                      <details className="text-[11px] text-slate-500">
                        <summary className="cursor-pointer uppercase tracking-wider hover:text-slate-300 select-none">
                          {t("chat.reasoning")} · {(message.reasoning.length / 1000).toFixed(1)}k
                        </summary>
                        <div className="mt-2 max-h-40 overflow-y-auto whitespace-pre-wrap">{message.reasoning}</div>
                      </details>
                    )}
                    <div
                      className="prose-chat text-sm text-slate-200 leading-relaxed [&_h1]:text-base [&_h2]:font-semibold [&_h2]:text-slate-100 [&_h2]:mt-4 [&_h3]:font-semibold [&_p]:my-2 [&_ul]:list-disc [&_ul]:ml-5 [&_ol]:list-decimal [&_ol]:ml-5 [&_strong]:text-white [&_table]:text-xs [&_td]:border [&_td]:border-slate-800 [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:border-slate-800 [&_th]:px-2 [&_th]:py-1"
                      dangerouslySetInnerHTML={{ __html: mdToHtml(message.content) }}
                    />
                  </div>
                </>
              )}
            </div>
          ))}
          {streaming && status && (
            <p className="text-xs text-amber-300/90 animate-pulse">{status}</p>
          )}
          {error && (
            <p role="alert" className="text-xs text-rose-300 bg-rose-950/40 border border-rose-800/60 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
        </div>

        <div className="flex items-end gap-2 border-t border-slate-800 pt-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send(input);
              }
            }}
            rows={1}
            placeholder={t("chat.placeholder")}
            aria-label={t("chat.placeholder")}
            className="flex-1 bg-ink-950 border border-slate-700 rounded-xl px-3 py-2.5 text-sm resize-none max-h-36 focus:outline-none focus:border-amber-500/60"
          />
          {streaming ? (
            <button
              onClick={() => controllerRef.current?.abort()}
              className="text-xs font-semibold text-slate-200 bg-slate-800 hover:bg-slate-700 px-4 py-2.5 rounded-xl transition"
            >
              {t("chat.stop")}
            </button>
          ) : (
            <button
              onClick={() => void send(input)}
              disabled={!input.trim()}
              className="btn-gold text-xs font-bold px-5 py-2.5 rounded-xl"
            >
              {t("chat.send")}
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
