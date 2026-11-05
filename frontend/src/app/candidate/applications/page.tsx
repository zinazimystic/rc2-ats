"use client";
import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Calendar, FileText, Send } from "lucide-react";
import { api } from "@/lib/api";
import type { CandidateApplicationOut } from "@/lib/types";
import { fmtDateTime, titleCase } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";
import { ProcessingBadge, StatusBadge, notifyError } from "@/components/app/common";

export default function MyApplications() {
  const qc = useQueryClient();
  const [target, setTarget] = useState<CandidateApplicationOut | null>(null);
  const q = useQuery({
    queryKey: ["my-applications"],
    queryFn: () => api<CandidateApplicationOut[]>("/applications/me"),
    refetchInterval: (query) => (query.state.data?.some((a) => a.processing_state === "queued" || a.processing_state === "processing") ? 2000 : 15_000),
  });
  const withdraw = useMutation({
    mutationFn: (id: string) => api<CandidateApplicationOut>(`/applications/${id}/withdraw`, { method: "POST" }),
    onSuccess: () => { toast.success("Application withdrawn"); qc.invalidateQueries({ queryKey: ["my-applications"] }); qc.invalidateQueries({ queryKey: ["jobs"] }); setTarget(null); },
    onError: notifyError,
  });
  return (
    <>
      <PageHeader title="My applications" description="Track where each application stands." />
      {q.isError ? <ErrorState error={q.error} retry={() => q.refetch()} /> : !q.data ? <Skeleton className="h-48" /> : q.data.length === 0 ? (
        <EmptyState icon={<Send className="size-8" />} title="No applications yet" description="Browse open roles and apply with your resume." action={<Button asChild><Link href="/candidate">Browse jobs</Link></Button>} />
      ) : (
        <div className="space-y-4">
          {q.data.map((a) => (
            <Card key={a.id}><CardContent className="space-y-4 pt-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><Link href={`/candidate/jobs/${a.job.id}`} className="text-lg font-semibold hover:text-primary">{a.job.title}</Link><p className="text-sm text-muted-foreground">{[a.job.department, a.job.location].filter(Boolean).join(" · ")}</p>{a.resume_filename && <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground"><FileText className="size-3" />{a.resume_filename}</p>}</div>
                <div className="flex items-center gap-2"><StatusBadge status={a.status} label={a.status_label} /><ProcessingBadge state={a.processing_state === "failed" ? "queued" : a.processing_state} /></div>
              </div>
              <ol className="space-y-2 border-l pl-4">
                {a.timeline.map((t, i) => (
                  <li key={i} className="relative text-sm"><span className="absolute top-1.5 -left-[1.35rem] size-2.5 rounded-full bg-primary" aria-hidden />{t.label} <span className="text-xs text-muted-foreground">· {fmtDateTime(t.at)}</span></li>
                ))}
              </ol>
              {a.interviews.filter((i) => i.status === "scheduled").map((i) => (
                <div key={i.id} className="flex items-start gap-3 rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm"><Calendar className="mt-0.5 size-4 text-primary" /><div><p className="font-medium">{titleCase(i.interview_type)} interview — {fmtDateTime(i.start_at)}</p><p className="text-muted-foreground">{i.interviewer_name && `With ${i.interviewer_name}`}{i.location && ` · ${i.location}`}</p></div></div>
              ))}
              {a.can_withdraw && <div className="flex justify-end"><Button variant="outline" size="sm" className="text-destructive" onClick={() => setTarget(a)}>Withdraw</Button></div>}
            </CardContent></Card>
          ))}
        </div>
      )}
      <Dialog open={!!target} onOpenChange={(o) => !o && setTarget(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Withdraw application?</DialogTitle><DialogDescription>You’ll no longer be considered for {target?.job.title}. Any scheduled interview will be cancelled. You can’t undo this.</DialogDescription></DialogHeader>
          <DialogFooter><Button variant="outline" onClick={() => setTarget(null)}>Keep application</Button><Button variant="destructive" loading={withdraw.isPending} onClick={() => target && withdraw.mutate(target.id)}>Withdraw</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
