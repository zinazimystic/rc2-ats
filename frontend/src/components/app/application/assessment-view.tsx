"use client";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Lightbulb, Quote, Scale, ShieldCheck, Sparkles, TrendingDown, TrendingUp } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import type { ApplicationDetailOut, AssessmentOut, FairnessOut, OverrideIn, RequirementResult } from "@/lib/types";
import { fmtScore, titleCase } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, Input, Textarea } from "@/components/ui/input";
import { Banner, Progress } from "@/components/ui/misc";
import { EvidenceBadge, FlagList, ScoreRing, notifyError } from "./../common";
import { cn } from "@/lib/utils";

function OverrideDialog({ a, app, open, onOpenChange }: { a: AssessmentOut; app: ApplicationDetailOut; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const [score, setScore] = useState(String(a.effective_score));
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const m = useMutation({
    mutationFn: (b: OverrideIn) => api<AssessmentOut>(`/applications/${app.id}/override`, { body: b }),
    onSuccess: () => { toast.success("Score overridden and logged in the audit trail"); qc.invalidateQueries({ queryKey: ["application", app.id] }); qc.invalidateQueries({ queryKey: ["applicants"] }); qc.invalidateQueries({ queryKey: ["history", app.id] }); onOpenChange(false); },
    onError: (e) => setErr(errMsg(e)),
  });
  function go() {
    const n = Number(score);
    if (!Number.isFinite(n) || n < 0 || n > 100) return setErr("Score must be between 0 and 100");
    if (reason.trim().length < 5) return setErr("A reason (at least 5 characters) is required for the audit trail");
    setErr(null);
    m.mutate({ score: Math.round(n * 10) / 10, reason: reason.trim() });
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Override AI score</DialogTitle><DialogDescription>The AI score ({fmtScore(a.total_score)}) is kept for reference. Your override and reason are audited.</DialogDescription></DialogHeader>
        {err && <Banner tone="danger">{err}</Banner>}
        <Field label="New score (0–100)" htmlFor="ov-score"><Input id="ov-score" type="number" min={0} max={100} step="0.1" value={score} onChange={(e) => setScore(e.target.value)} /></Field>
        <Field label="Reason" htmlFor="ov-reason"><Textarea id="ov-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Strong referral and relevant open-source work not in the resume" /></Field>
        <DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button><Button onClick={go} loading={m.isPending}>Apply override</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Fairness({ appId }: { appId: string }) {
  const m = useMutation({ mutationFn: () => api<FairnessOut>(`/applications/${appId}/fairness-check`, { method: "POST" }), onError: notifyError });
  const r = m.data;
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div><CardTitle className="flex items-center gap-2"><Scale className="size-4" />Fairness check</CardTitle><CardDescription className="mt-1">Re-scores with name, gender, age and nationality signals changed. A fair model must not move.</CardDescription></div>
          <Button variant="outline" size="sm" loading={m.isPending} onClick={() => m.mutate()}><ShieldCheck /> Run counterfactual check</Button>
        </div>
      </CardHeader>
      {r && (
        <CardContent className="space-y-3">
          <Banner tone={r.passed ? "success" : "danger"}>{r.passed ? "Passed" : "Failed"} — baseline {fmtScore(r.baseline_score)}, max change {r.max_abs_delta.toFixed(2)} points. {r.note}</Banner>
          <ul className="divide-y text-sm">
            {r.variants.map((v) => (
              <li key={v.name} className="flex items-center justify-between gap-2 py-2">
                <div><p className="font-medium">{titleCase(v.name)}</p><p className="text-xs text-muted-foreground">{v.description}</p></div>
                <div className="text-right"><p className="tabular-nums">{fmtScore(v.score)} <span className={v.delta === 0 ? "text-success" : "text-destructive"}>({v.delta > 0 ? "+" : ""}{v.delta.toFixed(2)})</span></p>{v.model_input_identical && <p className="text-xs text-muted-foreground">identical model input</p>}</div>
              </li>
            ))}
          </ul>
        </CardContent>
      )}
    </Card>
  );
}

function ReqRow({ r, onJump }: { r: RequirementResult; onJump: (key: string) => void }) {
  return (
    <li className="space-y-1.5 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{r.skill}</span>
        <Badge variant={r.kind === "required" ? "default" : "secondary"}>{r.kind}</Badge>
        <span className="text-xs text-muted-foreground">imp. {r.importance}</span>
        <EvidenceBadge status={r.status} />
        {r.match_type !== "none" && <Badge variant="outline">{titleCase(r.match_type)}{r.matched_as && r.matched_as.toLowerCase() !== r.skill.toLowerCase() ? ` → ${r.matched_as}` : ""}</Badge>}
        <span className="ml-auto text-sm font-semibold tabular-nums">{Math.round(r.credit * 100)}%</span>
      </div>
      <Progress value={r.credit * 100} tone={r.credit >= 0.75 ? "bg-success" : r.credit >= 0.4 ? "bg-warning" : "bg-destructive"} className="h-1.5" />
      <p className="text-sm text-muted-foreground">{r.explanation}</p>
      {r.evidence.map((e, i) => (
        <button key={i} onClick={() => onJump(`req:${r.skill}:${i}`)} className="flex w-full items-start gap-2 rounded-md border bg-muted/40 p-2 text-left text-xs transition-colors hover:border-primary" title="Show in resume">
          <Quote className="mt-0.5 size-3 shrink-0 text-muted-foreground" />
          <span className="italic">“{e.quote}”</span>
          {e.similarity != null && <Badge variant="muted" className="ml-auto shrink-0">sim {e.similarity.toFixed(2)}</Badge>}
        </button>
      ))}
    </li>
  );
}

export function AssessmentView({ app, onJump }: { app: ApplicationDetailOut; onJump: (key: string) => void }) {
  const [ovr, setOvr] = useState(false);
  const a = app.assessment;
  const qc = useQueryClient();
  const reprocess = useMutation({
    mutationFn: () => api(`/applications/${app.id}/reprocess`, { method: "POST" }),
    onSuccess: () => { toast.success("Re-assessment queued"); qc.invalidateQueries({ queryKey: ["application", app.id] }); },
    onError: notifyError,
  });
  if (!a)
    return (
      <Banner tone={app.processing_state === "failed" ? "danger" : "info"}>
        {app.processing_state === "failed" ? <>AI assessment failed{app.processing_error ? `: ${app.processing_error}` : ""}. You can retry, or review the resume manually and move the application forward.</> : "The AI assessment is being prepared — this page updates automatically."}
        {app.processing_state === "failed" && <Button size="sm" variant="outline" className="ml-3" loading={reprocess.isPending} onClick={() => reprocess.mutate()}>Retry</Button>}
      </Banner>
    );
  const comps = Object.entries(a.components);
  return (
    <div className="space-y-4">
      {a.stale && <Banner tone="warning">This assessment is based on an older version of the job. Re-scoring is in progress.</Banner>}
      {!a.semantic_available && <Banner tone="warning">Semantic matching (embeddings) was unavailable — only keyword and alias matches were used, so related skills may be under-credited.</Banner>}
      {a.summary_method === "rules" || a.summary_method === "template" ? <Banner tone="info">The narrative summary was generated from templates (LLM unavailable). Scores are unaffected — they are always computed deterministically.</Banner> : null}
      <FlagList flags={a.flags} />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardContent className="flex flex-col items-center gap-3 pt-5 text-center">
            <ScoreRing value={a.effective_score} size={128} label="Effective score" />
            <div className="text-sm">
              {a.override_score != null ? <><Badge variant="warning">Recruiter override</Badge><p className="mt-1 text-xs text-muted-foreground">AI score {fmtScore(a.total_score)} · “{a.override_reason}”</p></> : <p className="text-muted-foreground">AI relevance score</p>}
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => setOvr(true)}>Override</Button>
              <Button size="sm" variant="ghost" loading={reprocess.isPending} onClick={() => reprocess.mutate()}>Re-assess</Button>
            </div>
          </CardContent>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader><CardTitle>Score breakdown</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {comps.map(([k, c]) => (
              <div key={k} className={cn(!c.applicable && "opacity-60")}>
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span className="font-medium">{titleCase(k)} <span className="text-xs font-normal text-muted-foreground">weight {c.weight}%</span></span>
                  <span className="tabular-nums">{c.applicable ? `${fmtScore(c.score)} → ${c.points.toFixed(1)} pts` : "not applicable"}</span>
                </div>
                <Progress value={c.score} tone={c.score >= 75 ? "bg-success" : c.score >= 50 ? "bg-warning" : "bg-destructive"} />
                {c.details && Object.keys(c.details).length > 0 && (
                  <p className="mt-1 text-xs text-muted-foreground">{Object.entries(c.details).filter(([, v]) => ["string", "number", "boolean"].includes(typeof v)).map(([dk, dv]) => `${titleCase(dk)}: ${String(dv)}`).join(" · ")}</p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {a.summary && (
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Sparkles className="size-4 text-primary" />AI summary</CardTitle></CardHeader>
          <CardContent><p className="text-sm">{a.summary}</p>{a.summary_method && <p className="mt-2 text-xs text-muted-foreground">Generated by {a.summary_method}</p>}</CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <Card><CardHeader><CardTitle className="flex items-center gap-2 text-success"><TrendingUp className="size-4" />Strengths</CardTitle></CardHeader><CardContent><ul className="list-disc space-y-1 pl-4 text-sm">{a.strengths.length ? a.strengths.map((s, i) => <li key={i}>{s}</li>) : <li className="list-none text-muted-foreground">None identified</li>}</ul></CardContent></Card>
        <Card><CardHeader><CardTitle className="flex items-center gap-2 text-destructive"><TrendingDown className="size-4" />Gaps</CardTitle></CardHeader><CardContent><ul className="list-disc space-y-1 pl-4 text-sm">{a.gaps.length ? a.gaps.map((s, i) => <li key={i}>{s}</li>) : <li className="list-none text-muted-foreground">No gaps</li>}</ul></CardContent></Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Requirement evidence</CardTitle><CardDescription>Credit is awarded only for evidence that was verified verbatim in the resume. Click a quote to see it in context.</CardDescription></CardHeader>
        <CardContent><ul className="divide-y">{a.requirements.map((r, i) => <ReqRow key={`${r.skill}-${i}`} r={r} onJump={onJump} />)}</ul></CardContent>
      </Card>

      {a.learning_suggestions.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><Lightbulb className="size-4 text-warning" />Learning suggestions</CardTitle></CardHeader>
          <CardContent><ul className="space-y-2 text-sm">{a.learning_suggestions.map((l) => <li key={l.skill}><strong>{l.skill}:</strong> {l.suggestion}</li>)}</ul></CardContent>
        </Card>
      )}
      <Fairness appId={app.id} />
      <OverrideDialog key={String(ovr)} a={a} app={app} open={ovr} onOpenChange={setOvr} />
    </div>
  );
}
