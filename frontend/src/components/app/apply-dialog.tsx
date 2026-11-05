"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, Loader2, Pencil } from "lucide-react";
import { api } from "@/lib/api";
import { qk, useMyMatch, useResumes } from "@/lib/queries";
import { notify } from "@/lib/toast";
import type { ApplyIn, CandidateApplicationOut, ResumeOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, Textarea } from "@/components/ui/input";
import { Notice } from "@/components/ui/notice";
import { Skeleton } from "@/components/ui/misc";
import { cn } from "@/lib/utils";
import { ScoreRing } from "./common";
import { BAND_LABEL, ResumePicker, bandTone } from "./resume-picker";
import { ResumeUploader, isBusy } from "./resume-manager";
import { ResumeReviewSheet } from "./resume-review-sheet";

function Preview({ jobId, resumeId }: { jobId: string; resumeId: string }) {
  const m = useMyMatch(jobId, resumeId);
  if (m.isError) return <p className="rounded-2xl bg-muted/50 p-3 text-xs text-muted-foreground">We couldn’t estimate your fit right now. You can still apply.</p>;
  if (!m.data) return <Skeleton className="h-[4.5rem] rounded-2xl" />;
  const gaps = (m.data.gaps ?? []).slice(0, 3);
  return (
    <div className="flex items-center gap-4 rounded-2xl bg-muted/50 p-3">
      <ScoreRing value={m.data.score} size={64} label="Estimated fit" />
      <div className="min-w-0 text-sm">
        <p className={cn("font-semibold", bandTone(m.data.band))}>{BAND_LABEL[m.data.band]}</p>
        {gaps.length > 0 ? <p className="text-xs text-muted-foreground">To strengthen: {gaps.join(", ")}</p> : <p className="text-xs text-muted-foreground">Estimated from your resume. The employer’s review may differ.</p>}
      </div>
    </div>
  );
}

export function ApplyDialog({ jobId, jobTitle, open, onOpenChange }: { jobId: string; jobTitle: string; open: boolean; onOpenChange: (o: boolean) => void }) {
  const router = useRouter();
  const qc = useQueryClient();
  const resumes = useResumes();
  const [picked, setPicked] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [review, setReview] = useState(false);
  const [uploading, setUploading] = useState(false);

  const list: ResumeOut[] = resumes.data ?? [];
  const usable = list.filter((r) => r.parse_status === "parsed");
  const chosen = list.find((r) => r.id === picked && r.parse_status === "parsed") ?? usable.find((r) => r.is_current) ?? usable[0] ?? null;
  const reading = list.find((r) => isBusy(r));

  const apply = useMutation({
    mutationFn: (b: ApplyIn) => api<CandidateApplicationOut>("/applications", { body: b }),
    onSuccess: () => {
      notify.success("Application submitted", { description: `You applied to ${jobTitle}.` });
      qc.invalidateQueries({ queryKey: qk.applications });
      qc.invalidateQueries({ queryKey: qk.dashboard });
      qc.invalidateQueries({ queryKey: qk.openJobs });
      qc.invalidateQueries({ queryKey: qk.job(jobId) });
      qc.invalidateQueries({ queryKey: ["jobs"] });
      onOpenChange(false);
      router.push("/candidate/applications");
    },
    onError: (e) => notify.error(e),
  });

  return (
    <>
      <Dialog open={open} onOpenChange={(o) => !apply.isPending && onOpenChange(o)}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>Apply for this role</DialogTitle>
            <DialogDescription>{jobTitle}</DialogDescription>
          </DialogHeader>

          {!resumes.data ? (
            <Skeleton className="h-32 rounded-2xl" />
          ) : !chosen ? (
            <div className="space-y-3">
              {reading ? (
                <Notice tone="info" title="Reading your resume">This takes a few seconds. You’ll be able to apply as soon as it’s ready.</Notice>
              ) : (
                <Notice tone="info" title="Upload a resume to apply">We use your resume to match you to the role. PDF or DOCX, up to 5 MB.</Notice>
              )}
              {reading ? <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin text-primary" /> {reading.filename}</div> : <ResumeUploader compact />}
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3 rounded-2xl border p-3">
                <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary"><FileText className="size-5" /></span>
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-muted-foreground">Applying with</p>
                  <p className="truncate text-sm font-semibold" title={chosen.filename}>{chosen.filename}</p>
                </div>
                <ResumePicker jobId={jobId} resumes={list} value={chosen.id} onChange={setPicked} onUpload={() => setUploading(true)} />
              </div>
              {uploading && <ResumeUploader compact onUploaded={(r) => { setPicked(r.id); setUploading(false); }} />}
              <button type="button" onClick={() => setReview(true)} className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"><Pencil className="size-3.5" /> Review resume details</button>
              <Preview jobId={jobId} resumeId={chosen.id} />
              <Field label="Cover note (optional)" htmlFor="apply-note">
                <Textarea id="apply-note" maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Why are you a good fit?" />
              </Field>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" disabled={apply.isPending} onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button loading={apply.isPending} disabled={!chosen || apply.isPending} onClick={() => chosen && apply.mutate({ job_id: jobId, resume_id: chosen.id, cover_note: note.trim() || null })}>Apply</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <ResumeReviewSheet resumeId={chosen?.id ?? null} open={review} onOpenChange={setReview} />
    </>
  );
}
