"use client";
import { useEffect, type ClipboardEvent, type KeyboardEvent, type RefObject } from "react";
import { ArrowUp, Square } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onStop: () => void;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  max: number;
  busy: boolean; // waiting or streaming
  countdown: number; // seconds until sending is allowed again
  offline: boolean;
  unavailable: boolean;
}

export function Composer({ value, onChange, onSend, onStop, inputRef, max, busy, countdown, offline, unavailable }: Props) {
  const len = value.length;
  const over = len > max;
  const empty = !value.trim();
  const canSend = !empty && !over && !busy && !countdown && !offline && !unavailable;

  // Auto-grow up to ~6 lines.
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 136)}px`;
  }, [value, inputRef]);

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key !== "Enter" || e.shiftKey || e.nativeEvent.isComposing || e.keyCode === 229) return;
    e.preventDefault();
    if (canSend) onSend();
  };
  const onPaste = (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const t = e.clipboardData.getData("text");
    if (!t || t === t.trim()) return;
    e.preventDefault();
    const el = e.currentTarget;
    el.setRangeText(t.trim(), el.selectionStart, el.selectionEnd, "end");
    onChange(el.value);
  };

  const showCount = len >= max * 0.85;
  const label = countdown ? `Wait ${countdown}s` : "Send";
  return (
    <div className="border-t bg-card px-3 pt-2.5 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
      {busy && (
        <div className="mb-2 flex justify-center">
          <button
            type="button"
            onClick={onStop}
            className="inline-flex h-8 items-center gap-1.5 rounded-full border bg-background px-3 text-xs font-medium shadow-xs transition hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Square className="size-3 fill-current" /> Stop generating
          </button>
        </div>
      )}
      <div
        className={cn(
          "flex items-end gap-2 rounded-2xl border bg-background p-1.5 pl-3.5 transition-shadow focus-within:border-primary/60 focus-within:ring-3 focus-within:ring-primary/15",
          over && "border-destructive focus-within:border-destructive focus-within:ring-destructive/20",
        )}
      >
        <textarea
          ref={inputRef}
          rows={1}
          value={value}
          disabled={unavailable}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
          aria-label="Message the assistant"
          aria-invalid={over || undefined}
          placeholder={unavailable ? "Assistant unavailable" : "Ask a question…"}
          className="max-h-[136px] min-h-9 flex-1 resize-none bg-transparent py-1.5 text-[16px] leading-6 outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed sm:text-sm"
        />
        <button
          type="button"
          onClick={() => canSend && onSend()}
          disabled={!canSend}
          aria-label={countdown ? `Send available in ${countdown} seconds` : "Send message"}
          title={countdown ? `Send available in ${countdown} seconds` : "Send (Enter)"}
          className={cn(
            "inline-flex h-9 shrink-0 items-center justify-center gap-1 rounded-full bg-primary text-primary-foreground shadow-sm transition hover:brightness-110 focus-visible:ring-3 focus-visible:ring-primary/30 disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none",
            countdown ? "min-w-[4.5rem] px-3 text-xs font-medium tabular-nums" : "w-9",
          )}
        >
          {countdown ? label : <ArrowUp className="size-4" />}
        </button>
      </div>
      <div className="mt-1.5 flex h-4 items-center justify-between px-1 text-[11px] text-muted-foreground">
        <span>Enter to send · Shift+Enter for a new line</span>
        <span className={cn("tabular-nums transition-opacity", showCount ? "opacity-100" : "opacity-0", over && "font-medium text-destructive")} aria-live="off">
          {len}/{max}
        </span>
      </div>
    </div>
  );
}
