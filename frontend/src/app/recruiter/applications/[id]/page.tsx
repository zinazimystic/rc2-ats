"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Check, CircleX, RotateCcw } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import type { ApplicationDetailOut, ApplicationStatus, Evidence } from "@/lib/types";
import { STATUS_LABEL, fmtDate } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, Textarea } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Banner, ErrorState, Skeleton } from "@/components/ui/misc";
import { ProcessingBadge, StatusBadge } from "@/components/app/common";
import { AssessmentView } from "@/components/app/application/assessment-view";
import { ResumeView } from "@/components/app/application/resume-view";
import { QuestionsTab } from "@/components/app/application/questions-tab";
import { InterviewsTab } from "@/components/app/application/interviews-tab";
import { HistoryTab, NotesTab } from "@/components/app/application/notes-history";


function TransitionDialog({ app, to, onClose }: { app: ApplicationDetailOut; to: ApplicationStatus; onClose: () => void }) {
  const qc = useQueryClient();
  const reconsider = app.status === "rejected" && to === "recruiter_review";
  const required = to === "rejected" || reconsider;
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const m = useMutation({
    mutationFn: () => api<ApplicationDetailOut>(`/applications/${app.id}/transition`, { body: { to_status: to, reason: reason.trim() || null } }),
    onSuccess: (d) => {
      qc.setQueryData(["application", app.id], d);
      ["applicants", "analytics", "history"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      toast.success(`Moved to ${STATUS_LABEL[to]} — candidate notified`);
      onClose();
    },
    onError: (e) => setErr(errMsg(e)),
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>{reconsider ? "Reconsider candidate" : `Move to ${STATUS_LABEL[to]}`}</DialogTitle><DialogDescription>{app.candidate.full_name} · {STATUS_LABEL[app.status]} → {STATUS_LABEL[to]}</DialogDescription></DialogHeader>
        {err && <Banner tone="danger">{err}</Banner>}
        <Field label={required ? "Reason (required)" : "Note (optional)"} htmlFor="tr-reason"><Textarea id="tr-reason" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button variant={to === "rejected" ? "destructive" : "default"} loading={m.isPending} onClick={() => (required && reason.trim().length < 3 ? setErr("Please give a short reason") : m.mutate())}>Confirm</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function ApplicationPage() {
  const { id } = useParams<{ id: string }>();
  const [tab, setTab] = useState("assessment");
  const [active, setActive] = useState<string | null>(null);
  const [to, setTo] = useState<ApplicationStatus | null>(null);
  const q = useQuery({
    queryKey: ["application", id],
    queryFn: () => api<ApplicationDetailOut>(`/applications/${id}`),
    refetchInterval: (query) => (["queued", "processing"].includes(query.state.data?.processing_state ?? "") ? 2000 : false),
  });
  const a = q.data;
  const evidence = useMemo(() => {
    const out: (Evidence & { key: string })[] = [];
    a?.assessment?.requirements.forEach((r) => r.evidence.forEach((e, i) => out.push({ ...e, key: `req:${r.skill}:${i}` })));
    return out;
  }, [a]);

  if (q.isError) return <ErrorState error={q.error} retry={() => q.refetch()} />;
  if (!a) return <Skeleton className="h-96" />;

  const jump = (key: string) => { setActive(key); setTab("resume"); };
  const t = a.allowed_transitions;
  const btn = (s: ApplicationStatus) => {
    const reconsider = a.status === "rejected" && s === "recruiter_review";
    if (s === "rejected") return <Button key={s} variant="outline" className="text-destructive" onClick={() => setTo(s)}><CircleX /> Reject</Button>;
    if (s === "shortlisted") return <Button key={s} variant="success" onClick={() => setTo(s)}><Check /> Shortlist</Button>;
    if (reconsider) return <Button key={s} variant="outline" onClick={() => setTo(s)}><RotateCcw /> Reconsider</Button>;
    return <Button key={s} variant="outline" onClick={() => setTo(s)}>{STATUS_LABEL[s]}</Button>;
  };

  return (
    <>
      <Button variant="ghost" size="sm" asChild className="mb-2 -ml-2"><Link href={`/recruiter/jobs/${a.job.id}`}><ArrowLeft /> {a.job.title}</Link></Button>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="flex flex-wrap items-center gap-3 text-2xl font-semibold tracking-tight">{a.candidate.full_name}<StatusBadge status={a.status} /><ProcessingBadge state={a.processing_state} error={a.processing_error} />{a.is_duplicate && <Badge variant="warning">Possible duplicate</Badge>}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{[a.candidate.headline, a.candidate.email, a.candidate.location].filter(Boolean).join(" · ")} · Applied {fmtDate(a.applied_at)}</p>
          {a.cover_note && <p className="mt-2 max-w-2xl rounded-md border bg-muted/40 p-2 text-sm italic">“{a.cover_note}”</p>}
        </div>
        <div className="flex flex-wrap gap-2">{t.map(btn)}</div>
      </div>
      {a.status === "withdrawn" && <Banner tone="warning" className="mb-4">The candidate withdrew this application.</Banner>}
      {a.processing_state !== "done" && a.processing_state !== "failed" && <Banner tone="info" className="mb-4">AI analysis in progress — this page refreshes automatically.</Banner>}
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="assessment">Assessment</TabsTrigger>
          <TabsTrigger value="resume">Resume</TabsTrigger>
          <TabsTrigger value="questions">Questions</TabsTrigger>
          <TabsTrigger value="interviews">Interviews ({a.interviews.length})</TabsTrigger>
          <TabsTrigger value="notes">Notes ({a.notes_count})</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>
        <TabsContent value="assessment"><AssessmentView app={a} onJump={jump} /></TabsContent>
        <TabsContent value="resume">
          {a.resume ? <ResumeView resume={a.resume} evidence={evidence} activeKey={active} /> : <Banner tone="warning">No resume attached to this application.</Banner>}
        </TabsContent>
        <TabsContent value="questions"><QuestionsTab appId={id} /></TabsContent>
        <TabsContent value="interviews"><InterviewsTab appId={id} canSchedule={a.status === "shortlisted" || a.status === "interview"} /></TabsContent>
        <TabsContent value="notes"><NotesTab appId={id} /></TabsContent>
        <TabsContent value="history"><HistoryTab appId={id} /></TabsContent>
      </Tabs>
      {to && <TransitionDialog key={to} app={a} to={to} onClose={() => setTo(null)} />}
    </>
  );
}
