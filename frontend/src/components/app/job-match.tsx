"use client";
import { useState } from "react";
import Link from "next/link";
import { Lightbulb, Loader2, Sparkles } from "lucide-react";
import { useMyMatch } from "@/lib/queries";
import { fmtScore, scoreBg, scoreTone } from "@/lib/format";
import type { MyMatchOut, ResumeOut } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/misc";
import { Notice } from "@/components/ui/notice";
import { cn } from "@/lib/utils";
import { EvidenceBadge, ScoreRing } from "./common";
import { BAND_LABEL, ResumePicker, bandTone } from "./resume-picker";
import { isBusy } from "./resume-manager";

const COMPONENTS: [keyof MyMatchOut["components"], string][] = [
  ["skills", "Skills"],
  ["experience", "Experience"],
  ["projects", "Projects"],
  ["qualifications", "Qualifications"],
];

export function MatchSkeleton() {
  return (
    <div className="space-y-4" aria-hidden>
      <div className="flex items-center gap-5"><Skeleton className="size-24 rounded-full" /><div className="flex-1 space-y-2"><Skeleton className="h-5 w-40" /><Skeleton className="h-3 w-full" /><Skeleton className="h-3 w-4/5" /></div></div>
      <Skeleton className="h-24 w-full rounded-2xl" />
    </div>
  );
}

