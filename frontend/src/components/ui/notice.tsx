"use client";
import * as React from "react";
import { AlertTriangle, CheckCircle2, Info, Loader2, X, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "./button";

export type NoticeTone = "info" | "success" | "warning" | "error";

const TONE: Record<NoticeTone, { icon: React.ReactNode; color: string }> = {
  info: { icon: <Info />, color: "text-primary" },
  success: { icon: <CheckCircle2 />, color: "text-success" },
  warning: { icon: <AlertTriangle />, color: "text-warning" },
  error: { icon: <XCircle />, color: "text-destructive" },
};

export interface NoticeProps {
  tone?: NoticeTone;
  title?: React.ReactNode;
  children?: React.ReactNode;
  action?: { label: string; onClick: () => void; loading?: boolean; disabled?: boolean };
  onDismiss?: () => void;
  className?: string;
}

/** Restrained card for persistent, actionable states only (use toasts for transient feedback). */
export function Notice({ tone = "info", title, children, action, onDismiss, className }: NoticeProps) {
  const t = TONE[tone];
  return (
    <div role={tone === "error" ? "alert" : "status"} className={cn("flex items-start gap-3 rounded-2xl border border-border bg-card p-4 text-sm shadow-soft", className)}>
      <span className={cn("mt-0.5 shrink-0 [&_svg]:size-5", t.color)} aria-hidden>{action?.loading ? <Loader2 className="animate-spin" /> : t.icon}</span>
      <div className="min-w-0 flex-1 space-y-0.5">
        {title && <p className="text-[15px] leading-snug font-semibold">{title}</p>}
        {children && <div className="text-sm leading-relaxed text-muted-foreground">{children}</div>}
      </div>
      {action && <Button size="sm" variant="outline" className="shrink-0 self-center" loading={action.loading} disabled={action.disabled} onClick={action.onClick}>{action.label}</Button>}
      {onDismiss && (
        <button type="button" onClick={onDismiss} aria-label="Dismiss" className="shrink-0 rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-foreground"><X className="size-4" /></button>
      )}
    </div>
  );
}
