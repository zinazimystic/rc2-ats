"use client";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type RefObject } from "react";
import { ArrowDown, RotateCcw, SquarePen, WifiOff, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Composer } from "./composer";
import { Avatar, Message } from "./message";
import { useCountdown } from "./use-env";
import type { useChat } from "./use-chat";
import type { ChatConfig } from "./types";

type Chat = ReturnType<typeof useChat>;

interface Props {
  state: "open" | "closed";
  config: ChatConfig | undefined;
  configLoading: boolean;
  configFailed: boolean;
  onRecheck: () => void;
  chat: Chat;
  draft: string;
  setDraft: (v: string) => void;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  online: boolean;
  onClose: () => void;
}

const FOCUSABLE = 'button:not([disabled]),a[href],textarea:not([disabled]),input:not([disabled]),[tabindex]:not([tabindex="-1"])';

export default function ChatPanel({ state, config, configLoading, configFailed, onRecheck, chat, draft, setDraft, inputRef, online, onClose }: Props) {
  const { messages, phase, notice, retryAt, send, stop, retry, reset } = chat;
  const panelRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const prevLen = useRef(0);
  const [atBottom, setAtBottom] = useState(true);
  const countdown = useCountdown(retryAt);
  const busy = phase !== "idle";
  const unavailable = configFailed;
  const last = messages[messages.length - 1];

  // Move focus into the panel on open (input, or the first control if the input is disabled).
  useEffect(() => {
    inputRef.current?.focus({ preventScroll: true });
    if (!panelRef.current?.contains(document.activeElement)) panelRef.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus({ preventScroll: true });
  }, [inputRef]);

  const scrollDown = useCallback((smooth: boolean) => {
    const el = listRef.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth && !reduce ? "smooth" : "auto" });
  }, []);

  // Keep pinned to the latest message unless the user scrolled up.
  useLayoutEffect(() => {
    const grew = messages.length > prevLen.current;
    prevLen.current = messages.length;
    if (grew && messages[messages.length - 1]?.role === "user") stick.current = true;
    if (stick.current) scrollDown(grew);
  }, [messages, phase, notice, scrollDown]);

  const onScroll = () => {
    const el = listRef.current;
    if (!el) return;
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    stick.current = near;
    setAtBottom(near);
  };

  const trapTab = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "Tab") return;
    const nodes = Array.from(panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []).filter((n) => n.offsetParent !== null);
    if (!nodes.length) return;
    const first = nodes[0];
    const lastN = nodes[nodes.length - 1];
    const active = document.activeElement;
    if (e.shiftKey && (active === first || !panelRef.current?.contains(active))) {
      e.preventDefault();
      lastN.focus();
    } else if (!e.shiftKey && (active === lastN || !panelRef.current?.contains(active))) {
      e.preventDefault();
      first.focus();
    }
  };

  const submit = (text: string) => {
    if (send(text)) setDraft("");
  };

  const announce =
    phase !== "idle" ? "Assistant is typing" : last?.role === "assistant" && last.status === "done" ? last.content.slice(0, 600) : "";
  const lastAsst = last?.role === "assistant" ? last : undefined;
  const canRetryNotice = notice?.retryable && !busy && !countdown && online;
  const showGreetingChips = !messages.length && !!config?.suggestions.length;

  return (
    <div
      ref={panelRef}
      role="dialog"
      aria-label="RC3 Assistant chat"
      data-state={state}
      onKeyDown={trapTab}
      className={cn(
        "rc-panel fixed z-[60] flex flex-col overflow-hidden bg-background text-foreground",
        "inset-0 h-dvh w-full",
        "sm:inset-auto sm:right-5 sm:bottom-5 sm:h-[600px] sm:max-h-[calc(100dvh-2.5rem)] sm:w-[400px] sm:rounded-2xl sm:border sm:shadow-2xl sm:shadow-black/20",
        state === "closed" && "pointer-events-none",
      )}
    >
      <header className="flex items-center gap-3 border-b bg-card px-4 pt-[max(0.75rem,env(safe-area-inset-top))] pb-3">
        <Avatar className="size-9" />
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-sm leading-tight font-semibold">RC3 Assistant</h2>
          <p className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className={cn("size-2 rounded-full", config?.available && !configFailed ? "bg-success" : "bg-muted-foreground/50")} aria-hidden />
            {configLoading ? "Connecting…" : config?.available && !configFailed ? "Online" : "Offline"}
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            reset();
            setDraft("");
            inputRef.current?.focus();
          }}
          aria-label="New chat"
          title="New chat"
          className="inline-flex size-8 items-center justify-center rounded-full text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
        >
          <SquarePen className="size-4" />
        </button>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close chat"
          title="Close (Esc)"
          className="inline-flex size-8 items-center justify-center rounded-full text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
        >
          <X className="size-4" />
        </button>
      </header>

      <div className="relative min-h-0 flex-1">
        <div ref={listRef} onScroll={onScroll} role="log" aria-label="Conversation" aria-live="off" className="h-full space-y-4 overflow-y-auto overscroll-contain px-3.5 py-4">
          {configLoading ? (
            <div className="flex items-start gap-2" aria-busy="true">
              <Avatar className="mt-0.5" />
              <div className="skeleton h-16 w-[75%] rounded-2xl" />
            </div>
          ) : (
            <div className="rc-msg flex items-start gap-2">
              <Avatar className="mt-0.5" />
              <div className="max-w-[88%] rounded-2xl rounded-tl-md border bg-card px-3.5 py-2.5 text-sm leading-relaxed shadow-xs [overflow-wrap:anywhere]">
                {config?.greeting ?? "Hi! I'm the RC3 Assistant."}
              </div>
            </div>
          )}
          {showGreetingChips && (
            <div className="flex flex-wrap gap-2 pl-10" aria-label="Suggested questions">
              {config!.suggestions.slice(0, 4).map((s) => (
                <button
                  key={s}
                  type="button"
                  disabled={busy || !online || !!countdown}
                  onClick={() => submit(s)}
                  className="rounded-full border bg-card px-3 py-1.5 text-left text-xs font-medium shadow-xs transition hover:border-primary/50 hover:bg-primary/5 hover:text-primary focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
          {messages.map((m) => (
            <Message
              key={m.id}
              m={m}
              waiting={m.role === "assistant" && m.status === "streaming" && !m.content}
              canRegenerate={m === lastAsst && m.status === "done" && !busy}
              disabled={busy || !!countdown || !online}
              onRegenerate={retry}
              onRetry={retry}
              onNavigate={onClose}
            />
          ))}
        </div>
        <div className="sr-only" aria-live="polite" aria-atomic="true">
          {announce}
        </div>
        {!atBottom && messages.length > 0 && (
          <button
            type="button"
            onClick={() => {
              stick.current = true;
              scrollDown(true);
            }}
            className="absolute bottom-3 left-1/2 inline-flex h-8 -translate-x-1/2 items-center gap-1.5 rounded-full border bg-card px-3 text-xs font-medium shadow-lg transition hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ArrowDown className="size-3.5" /> Jump to latest
          </button>
        )}
      </div>

      <div className="space-y-2 px-3 pt-2 empty:hidden">
        {!online && (
          <p role="status" className="flex items-center gap-2 rounded-xl bg-warning/15 px-3 py-2 text-xs">
            <WifiOff className="size-3.5 shrink-0" /> You&apos;re offline. Your draft is kept until you reconnect.
          </p>
        )}
        {configFailed && (
          <p role="alert" className="flex items-center justify-between gap-2 rounded-xl bg-destructive/10 px-3 py-2 text-xs">
            <span>The assistant isn&apos;t available right now.</span>
            <button type="button" onClick={onRecheck} className="shrink-0 font-semibold underline underline-offset-2">
              Check again
            </button>
          </p>
        )}
        {notice && (
          <p role={notice.tone === "error" ? "alert" : "status"} className={cn("flex items-center justify-between gap-2 rounded-xl px-3 py-2 text-xs", notice.tone === "error" ? "bg-destructive/10" : "bg-primary/10")}>
            <span>{notice.text}</span>
            {notice.retryable && (
              <button
                type="button"
                onClick={retry}
                disabled={!canRetryNotice}
                className="inline-flex shrink-0 items-center gap-1 rounded-full border bg-card px-2.5 py-1 font-semibold disabled:opacity-50"
              >
                <RotateCcw className="size-3" /> Retry
              </button>
            )}
          </p>
        )}
      </div>

      <Composer
        value={draft}
        onChange={setDraft}
        onSend={() => submit(draft)}
        onStop={stop}
        inputRef={inputRef}
        max={config?.max_chars ?? 2000}
        busy={busy}
        countdown={countdown}
        offline={!online}
        unavailable={unavailable}
      />
    </div>
  );
}
