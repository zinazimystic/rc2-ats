import * as React from "react";
import { AlertTriangle, Inbox, Loader2, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "./button";
import { errMsg } from "@/lib/api";

export function Skeleton({ className, ...p }: React.ComponentProps<"div">) {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} {...p} />;
}
export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("size-4 animate-spin", className)} aria-label="Loading" />;
}
export function Progress({ value, className, tone }: { value: number; className?: string; tone?: string }) {
  const v = Math.max(0, Math.min(100, value));
  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(v)}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn("h-2 w-full overflow-hidden rounded-full bg-muted", className)}
    >
      <div className={cn("h-full rounded-full transition-all", tone ?? "bg-primary")} style={{ width: `${v}%` }} />
    </div>
  );
}
export function Separator({ className }: { className?: string }) {
  return <hr className={cn("border-border", className)} />;
}
export function EmptyState({
  title,
  description,
  icon,
  action,
  className,
}: {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center gap-2 rounded-3xl border border-dashed bg-card/60 p-10 text-center", className)}>
      <div className="text-muted-foreground">{icon ?? <Inbox className="size-8" />}</div>
      <p className="font-medium">{title}</p>
      {description && <p className="max-w-md text-sm text-muted-foreground">{description}</p>}
      {action}
    </div>
  );
}
export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center gap-3 rounded-3xl border border-destructive/30 bg-destructive/5 p-8 text-center">
      <AlertTriangle className="size-7 text-destructive" />
      <p className="max-w-md text-sm">{errMsg(error)}</p>
      {retry && (
        <Button size="sm" variant="outline" onClick={retry}>
          <RefreshCw /> Retry
        </Button>
      )}
    </div>
  );
}
export function Banner({
  tone = "info",
  children,
  className,
}: {
  tone?: "info" | "warning" | "danger" | "success";
  children: React.ReactNode;
  className?: string;
}) {
  const t = {
    info: "border-primary/30 bg-primary/8",
    warning: "border-warning/50 bg-warning/12",
    danger: "border-destructive/40 bg-destructive/8",
    success: "border-success/40 bg-success/10",
  }[tone];
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cn("rounded-lg border px-3 py-2 text-sm", t, className)}>
      {children}
    </div>
  );
}
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
