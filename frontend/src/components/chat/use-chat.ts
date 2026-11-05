"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { readSSE } from "./sse";
import { DEFAULT_CONFIG, type ChatConfig, type ChatMessage, type ChatNotice, type Phase } from "./types";

const KEY = "rc3.chat.v1";
const CAP = 20;
const FALLBACK_REPLY = "Sorry, I couldn't put together a reply just now. Could you try rephrasing your question?";
const JARGON = /\b(llm|embeddings?|json|traceback|exception|stack|sqlalchemy|psycopg|nonetype|keyerror|openai|anthropic|pydantic|fastapi|uvicorn)\b/i;

const uid = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;

function loadStored(): ChatMessage[] {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return [];
    const v = JSON.parse(raw) as { v?: number; messages?: ChatMessage[] };
    if (v?.v !== 1 || !Array.isArray(v.messages)) return [];
    return v.messages
      .filter((m) => m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string" && m.content)
      .slice(-CAP)
      .map((m) => ({ ...m, status: m.status === "streaming" ? "interrupted" : m.status }));
  } catch {
    return [];
  }
}
function store(messages: ChatMessage[]) {
  try {
    if (!messages.length) sessionStorage.removeItem(KEY);
    else sessionStorage.setItem(KEY, JSON.stringify({ v: 1, messages: messages.slice(-CAP) }));
  } catch {
    /* private mode / quota */
  }
}

function friendlyCode(code?: string, status?: number): string {
  if (code === "upstream_busy" || status === 503) return "The assistant is busy right now. Please try again in a moment.";
  if (code === "rate_limited" || status === 429) return "You're sending messages too quickly. Please wait a moment.";
  if (status === 0 || code === "network_error") return "We can't reach the server. Check your connection and try again.";
  return "Something went wrong. Please try again.";
}
function safeDetail(d: unknown): string {
  if (typeof d === "string" && d.trim() && d.length <= 200 && !JARGON.test(d)) return d.trim();
  return "That message couldn't be sent. Try shortening or rewording it.";
}
function retrySeconds(v: unknown): number {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? Math.min(Math.ceil(n), 3600) : 30;
}

interface Opts {
  config: ChatConfig | undefined;
  online: boolean;
  /** Put text back into the composer (rejected sends). */
  onRestoreDraft: (text: string) => void;
  /** An assistant reply finished. */
  onReply: () => void;
}

