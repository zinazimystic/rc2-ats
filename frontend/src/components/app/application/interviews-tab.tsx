"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { CalendarPlus, MessageSquareText } from "lucide-react";
import { api, ApiError, errMsg } from "@/lib/api";
import type { ConflictErrorOut, ConflictOut, FeedbackIn, InterviewIn, InterviewOut, InterviewType, Recommendation } from "@/lib/types";
import { fmtDateTime, titleCase, toLocalInput } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { Banner, EmptyState, ErrorState, Skeleton } from "@/components/ui/misc";
import { cn } from "@/lib/utils";
import { DateTile } from "@/components/app/common";
import { InterviewDetailDialog, InterviewStatusPill } from "@/components/app/application/interview-detail";

const TYPES: InterviewType[] = ["technical", "hr", "behavioral", "panel", "final"];

export function ScheduleDialog({ appId, existing, open, onOpenChange }: { appId: string; existing?: InterviewOut; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const [f, setF] = useState(() => {
    const start = existing ? new Date(existing.start_at) : new Date(Date.now() + 86_400_000);
    if (!existing) { start.setMinutes(0, 0, 0); start.setHours(10); }
    return {
      name: existing?.interviewer_name ?? "", email: existing?.interviewer_email ?? "", type: (existing?.interview_type ?? "technical") as InterviewType,
      start: toLocalInput(start), dur: existing ? String(Math.round((+new Date(existing.end_at) - +new Date(existing.start_at)) / 60000)) : "45",
      location: existing?.location ?? "", notes: existing?.notes ?? "",
    };
  });
  const [err, setErr] = useState<string | null>(null);
  const [conflicts, setConflicts] = useState<ConflictOut[]>([]);
  const m = useMutation({
    mutationFn: (force: boolean) => {
      const body: InterviewIn = {
        interviewer_name: f.name.trim(), interviewer_email: f.email.trim() || null, interview_type: f.type,
        start_at: new Date(f.start).toISOString(), duration_minutes: Number(f.dur), location: f.location.trim() || null, notes: f.notes.trim() || null, force,
      };
      return existing ? api<InterviewOut>(`/interviews/${existing.id}`, { method: "PATCH", body }) : api<InterviewOut>(`/applications/${appId}/interviews`, { body });
    },
    onSuccess: (iv) => {
      toast.success(iv.has_conflict ? "Scheduled with conflicts" : existing ? "Interview rescheduled" : "Interview scheduled — candidate notified");
      ["application", "interviews"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      qc.invalidateQueries({ queryKey: ["applicants"] }); qc.invalidateQueries({ queryKey: ["analytics"] });
      onOpenChange(false);
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 409) {
        setConflicts((e.body as ConflictErrorOut).conflicts ?? []);
        setErr(null);
      } else { setConflicts([]); setErr(errMsg(e)); }
    },
  });
  function submit(force: boolean) {
    const d = Number(f.dur);
    if (f.name.trim().length < 2) return setErr("Interviewer name is required");
    if (f.email && !/^\S+@\S+\.\S+$/.test(f.email)) return setErr("Enter a valid interviewer email");
    if (!f.start || isNaN(+new Date(f.start))) return setErr("Choose a valid date and time");
    if (!existing && new Date(f.start) < new Date()) return setErr("Start time is in the past");
    if (!Number.isFinite(d) || d < 15 || d > 480) return setErr("Duration must be 15–480 minutes");
    setErr(null);
    m.mutate(force);
  }
  const set = (k: keyof typeof f, v: string) => { setF({ ...f, [k]: v }); setConflicts([]); };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>{existing ? "Reschedule interview" : "Schedule interview"}</DialogTitle><DialogDescription>Times are in your local timezone. Conflicts are checked for the interviewer and candidate.</DialogDescription></DialogHeader>
        {err && <Banner tone="danger">{err}</Banner>}
        {conflicts.length > 0 && (
          <Banner tone="warning" className="space-y-1">
            <p className="font-medium">Schedule conflict</p>
            <ul className="list-disc pl-4">{conflicts.map((c, i) => <li key={i}>{c.message} ({fmtDateTime(c.start_at)})</li>)}</ul>
          </Banner>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Interviewer *" htmlFor="iv-name"><Input id="iv-name" value={f.name} onChange={(e) => set("name", e.target.value)} /></Field>
          <Field label="Interviewer email" htmlFor="iv-email"><Input id="iv-email" type="email" value={f.email} onChange={(e) => set("email", e.target.value)} /></Field>
          <Field label="Type" htmlFor="iv-type"><Select id="iv-type" value={f.type} onChange={(e) => set("type", e.target.value)}>{TYPES.map((t) => <option key={t} value={t}>{titleCase(t)}</option>)}</Select></Field>
          <Field label="Duration (min)" htmlFor="iv-dur"><Input id="iv-dur" type="number" min={15} max={480} step={15} value={f.dur} onChange={(e) => set("dur", e.target.value)} /></Field>
          <Field label="Start *" htmlFor="iv-start" className="col-span-2"><Input id="iv-start" type="datetime-local" value={f.start} onChange={(e) => set("start", e.target.value)} /></Field>
          <Field label="Location / link" htmlFor="iv-loc" className="col-span-2"><Input id="iv-loc" value={f.location} onChange={(e) => set("location", e.target.value)} placeholder="Zoom link or room" /></Field>
          <Field label="Notes" htmlFor="iv-notes" className="col-span-2"><Textarea id="iv-notes" rows={2} value={f.notes} onChange={(e) => set("notes", e.target.value)} /></Field>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          {conflicts.length > 0 && <Button variant="destructive" loading={m.isPending} onClick={() => m.mutate(true)}>Schedule anyway</Button>}
          <Button loading={m.isPending && conflicts.length === 0} onClick={() => submit(false)}>{existing ? "Save" : "Schedule"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const RATINGS = ["technical", "communication", "problem_solving", "culture_fit"] as const;
const RECS: [Recommendation, string][] = [["strong_yes", "Strong yes"], ["yes", "Yes"], ["no", "No"], ["strong_no", "Strong no"]];

export function FeedbackDialog({ iv, open, onOpenChange }: { iv: InterviewOut; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const [ratings, setRatings] = useState({ technical: 3, communication: 3, problem_solving: 3, culture_fit: 3 });
  const [rec, setRec] = useState<Recommendation | "">("");
  const [comments, setComments] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const m = useMutation({
    mutationFn: (b: FeedbackIn) => api<InterviewOut>(`/interviews/${iv.id}/feedback`, { body: b }),
    onSuccess: () => { toast.success("Feedback saved"); ["application", "interviews"].forEach((k) => qc.invalidateQueries({ queryKey: [k] })); onOpenChange(false); },
    onError: (e) => setErr(errMsg(e)),
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Interview feedback</DialogTitle><DialogDescription>{iv.candidate_name} · {titleCase(iv.interview_type)} · {fmtDateTime(iv.start_at)}</DialogDescription></DialogHeader>
        {err && <Banner tone="danger">{err}</Banner>}
        {RATINGS.map((k) => (
          <div key={k} className="flex items-center justify-between gap-3">
            <span className="text-sm font-medium">{titleCase(k)}</span>
            <div role="radiogroup" aria-label={titleCase(k)} className="flex gap-1">
              {[1, 2, 3, 4, 5].map((n) => (
                <button key={n} type="button" role="radio" aria-checked={ratings[k] === n} onClick={() => setRatings({ ...ratings, [k]: n })} className={cn("size-8 rounded-md border text-sm font-medium", ratings[k] === n ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted")}>{n}</button>
              ))}
            </div>
          </div>
        ))}
        <Field label="Recommendation *" htmlFor="fb-rec"><Select id="fb-rec" value={rec} onChange={(e) => setRec(e.target.value as Recommendation)}><option value="">Select…</option>{RECS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select></Field>
        <Field label="Comments" htmlFor="fb-c"><Textarea id="fb-c" value={comments} onChange={(e) => setComments(e.target.value)} /></Field>
        <DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button><Button loading={m.isPending} onClick={() => (rec ? m.mutate({ ratings, recommendation: rec, comments: comments.trim() || null }) : setErr("Choose a recommendation"))}>Submit feedback</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function InterviewCard({ iv, onReschedule, onFeedback, onDetails }: { iv: InterviewOut; onReschedule: () => void; onFeedback: () => void; onDetails?: () => void }) {
  const qc = useQueryClient();
  const upd = useMutation({
    mutationFn: (status: "cancelled" | "completed") => api<InterviewOut>(`/interviews/${iv.id}`, { method: "PATCH", body: { status } }),
    onSuccess: () => { ["application", "interviews"].forEach((k) => qc.invalidateQueries({ queryKey: [k] })); toast.success("Interview updated"); },
    onError: (e) => toast.error(errMsg(e)),
  });
  return (
    <Card className={cn(iv.status === "cancelled" && "opacity-60")}>
      <CardContent className="space-y-2 pt-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-3"><DateTile iso={iv.start_at} /><div><p className="font-semibold">{titleCase(iv.interview_type)} interview with {iv.interviewer_name}</p><p className="text-sm text-muted-foreground">{fmtDateTime(iv.start_at)} → {fmtDateTime(iv.end_at)}{iv.location && ` · ${iv.location}`}</p></div></div>
          <div className="flex gap-1"><InterviewStatusPill status={iv.status} />{iv.has_conflict && <Badge variant="warning">conflict</Badge>}</div>
        </div>
        {iv.conflict_details.map((c, i) => <Banner key={i} tone="warning">{c.message}</Banner>)}
        {iv.feedback.map((f) => (
          <div key={f.id} className="rounded-md bg-muted/50 p-2 text-sm">
            <p className="font-medium">{f.author_name} — <Badge variant={f.recommendation.includes("yes") ? "success" : "destructive"}>{titleCase(f.recommendation)}</Badge></p>
            <p className="text-xs text-muted-foreground">{Object.entries(f.ratings).map(([k, v]) => `${titleCase(k)} ${v}/5`).join(" · ")}</p>
            {f.comments && <p className="mt-1">{f.comments}</p>}
          </div>
        ))}
        {iv.status !== "cancelled" && (
          <div className="flex flex-wrap gap-2 pt-1">
            {onDetails && <Button size="sm" onClick={onDetails}>Details</Button>}
            {iv.status === "scheduled" && <Button size="sm" variant="outline" onClick={onReschedule}>Reschedule</Button>}
            {iv.status === "scheduled" && <Button size="sm" variant="outline" loading={upd.isPending} onClick={() => upd.mutate("completed")}>Mark completed</Button>}
            <Button size="sm" variant="outline" onClick={onFeedback}><MessageSquareText /> Feedback</Button>
            {iv.status === "scheduled" && <Button size="sm" variant="ghost" className="text-destructive" loading={upd.isPending} onClick={() => confirm("Cancel this interview? The candidate will be notified.") && upd.mutate("cancelled")}>Cancel</Button>}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function InterviewsTab({ appId, canSchedule }: { appId: string; canSchedule: boolean }) {
  const [sched, setSched] = useState<{ open: boolean; iv?: InterviewOut }>({ open: false });
  const [fb, setFb] = useState<InterviewOut | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["interviews", "app", appId], queryFn: () => api<InterviewOut[]>(`/applications/${appId}/interviews`) });
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">{canSchedule ? "Scheduling an interview moves a shortlisted candidate to the Interview stage." : "Shortlist the candidate before scheduling an interview."}</p>
        <Button disabled={!canSchedule} onClick={() => setSched({ open: true })}><CalendarPlus /> Schedule interview</Button>
      </div>
      {q.isError ? <ErrorState error={q.error} retry={() => q.refetch()} /> : !q.data ? <Skeleton className="h-32" /> : q.data.length === 0 ? <EmptyState title="No interviews scheduled" /> :
        q.data.map((iv) => <InterviewCard key={iv.id} iv={iv} onReschedule={() => setSched({ open: true, iv })} onFeedback={() => setFb(iv)} onDetails={() => setDetailId(iv.id)} />)}
      {(() => { const d = q.data?.find((x) => x.id === detailId); return d ? <InterviewDetailDialog iv={d} open onOpenChange={(o) => !o && setDetailId(null)} onReschedule={() => { setDetailId(null); setSched({ open: true, iv: d }); }} onFeedback={() => { setDetailId(null); setFb(d); }} /> : null; })()}
      {sched.open && <ScheduleDialog key={sched.iv?.id ?? "new"} appId={appId} existing={sched.iv} open onOpenChange={(o) => setSched({ open: o })} />}
      {fb && <FeedbackDialog key={fb.id} iv={fb} open onOpenChange={(o) => !o && setFb(null)} />}
    </div>
  );
}