export function MatchBars({ components }: { components: MyMatchOut["components"] }) {
  const rows = COMPONENTS.filter(([k]) => components[k] !== null && components[k] !== undefined);
  return (
    <ul className="min-w-0 flex-1 space-y-2.5">
      {rows.map(([k, label]) => {
        const v = components[k] as number;
        return (
          <li key={k}>
            <div className="mb-1 flex justify-between text-[13px]"><span className="font-medium">{label}</span><span className={cn("font-semibold tabular-nums", scoreTone(v))}>{fmtScore(v)}</span></div>
            <div className="h-1.5 overflow-hidden rounded-full bg-muted" role="progressbar" aria-label={label} aria-valuenow={Math.round(v)} aria-valuemin={0} aria-valuemax={100}>
              <div className={cn("h-full rounded-full", scoreBg(v))} style={{ width: `${Math.max(0, Math.min(100, v))}%` }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function WorkOn({ m }: { m: MyMatchOut }) {
  const [done, setDone] = useState<Record<string, boolean>>({});
  const items = [...(m.improvements ?? []).map((i) => ({ key: `i-${i.skill}`, title: i.skill, text: i.suggestion })), ...(m.tips ?? []).map((t, idx) => ({ key: `t-${idx}`, title: null as string | null, text: t }))];
  if (items.length === 0) return null;
  return (
    <section aria-labelledby="work-on">
      <h3 id="work-on" className="mb-2 flex items-center gap-2 text-sm font-semibold"><Lightbulb className="size-4 text-warning" /> What to work on</h3>
      <ul className="space-y-2">
        {items.map((it) => (
          <li key={it.key}>
            <label className="flex cursor-pointer items-start gap-2.5 rounded-xl bg-muted/50 p-3 text-sm">
              <Checkbox className="mt-0.5" checked={!!done[it.key]} onChange={(e) => setDone({ ...done, [it.key]: e.target.checked })} />
              <span className={cn(done[it.key] && "text-muted-foreground line-through")}>{it.title && <strong className="font-semibold">{it.title}: </strong>}{it.text}</span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}

function MatchBody({ m }: { m: MyMatchOut }) {
  const reqs = m.requirements ?? [];
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-6">
        <div className="flex items-center gap-4">
          <ScoreRing value={m.score} label="Estimated fit" />
          <div>
            <p className={cn("text-lg font-semibold", bandTone(m.band))}>{BAND_LABEL[m.band] ?? "Estimated fit"}</p>
            <p className="max-w-[14rem] text-[13px] text-muted-foreground">Estimated fit based on your resume. The employer’s review may differ.</p>
          </div>
        </div>
        <div className="flex min-w-48 flex-1"><MatchBars components={m.components} /></div>
      </div>

      {reqs.length > 0 && (
        <section aria-labelledby="req-h">
          <h3 id="req-h" className="mb-2 text-sm font-semibold">How you line up</h3>
          <ul className="divide-y rounded-2xl border">
            {reqs.map((r) => (
              <li key={r.skill + r.kind} className="flex flex-wrap items-start gap-x-3 gap-y-1 px-3.5 py-2.5 text-sm">
                <span className="font-medium">{r.skill}</span>
                {r.kind === "preferred" && <Badge variant="muted">Nice to have</Badge>}
                {r.matched_as && r.matched_as.toLowerCase() !== r.skill.toLowerCase() && <span className="text-[13px] text-muted-foreground">via {r.matched_as}</span>}
                <span className="ml-auto"><EvidenceBadge status={r.status} /></span>
                {r.evidence && <p className="w-full truncate text-[13px] text-muted-foreground italic" title={r.evidence}>“{r.evidence}”</p>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {(m.strengths?.length ?? 0) > 0 && (
        <section><h3 className="mb-2 text-sm font-semibold">Your strengths</h3><ul className="space-y-1 text-sm">{m.strengths.map((s, i) => <li key={i} className="flex gap-2"><span className="mt-2 size-1.5 shrink-0 rounded-full bg-success" />{s}</li>)}</ul></section>
      )}
      <WorkOn m={m} />
    </div>
  );
}

/** The candidate's own estimate of fit for a job, based on one of their resumes. */
export function MyMatchCard({ jobId, resumes, resumeId, onResumeChange, onUpload }: { jobId: string; resumes: ResumeOut[]; resumeId: string | null; onResumeChange: (id: string) => void; onUpload: () => void }) {
  const selected = resumes.find((r) => r.id === resumeId) ?? null;
  const parsed = resumes.filter((r) => r.parse_status === "parsed");
  const noResume = resumes.length === 0;
  const reading = !!selected && isBusy(selected);
  const m = useMyMatch(jobId, resumeId, !!selected && selected.parse_status === "parsed");
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3">
        <div>
          <CardTitle className="flex items-center gap-2"><Sparkles className="size-4 text-primary" /> Your match</CardTitle>
          <CardDescription>{selected ? <>Based on <strong className="font-medium text-foreground">{selected.filename}</strong></> : "See how your resume lines up with this role."}</CardDescription>
        </div>
        {!noResume && <ResumePicker jobId={jobId} resumes={resumes} value={resumeId} onChange={onResumeChange} onUpload={onUpload} label="Change resume" />}
      </CardHeader>
      <CardContent>
        {noResume ? (
          <Notice tone="info" title="Upload a resume to see your match" action={{ label: "Upload resume", onClick: onUpload }}>We’ll estimate how well your experience fits this role and what to work on.</Notice>
        ) : reading ? (
          <div className="flex items-center gap-3 rounded-2xl bg-muted/50 p-4 text-sm" role="status"><Loader2 className="size-5 animate-spin text-primary" /> Reading your resume. Your match will appear in a moment.</div>
        ) : parsed.length === 0 ? (
          <Notice tone="warning" title="We couldn’t read your resume">Open your profile to re-parse it or upload a different file. <Link href="/candidate/resume" className="font-medium underline">Go to resumes</Link></Notice>
        ) : m.isError ? (
          <Notice tone="warning" title="Your match isn’t available right now" action={{ label: "Try again", onClick: () => m.refetch(), loading: m.isFetching }}>You can still apply. We just couldn’t estimate the fit this time.</Notice>
        ) : !m.data ? (
          <MatchSkeleton />
        ) : m.data.needs_resume ? (
          <Notice tone="info" title="Choose a resume to see your match" action={{ label: "Upload resume", onClick: onUpload }} />
        ) : (
          <MatchBody m={m.data} />
        )}
        {m.data && !m.isError && <Button asChild variant="link" size="sm" className="mt-2 px-0"><Link href="/candidate/resume">Improve your resume</Link></Button>}
      </CardContent>
    </Card>
  );
}
