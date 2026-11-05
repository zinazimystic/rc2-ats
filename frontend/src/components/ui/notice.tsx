"use client";
import * as React from "react";
import { AlertTriangle, CheckCircle2, Info, Loader2, X, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "./button";

export type NoticeTone = "info" | "success" | "warning" | "error";

const TONE: Record<NoticeTone, { bar: string; bg: string; chip: string; icon: React.ReactNode }> = {
  info: { bar: "bg-primary", bg: "bg-primary/6", chip: "bg-primary/15 text-primary", icon: <Info /> },
  success: { bar: "bg-success", bg: "bg-success/8", chip: "bg-success/15 text-success", icon: <CheckCircle2 /> },
  warning: { bar: "bg-warning", bg: "bg-warning/10", chip: "bg-warning/25 text-[color-mix(in_oklab,var(--warning)_60%,var(--foreground))]", icon: <AlertTriangle /> },
  error: { bar: "bg-destructive", bg: "bg-destructive/6", chip: "bg-destructive/15 text-destructive", icon: <XCircle /> },
};

export interface NoticeProps {
  tone?: NoticeTone;
  title?: React.ReactNode;
  children?: React.ReactNode;
  action?: { label: string; onClick: () => void; loading?: boolean; disabled?: boolean };
  onDismiss?: () => void;
  className?: string;
}

/** Persistent, page-level message: accent bar, icon chip, title + short text, optional action. */
export function Notice({ tone = "info", title, children, action, onDismiss, className }: NoticeProps) {
  const t = TONE[tone];
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn("relative flex items-start gap-3 overflow-hidden rounded-2xl border border-border/60 py-3 pr-3 pl-5 text-sm", t.bg, className)}
    >
      <span className={cn("absolute inset-y-0 left-0 w-1.5", t.bar)} aria-hidden />
      <span className={cn("mt-0.5 grid size-6 shrink-0 place-items-center rounded-full [&_svg]:size-3.5", t.chip)} aria-hidden>
        {action?.loading ? <Loader2 className="animate-spin" /> : t.icon}
      </span>
      <div className="min-w-0 flex-1">
        {title && <p className="leading-snug font-semibold">{title}</p>}
        {children && <div className={cn("leading-snug text-foreground/80", title && "mt-0.5 text-[13px]")}>{children}</div>}
      </div>
      {action && (
        <Button size="sm" variant="outline" className="shrink-0 self-center" loading={action.loading} disabled={action.disabled} onClick={action.onClick}>
          {action.label}
        </Button>
      )}
      {onDismiss && (
        <button type="button" onClick={onDismiss} aria-label="Dismiss" className="shrink-0 self-start rounded-full p-1 text-muted-foreground hover:bg-black/5 hover:text-foreground dark:hover:bg-white/10">
          <X className="size-4" />
        </button>
      )}
    </div>
  );
}
