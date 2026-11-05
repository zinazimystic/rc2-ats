"use client";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "@/lib/toast";
import { CalendarClock, Clock, Globe2, MapPin, MessageSquareText, UserRound } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import type { InterviewOut } from "@/lib/types";
import { fmtDateTime, fmtTime, titleCase } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Banner } from "@/components/ui/misc";
import { DateTile } from "@/components/app/common";
import { cn } from "@/lib/utils";

export function InterviewStatusPill({ status, className }: { status: string; className?: string }) {
  const tone = status === "scheduled" ? "bg-primary/12 text-primary" : status === "completed" ? "bg-success/15 text-success" : "bg-muted text-muted-foreground";
  return <span className={cn("inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[13px] font-semibold capitalize", tone, className)}><span className="size-1.5 rounded-full bg-current" />{status}</span>;
}

function minutes(a: string, b: string) {
  return Math.max(0, Math.round((new Date(b).getTime() - new Date(a).getTime()) / 60000));
}

export function InterviewDetailDialog({
  iv, open, onOpenChange, onReschedule, onFeedback,
}: { iv: InterviewOut; open: boolean; onOpenChange: (o: boolean) => void; onReschedule: () => void; onFeedback: () => void }) {
  const qc = useQueryClient();
  const upd = useMutation({
    mutationFn: (status: "cancelled" | "completed") => api<InterviewOut>(`/interviews/${iv.id}`, { method: "PATCH", body: { status } }),
    onSuccess: () => { ["application", "interviews"].forEach((k) => qc.invalidateQueries({ queryKey: [k] })); toast.success("Interview updated"); },
    onError: (e) => toast.error(errMsg(e)),
  });
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const dur = minutes(iv.start_at, iv.end_at);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl gap-5 rounded-3xl p-0">
        <div className="flex flex-wrap items-center gap-4 p-6 pb-0 pr-14">
          <DateTile iso={iv.start_at} className="size-20 rounded-3xl [&_p:last-child]:text-3xl" />
          <div className="min-w-0 flex-1">
            <DialogTitle className="text-xl">{iv.candidate_name}</DialogTitle>
            <DialogDescription className="mt-1 flex items-center gap-1.5"><Clock className="size-3.5" />{fmtTime(iv.start_at)} – {fmtTime(iv.end_at)} · {iv.job_title}</DialogDescription>
            <p className="mt-1 text-[13px] text-muted-foreground">ID {iv.id.slice(0, 8)} · {tz} · {dur} min</p>
          </div>
          <InterviewStatusPill status={iv.status} />
        </div>
        <Tabs defaultValue="details" className="px-6 pb-6">
          <TabsList>
            <TabsTrigger value="details">Detail Information</TabsTrigger>
            <TabsTrigger value="feedback">Feedback ({iv.feedback.length})</TabsTrigger>
            <TabsTrigger value="notes">Notes</TabsTrigger>
            <TabsTrigger value="questions">Questions</TabsTrigger>
          </TabsList>
          <TabsContent value="details" className="space-y-4">
            <div className="grid gap-3 rounded-2xl bg-sidebar p-5 text-white sm:grid-cols-2">
              <p className="flex items-center gap-2 text-sm"><CalendarClock className="size-4 text-white/60" />{titleCase(iv.interview_type)} interview</p>
              <p className="flex items-center gap-2 text-sm"><UserRound className="size-4 text-white/60" />{iv.interviewer_name}{iv.interviewer_email ? ` · ${iv.interviewer_email}` : ""}</p>
              <p className="flex items-center gap-2 text-sm"><MapPin className="size-4 text-white/60" />{iv.location || "No location or link"}</p>
              <p className="flex items-center gap-2 text-sm"><Globe2 className="size-4 text-white/60" />{fmtDateTime(iv.start_at)} → {fmtDateTime(iv.end_at)}</p>
            </div>
            {iv.has_conflict && <Badge variant="warning">conflict</Badge>}
            {iv.conflict_details.map((c, i) => <Banner key={i} tone="warning">{c.message}</Banner>)}
            {iv.status !== "cancelled" && (
              <div className="flex flex-wrap gap-2">
                {iv.status === "scheduled" && <Button size="sm" variant="outline" onClick={onReschedule}>Reschedule</Button>}
                {iv.status === "scheduled" && <Button size="sm" variant="outline" loading={upd.isPending} onClick={() => upd.mutate("completed")}>Mark completed</Button>}
                {iv.status === "scheduled" && <Button size="sm" variant="ghost" className="text-destructive" loading={upd.isPending} onClick={() => confirm("Cancel this interview? The candidate will be notified.") && upd.mutate("cancelled")}>Cancel</Button>}
              </div>
            )}
          </TabsContent>
          <TabsContent value="feedback" className="space-y-3">
            {iv.feedback.length === 0 && <p className="rounded-2xl bg-muted/60 p-6 text-center text-sm text-muted-foreground">No feedback submitted yet.</p>}
            {iv.feedback.map((f) => (
              <div key={f.id} className="rounded-2xl bg-muted/60 p-4 text-sm">
                <p className="flex flex-wrap items-center gap-2 font-medium">{f.author_name} <Badge variant={f.recommendation.includes("yes") ? "success" : "destructive"}>{titleCase(f.recommendation)}</Badge></p>
                <p className="mt-1 text-[13px] text-muted-foreground">{Object.entries(f.ratings).map(([k, v]) => `${titleCase(k)} ${v}/5`).join(" · ")}</p>
                {f.comments && <p className="mt-2">{f.comments}</p>}
              </div>
            ))}
            {iv.status !== "cancelled" && <Button size="sm" variant="outline" onClick={onFeedback}><MessageSquareText /> Add feedback</Button>}
          </TabsContent>
          <TabsContent value="notes">
            <p className="rounded-2xl bg-muted/60 p-5 text-sm whitespace-pre-wrap">{iv.notes || "No notes were added for this interview."}</p>
          </TabsContent>
          <TabsContent value="questions">
            <div className="rounded-2xl bg-muted/60 p-5 text-sm">
              <p className="text-muted-foreground">Tailored interview questions are generated from the candidate&apos;s assessment.</p>
              <Button asChild size="sm" className="mt-3"><Link href={`/recruiter/applications/${iv.application_id}`}>Open application questions</Link></Button>
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