export function useChat(opts: Opts) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [phase, setPhase] = useState<Phase>("idle");
  const [notice, setNotice] = useState<ChatNotice | null>(null);
  const [retryAt, setRetryAt] = useState<number | null>(null);
  const [hydrated, setHydrated] = useState(false);

  const optsRef = useRef(opts);
  useEffect(() => {
    optsRef.current = opts;
  });
  const messagesRef = useRef<ChatMessage[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const genRef = useRef(0);
  const busyRef = useRef(false);
  const retryAtRef = useRef<number | null>(null);
  const liveRef = useRef<{ id: string; text: string } | null>(null);

  const commit = useCallback((next: ChatMessage[]) => {
    messagesRef.current = next;
    setMessages(next);
  }, []);

  // Hydration-safe restore (never touches sessionStorage during SSR).
  useEffect(() => {
    const t = setTimeout(() => {
      const stored = loadStored();
      if (stored.length && !messagesRef.current.length) commit(stored);
      setHydrated(true);
    }, 0);
    return () => clearTimeout(t);
  }, [commit]);

  // Persist only settled conversations.
  useEffect(() => {
    if (hydrated && phase === "idle") store(messages);
  }, [messages, phase, hydrated]);

  const abortNow = useCallback(() => {
    genRef.current++;
    abortRef.current?.abort();
    abortRef.current = null;
    busyRef.current = false;
  }, []);

  useEffect(() => abortNow, [abortNow]); // abort on unmount

  const start = useCallback(
    async (base: ChatMessage[]) => {
      const cfg = optsRef.current.config ?? DEFAULT_CONFIG;
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      const gen = ++genRef.current;
      busyRef.current = true;
      const alive = () => genRef.current === gen && !ctrl.signal.aborted;

      const asst: ChatMessage = { id: uid(), role: "assistant", content: "", ts: Date.now(), status: "streaming" };
      liveRef.current = { id: asst.id, text: "" };
      setNotice(null);
      commit([...base, asst]);
      setPhase("waiting");

      let text = "";
      let raf = 0;
      let firstToken = false;
      const patch = (p: Partial<ChatMessage>) => commit(messagesRef.current.map((m) => (m.id === asst.id ? { ...m, ...p } : m)));
      const flush = () => {
        raf = 0;
        if (alive()) patch({ content: text });
      };
      const settle = () => {
        if (raf) cancelAnimationFrame(raf);
        raf = 0;
        busyRef.current = false;
        setPhase("idle");
      };
      const dropAssistant = () => commit(messagesRef.current.filter((m) => m.id !== asst.id));
      /** Pre-reply failure: reject the send, restore the draft, optionally start a countdown. */
      const reject = (n: ChatNotice, seconds?: number) => {
        const user = base[base.length - 1];
        commit(base.slice(0, -1));
        if (user?.role === "user") optsRef.current.onRestoreDraft(user.content);
        if (seconds) {
          retryAtRef.current = Date.now() + seconds * 1000;
          setRetryAt(retryAtRef.current);
        }
        setNotice(n);
        settle();
      };
      const failAfterStart = (code?: string, status?: number) => {
        if (text) {
          patch({ content: text, status: "interrupted" });
          settle();
        } else {
          dropAssistant();
          setNotice({ text: friendlyCode(code, status), tone: "error", retryable: true });
          settle();
        }
      };

      // History: never the greeting, last max_messages, each truncated to max_chars, starting with a user turn.
      let history = base
        .filter((m) => m.content.trim())
        .slice(-cfg.max_messages)
        .map((m) => ({ role: m.role, content: m.content.slice(0, cfg.max_chars) }));
      while (history.length && history[0].role !== "user") history = history.slice(1);

      try {
        const res = await fetch("/api/chat/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
          credentials: "same-origin",
          cache: "no-store",
          signal: ctrl.signal,
          body: JSON.stringify({ messages: history, page: typeof location !== "undefined" ? location.pathname : null }),
        });
        if (!alive()) return;
        if (!res.ok) {
          const body = (await res.json().catch(() => null)) as { detail?: unknown; code?: string; retry_after?: number } | null;
          if (!alive()) return;
          if (res.status === 429) {
            const s = retrySeconds(body?.retry_after ?? res.headers.get("retry-after"));
            return reject({ text: "You're sending messages too quickly. You can send again shortly.", tone: "info", retryable: false }, s);
          }
          if (res.status === 422) return reject({ text: safeDetail(body?.detail), tone: "error", retryable: false });
          if (res.status === 401) return reject({ text: "Your session has expired. Please sign in again.", tone: "error", retryable: false });
          return failAfterStart(body?.code, res.status);
        }
        const ct = res.headers.get("content-type") ?? "";
        if (!res.body || !ct.includes("text/event-stream")) return failAfterStart("network_error", 0);

        let finished = false;
        let streamErr: { code?: string; retry_after?: number | null } | null = null;
        await readSSE(res.body, (ev) => {
          if (!alive() || finished) return;
          let d: Record<string, unknown> = {};
          try {
            d = JSON.parse(ev.data) as Record<string, unknown>;
          } catch {
            return;
          }
          if (ev.event === "token") {
            const t = typeof d.t === "string" ? d.t : "";
            if (!t) return;
            text += t;
            if (liveRef.current) liveRef.current.text = text;
            if (!firstToken) {
              firstToken = true;
              setPhase("streaming");
            }
            if (!raf) {
              raf = requestAnimationFrame(flush);
              // requestAnimationFrame is paused in background tabs: a short timer keeps the text streaming there too
              window.setTimeout(() => {
                if (raf) {
                  cancelAnimationFrame(raf);
                  flush();
                }
              }, 80);
            }
          } else if (ev.event === "done") {
            finished = true;
            patch({ content: text.trim() ? text : FALLBACK_REPLY, status: "done", finish: typeof d.finish === "string" ? d.finish : "stop" });
            settle();
            optsRef.current.onReply();
          } else if (ev.event === "error") {
            finished = true;
            streamErr = { code: typeof d.code === "string" ? d.code : undefined, retry_after: typeof d.retry_after === "number" ? d.retry_after : null };
          }
        });
        if (!alive()) return;
        if (finished && !streamErr) return;
        if (streamErr) {
          const e = streamErr as { code?: string; retry_after?: number | null };
          if (e.code === "rate_limited" || e.retry_after) {
            retryAtRef.current = Date.now() + retrySeconds(e.retry_after) * 1000;
            setRetryAt(retryAtRef.current);
          }
          return failAfterStart(e.code);
        }
        failAfterStart("network_error", 0); // stream ended without a done event
      } catch (e) {
        if (!alive() || (e as Error).name === "AbortError") return;
        failAfterStart("network_error", 0);
      }
    },
    [commit],
  );

  const send = useCallback(
    (raw: string): boolean => {
      const o = optsRef.current;
      const cfg = o.config ?? DEFAULT_CONFIG;
      const content = raw.trim();
      if (!content || busyRef.current) return false;
      if (content.length > cfg.max_chars) return false;
      if (retryAtRef.current && retryAtRef.current > Date.now()) return false;
      if (!o.online) {
        setNotice({ text: "You're offline. Your message is saved, so you can send it once you're back online.", tone: "error", retryable: false });
        return false;
      }
      const user: ChatMessage = { id: uid(), role: "user", content, ts: Date.now(), status: "done" };
      void start([...messagesRef.current, user]);
      return true;
    },
    [start],
  );

  const stop = useCallback(() => {
    if (!busyRef.current) return;
    const live = liveRef.current;
    abortNow();
    if (live) {
      const next = messagesRef.current.flatMap((m) => (m.id !== live.id ? [m] : live.text ? [{ ...m, content: live.text, status: "stopped" as const }] : []));
      commit(next);
    }
    setPhase("idle");
  }, [abortNow, commit]);

  const retry = useCallback(() => {
    if (busyRef.current) return;
    if (retryAtRef.current && retryAtRef.current > Date.now()) return;
    if (!optsRef.current.online) return;
    let base = messagesRef.current;
    while (base.length && base[base.length - 1].role === "assistant") base = base.slice(0, -1);
    if (base.length) void start(base);
  }, [start]);

  const regenerate = retry;

  const reset = useCallback(() => {
    abortNow();
    liveRef.current = null;
    retryAtRef.current = null;
    setRetryAt(null);
    setNotice(null);
    setPhase("idle");
    commit([]);
    store([]);
  }, [abortNow, commit]);

  return { messages, phase, notice, retryAt, hydrated, send, stop, retry, regenerate, reset, dismissNotice: () => setNotice(null) };
}
