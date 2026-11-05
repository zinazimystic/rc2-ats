"use client";
import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, CircleHelp, Info, ShieldAlert, UserCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Banner } from "@/components/ui/misc";
import type { ApplicationStatus, EvidenceStatus, Flag, ProcessingState, Verification } from "@/lib/types";
import { STATUS_LABEL, fmtScore, scoreTone } from "@/lib/format";
import { cn } from "@/lib/utils";
import { toast } from "@/lib/toast";

export function notifyError(e: unknown) {
  toast.error(e);
}

const STATUS_VARIANT: Record<ApplicationStatus, "default" | "secondary" | "success" | "destructive" | "warning" | "muted"> = {
  submitted: "muted",
  parsed: "secondary",
  ai_assessed: "default",
  recruiter_review: "warning",
  shortlisted: "success",
  interview: "default",
  selected: "success",
  rejected: "destructive",
  withdrawn: "muted",
};
export function StatusBadge({ status, label }: { status: ApplicationStatus; label?: string }) {
  return <Badge variant={STATUS_VARIANT[status]}>{label ?? STATUS_LABEL[status]}</Badge>;
}

export function ProcessingBadge({ state, error }: { state: ProcessingState; error?: string | null }) {
  if (state === "done") return null;
  if (state === "failed")
    return (
      <Badge variant="destructive" title={error ?? undefined}>
        <AlertTriangle /> Processing failed
      </Badge>
    );
  return (
    <Badge variant="warning">
      <span className="size-1.5 animate-pulse rounded-full bg-current" /> {state === "queued" ? "Queued" : "Analysing…"}
    </Badge>
  );
}

export function VerificationBadge({ v }: { v: Verification }) {
  switch (v) {
    case "verified":
      return <Badge variant="success"><CheckCircle2 /> Verified</Badge>;
    case "fuzzy":
      return <Badge variant="warning"><Info /> Approx. match</Badge>;
    case "self_reported":
      return <Badge variant="secondary"><UserCheck /> Self-reported</Badge>;
    default:
      return <Badge variant="destructive"><CircleHelp /> Unverified</Badge>;
  }
}

const EV_LABEL: Record<EvidenceStatus, [string, "success" | "warning" | "destructive" | "muted"]> = {
  evidenced: ["Evidenced", "success"],
  partial: ["Partial", "warning"],
  missing_evidence: ["No evidence", "destructive"],
  confirmed_absent: ["Confirmed absent", "muted"],
};
export function EvidenceBadge({ status }: { status: EvidenceStatus }) {
  const [l, v] = EV_LABEL[status];
  return <Badge variant={v}>{l}</Badge>;
}

