"use client";
import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, CircleHelp, Info, ShieldAlert, UserCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Banner } from "@/components/ui/misc";
import type { ApplicationStatus, EvidenceStatus, Flag, ProcessingState, Verification } from "@/lib/types";
import { STATUS_LABEL, fmtScore, scoreTone } from "@/lib/format";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { errMsg } from "@/lib/api";

export function notifyError(e: unknown) {
  toast.error(errMsg(e));
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
  if (!skills.length) return <span className="text-xs text-muted-foreground">—</span>;
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

export function Stat({ label, value, icon, hint }: { label: string; value: ReactNode; icon?: ReactNode; hint?: string }) {
  return (
    <div className="rounded-xl border bg-card p-4 shadow-xs">
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        {label}
        <span className="[&_svg]:size-4">{icon}</span>
      </div>
      <p className="mt-2 text-2xl font-semibold tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
