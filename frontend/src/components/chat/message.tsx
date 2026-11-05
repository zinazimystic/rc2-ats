"use client";
import { memo, useState } from "react";
import { Check, Copy, RefreshCw, RotateCcw, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { Markdown } from "./markdown";
import { Typing } from "./typing";
import { copyText } from "./clipboard";
import type { ChatMessage } from "./types";

export function Avatar({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn("inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#2f6bff] to-[#7c5cff] text-white shadow-sm", className)}
    >
      <Sparkles className="size-4" />
    </span>
  );
}

function rel(ts: number) {
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return new Date(ts).toLocaleDateString();
}
function Time({ ts, className }: { ts: number; className?: string }) {
  return (
    <time
      dateTime={new Date(ts).toISOString()}
      title={new Date(ts).toLocaleString()}
      className={cn("text-[11px] text-muted-foreground tabular-nums opacity-0 transition-opacity group-focus-within/msg:opacity-100 group-hover/msg:opacity-100", className)}
      suppressHydrationWarning
    >
      {rel(ts)}
    </time>
  );
}

const iconBtn =
  "inline-flex h-7 items-center gap-1 rounded-full px-2 text-[11px] font-medium text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50";

interface Props {
  m: ChatMessage;
  waiting: boolean; // assistant placeholder with no tokens yet
  canRegenerate: boolean;
  disabled: boolean;
  onRegenerate: () => void;
  onRetry: () => void;
  onNavigate: () => void;
}

function MessageImpl({ m, waiting, canRegenerate, disabled, onRegenerate, onRetry, onNavigate }: Props) {
  const [copied, setCopied] = useState(false);
  if (m.role === "user") {
    return (
      <div className="rc-msg group/msg flex flex-col items-end gap-0.5">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-3.5 py-2 text-sm whitespace-pre-wrap text-primary-foreground shadow-sm [overflow-wrap:anywhere]">
          {m.content}
        </div>
        <Time ts={m.ts} />
      </div>
    );
  }
  const streaming = m.status === "streaming";
  return (
    <div className="rc-msg group/msg flex items-start gap-2">
      <Avatar className="mt-0.5" />
      <div className="min-w-0 max-w-[88%]">
        <div className="rounded-2xl rounded-tl-md border bg-card px-3.5 py-2.5 shadow-xs">
          {waiting ? <Typing /> : <Markdown text={m.content} streaming={streaming} onNavigate={onNavigate} />}
          {m.status === "stopped" && <p className="mt-1.5 text-[11px] text-muted-foreground italic">Stopped</p>}
          {m.status === "interrupted" && (
            <div className="mt-2 flex items-center gap-2 text-[11px] text-muted-foreground">
              <span className="italic">Reply interrupted</span>
              <button type="button" onClick={onRetry} disabled={disabled} className={cn(iconBtn, "border text-foreground")}>
                <RotateCcw className="size-3" /> Retry
              </button>
            </div>
          )}
          {m.finish === "length" && m.status === "done" && <p className="mt-1.5 text-[11px] text-muted-foreground italic">Reply was cut short.</p>}
        </div>
        {!waiting && !streaming && (
          <div className="mt-0.5 flex items-center gap-1 pl-1">
            <button
              type="button"
              aria-label={copied ? "Copied" : "Copy reply"}
              title={copied ? "Copied" : "Copy reply"}
              className={iconBtn}
              onClick={async () => {
                if (await copyText(m.content)) {
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1500);
                }
              }}
            >
              {copied ? <Check className="size-3 text-success" /> : <Copy className="size-3" />}
              {copied ? "Copied" : "Copy"}
            </button>
            {canRegenerate && (
              <button type="button" aria-label="Regenerate reply" title="Regenerate reply" className={iconBtn} onClick={onRegenerate} disabled={disabled}>
                <RefreshCw className="size-3" /> Regenerate
              </button>
            )}
            <Time ts={m.ts} className="ml-1" />
          </div>
        )}
      </div>
    </div>
  );
}
export const Message = memo(MessageImpl);