export function ScoreRing({ value, size = 96, label }: { value: number | null; size?: number; label?: string }) {
  const r = (size - 10) / 2;
  const c = 2 * Math.PI * r;
  const v = value ?? 0;
  return (
    <div className="relative inline-grid place-items-center" style={{ width: size, height: size }} role="img" aria-label={`${label ?? "Score"} ${fmtScore(value)} out of 100`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={8} className="stroke-muted" />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={8} strokeLinecap="round"
          className={cn("transition-all", v >= 75 ? "stroke-success" : v >= 50 ? "stroke-warning" : "stroke-destructive")}
          strokeDasharray={c} strokeDashoffset={c - (c * Math.max(0, Math.min(100, v))) / 100}
        />
      </svg>
      <span className={cn("absolute text-xl font-semibold tabular-nums", scoreTone(value))}>{fmtScore(value)}</span>
    </div>
  );
}

export function ScoreBar({ value }: { value: number | null }) {
  return (
    <div className="flex min-w-24 items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
        <div
          className={cn("h-full rounded-full", (value ?? 0) >= 75 ? "bg-success" : (value ?? 0) >= 50 ? "bg-warning" : "bg-destructive")}
          style={{ width: `${Math.max(0, Math.min(100, value ?? 0))}%` }}
        />
      </div>
      <span className={cn("w-10 text-right text-sm font-semibold tabular-nums", scoreTone(value))}>{fmtScore(value)}</span>
    </div>
  );
}

export function FlagList({ flags }: { flags: Flag[] }) {
  if (!flags.length) return null;
  return (
    <ul className="space-y-1.5">
      {flags.map((f, i) => (
        <li key={i}>
          <Banner tone={f.severity === "critical" ? "danger" : f.severity === "warning" ? "warning" : "info"}>
            <span className="inline-flex items-start gap-2">
              <ShieldAlert className="mt-0.5 size-4 shrink-0" />
              <span>{f.message}</span>
            </span>
          </Banner>
        </li>
      ))}
    </ul>
  );
}

export function SkillChips({ skills, tone = "default", max = 6 }: { skills: string[]; tone?: "default" | "success" | "destructive"; max?: number }) {
  if (!skills.length) return <span className="text-[13px] text-muted-foreground">—</span>;
  const shown = skills.slice(0, max);
  return (
    <div className="flex flex-wrap gap-1">
      {shown.map((s) => (
        <Badge key={s} variant={tone === "default" ? "secondary" : tone}>{s}</Badge>
      ))}
      {skills.length > max && <Badge variant="muted">+{skills.length - max}</Badge>}
    </div>
  );
}

export function Stat({ label, value, icon, hint, highlight }: { label: string; value: ReactNode; icon?: ReactNode; hint?: string; highlight?: boolean }) {
  return (
    <div className={cn("rounded-2xl border p-5 shadow-soft transition-transform hover:-translate-y-0.5", highlight ? "border-transparent bg-primary text-primary-foreground" : "border-border/60 bg-card")}>
      <div className={cn("flex items-center justify-between text-sm font-medium", highlight ? "text-white/85" : "text-muted-foreground")}>
        {label}
        <span className={cn("grid size-8 place-items-center rounded-full [&_svg]:size-4", highlight ? "bg-white/20" : "bg-muted")}>{icon}</span>
      </div>
      <p className="mt-3 text-4xl font-semibold tracking-tight tabular-nums">{value}</p>
      {hint && <p className={cn("mt-2 inline-block rounded-full px-2.5 py-0.5 text-[13px] font-medium", highlight ? "bg-white/20 text-white" : "bg-success/12 text-success")}>{hint}</p>}
    </div>
  );
}

export function DateTile({ iso, className }: { iso: string; className?: string }) {
  const d = new Date(iso);
  return (
    <div className={cn("grid size-14 shrink-0 place-items-center rounded-2xl bg-primary/10 text-primary", className)} aria-hidden>
      <div className="text-center leading-none">
        <p className="text-[13px] font-semibold tracking-wide uppercase">{d.toLocaleDateString(undefined, { weekday: "short" })}</p>
        <p className="mt-0.5 text-xl font-bold tabular-nums">{d.getDate()}</p>
      </div>
    </div>
  );
}

export function MatchBadge({ score }: { score: number }) {
  const high = score >= 80;
  return (
    <span className={cn("inline-flex shrink-0 items-center rounded-full px-3 py-1 text-[13px] font-semibold tabular-nums", high ? "bg-success/15 text-success" : "bg-warning/20 text-[color-mix(in_oklab,var(--warning)_55%,var(--foreground))]")}>
      {Math.round(score)}% Match
    </span>
  );
}

export function MiniCalendar({ marked = [] }: { marked?: string[] }) {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth();
  const first = new Date(y, m, 1).getDay();
  const days = new Date(y, m + 1, 0).getDate();
  const markSet = new Set(marked.map((iso) => new Date(iso).toDateString()));
  const cells: (number | null)[] = [...Array(first).fill(null), ...Array.from({ length: days }, (_, i) => i + 1)];
  return (
    <div>
      <p className="mb-3 text-center text-sm font-semibold">{now.toLocaleDateString(undefined, { month: "long", year: "numeric" })}</p>
      <div className="grid grid-cols-7 gap-y-1 text-center text-[13px]">
        {["S", "M", "T", "W", "T", "F", "S"].map((d, i) => <span key={i} className="pb-1 font-medium text-muted-foreground">{d}</span>)}
        {cells.map((d, i) => d === null ? <span key={i} /> : (
          <span key={i} className={cn("mx-auto grid size-8 place-items-center rounded-full tabular-nums", d === now.getDate() ? "bg-primary font-semibold text-primary-foreground" : markSet.has(new Date(y, m, d).toDateString()) ? "bg-primary/10 font-semibold text-primary" : "text-foreground/80")}>{d}</span>
        ))}
      </div>
    </div>
  );
}
