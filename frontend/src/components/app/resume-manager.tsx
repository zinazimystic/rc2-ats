"use client";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileText, Loader2, Pencil, RefreshCw, Star, Trash2, UploadCloud } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { qk, useResumes } from "@/lib/queries";
import { notify } from "@/lib/toast";
import { fmtDate, fmtSize } from "@/lib/format";
import type { DeleteResumesOut, Msg, ResumeNotice, ResumeOut } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/input";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/misc";
import { Notice } from "@/components/ui/notice";
import { cn } from "@/lib/utils";

const MAX_MB = 5;
const OK_EXT = [".pdf", ".docx"];

export const isBusy = (r: ResumeOut) => r.parse_status === "pending" || r.parse_status === "processing";

/** Notices from the server, or a sensible fallback when the backend doesn't send them yet. */
export function resumeNotices(r: ResumeOut): ResumeNotice[] {
  if (r.notices) return r.notices;
  if (r.parse_status === "failed")
    return [{ code: "parse_failed", level: "error", message: "We couldn’t read this file. Try again, or upload a text-based PDF or DOCX (scanned images aren’t supported).", action: "reparse" }];
  return [];
}

export function ResumeStatusChip({ resume }: { resume: ResumeOut }) {
  if (isBusy(resume)) return <Badge variant="warning"><Loader2 className="animate-spin" /> Parsing…</Badge>;
  const attention = resume.parse_status === "failed" || resumeNotices(resume).some((n) => n.level !== "info");
  return attention ? <Badge variant="warning">Needs attention</Badge> : <Badge variant="success"><CheckCircle2 /> Ready</Badge>;
}

/** Invalidate everything a resume change can affect, in one place. */
export function useInvalidateResumes() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: qk.resumes });
    qc.invalidateQueries({ queryKey: qk.dashboard });
    qc.invalidateQueries({ queryKey: qk.profile });
    qc.invalidateQueries({ queryKey: ["my-match"] });
  };
}

export function ResumeUploader({ compact, onUploaded }: { compact?: boolean; onUploaded?: (r: ResumeOut) => void }) {
  const inv = useInvalidateResumes();
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const up = useMutation({
    mutationFn: (f: File) => {
      const fd = new FormData();
      fd.append("file", f);
      return api<ResumeOut>("/candidates/me/resumes", { form: fd });
    },
    onSuccess: (r) => {
      notify.success("Resume uploaded", { description: "We’re reading it now. This takes a few seconds." });
      inv();
      onUploaded?.(r);
    },
    onError: (e) => { setErr(null); notify.error(e); },
  });
  function take(files: FileList | File[] | null | undefined) {
    const f = files?.[0];
    if (!f) return;
    const ext = f.name.includes(".") ? f.name.slice(f.name.lastIndexOf(".")).toLowerCase() : "";
    if (!OK_EXT.includes(ext)) return setErr("Only PDF and DOCX files are supported.");
    if (f.size === 0) return setErr("That file is empty.");
    if (f.size > MAX_MB * 1024 * 1024) return setErr(`That file is too large. The limit is ${MAX_MB} MB.`);
    setErr(null);
    up.mutate(f);
  }
  return (
    <div className="space-y-2">
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); take(e.dataTransfer.files); }}
        className={cn("flex flex-col items-center gap-2 rounded-2xl border-2 border-dashed text-center transition-colors", compact ? "p-5" : "p-8", drag ? "border-primary bg-primary/5" : "border-border")}
      >
        {up.isPending ? <Loader2 className="size-7 animate-spin text-primary" /> : <UploadCloud className="size-7 text-muted-foreground" />}
        <p className="text-sm font-medium">{up.isPending ? "Uploading…" : drag ? "Drop to upload" : "Drag & drop your resume here"}</p>
        <p className="text-xs text-muted-foreground">PDF or DOCX · up to {MAX_MB} MB · text-based files work best</p>
        <Button variant="outline" size="sm" disabled={up.isPending} onClick={() => input.current?.click()}>Choose file</Button>
        <input ref={input} type="file" hidden accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" aria-label="Upload resume" onChange={(e) => { take(e.target.files); e.target.value = ""; }} />
      </div>
      {err && <Notice tone="error" onDismiss={() => setErr(null)}>{err}</Notice>}
    </div>
  );
}

function ResumeCard({
  r, selected, onSelect, onReview, onDelete, onPrimary, busyAction,
}: {
  r: ResumeOut; selected: boolean; onSelect: (v: boolean) => void; onReview: () => void; onDelete: () => void; onPrimary: () => void; busyAction: boolean;
}) {
  const inv = useInvalidateResumes();
  const reparse = useMutation({
    mutationFn: () => api<ResumeOut>(`/resumes/${r.id}/reprocess`, { method: "POST" }),
    onSuccess: () => { notify.loading(`Re-reading ${r.filename}…`, { id: `reparse-${r.id}`, duration: 15000 }); inv(); },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 409) notify.info("Already being read. Hang tight.");
      else notify.error(e);
    },
  });
  // Report the outcome when a re-read we watched finishes.
  const prev = useRef(r.parse_status);
  useEffect(() => {
    const was = prev.current;
    prev.current = r.parse_status;
    if (was === "parsed" || was === "failed" || was === r.parse_status) return;
    notify.dismiss(`reparse-${r.id}`);
    if (r.parse_status === "parsed") notify.success(`${r.filename} is ready`);
    else if (r.parse_status === "failed") notify.warning(`${r.filename} needs attention`, { description: "We couldn’t read this file." });
  }, [r.parse_status, r.id, r.filename]);

  const busy = isBusy(r) || reparse.isPending;
  const notices = busy ? [] : resumeNotices(r);
  const count = r.application_count ?? 0;
  return (
    <Card className={cn("p-4 transition-shadow", selected && "ring-2 ring-primary/40")}>
      <div className="flex items-start gap-3">
        <Checkbox aria-label={`Select ${r.filename}`} className="mt-1.5" checked={selected} onChange={(e) => onSelect(e.target.checked)} />
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary"><FileText className="size-5" /></span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="max-w-full truncate font-semibold" title={r.filename}>{r.filename}</p>
            {r.is_current && <Badge variant="default"><Star /> Primary</Badge>}
            <ResumeStatusChip resume={{ ...r, parse_status: busy && !isBusy(r) ? "processing" : r.parse_status }} />
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {fmtSize(r.size)} · Uploaded {fmtDate(r.created_at)}
            {count > 0 && <> · Used in {count} application{count === 1 ? "" : "s"}</>}
          </p>
        </div>
      </div>
      {busy && (
        <div className="mt-3 flex items-center gap-2 rounded-xl bg-muted/60 px-3 py-2 text-xs text-muted-foreground" role="status">
          <Loader2 className="size-3.5 animate-spin text-primary" /> Reading your resume. This usually takes a few seconds.
        </div>
      )}
      {notices.length > 0 && (
        <div className="mt-3 space-y-2">
          {notices.map((n) => (
            <Notice
              key={n.code}
              tone={n.level === "error" ? "error" : n.level}
              action={n.action === "reparse" ? { label: "Re-parse", onClick: () => reparse.mutate(), loading: reparse.isPending } : n.action === "edit" ? { label: "Review details", onClick: onReview } : undefined}
            >
              {n.message}
            </Notice>
          ))}
        </div>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2 pl-[3.25rem]">
        <Button size="sm" variant="outline" disabled={busy} onClick={onReview}><Pencil /> Review details</Button>
        {!r.is_current && r.parse_status === "parsed" && <Button size="sm" variant="ghost" disabled={busyAction} onClick={onPrimary}><Star /> Make primary</Button>}
        {r.parse_status === "parsed" && !busy && <Button size="sm" variant="ghost" loading={reparse.isPending} onClick={() => reparse.mutate()}><RefreshCw /> Re-parse</Button>}
        <Button size="sm" variant="ghost" className="ml-auto text-destructive hover:text-destructive" onClick={onDelete} aria-label={`Delete ${r.filename}`}><Trash2 /> Delete</Button>
      </div>
    </Card>
  );
}

export function ResumeListSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      <Skeleton className="h-36 rounded-3xl" />
      <Skeleton className="h-28 rounded-3xl" />
    </div>
  );
}

export function ResumeManager({ onReview }: { onReview: (id: string) => void }) {
  const inv = useInvalidateResumes();
  const list = useResumes();
  const [sel, setSel] = useState<string[]>([]);
  const [confirm, setConfirm] = useState<ResumeOut[] | null>(null);

  const del = useMutation({
    mutationFn: (ids: string[]) => api<DeleteResumesOut>("/candidates/me/resumes/delete", { body: { ids } }),
    onSuccess: (res) => {
      if (res.deleted.length) notify.success(res.deleted.length === 1 ? "Resume deleted" : `${res.deleted.length} resumes deleted`);
      for (const b of res.blocked) notify.warning(`Couldn’t delete ${b.filename}`, { description: b.reason });
      setSel((s) => s.filter((id) => !res.deleted.includes(id)));
      setConfirm(null);
      inv();
    },
    onError: (e) => { setConfirm(null); notify.error(e); },
  });
  const primary = useMutation({
    mutationFn: (id: string) => api<Msg>(`/resumes/${id}/primary`, { method: "POST" }),
    onSuccess: () => { notify.success("Primary resume updated"); inv(); },
    onError: (e) => {
      if (e instanceof ApiError && (e.status === 404 || e.status === 405)) notify.info("Changing the primary resume isn’t available yet. Choose a resume when you apply.");
      else notify.error(e);
    },
  });

  if (list.isError && !list.data) return <ErrorState error={list.error} retry={() => list.refetch()} />;
  if (!list.data) return <ResumeListSkeleton />;
  const resumes = list.data;
  const allSelected = resumes.length > 0 && resumes.every((r) => sel.includes(r.id));
  const chosen = resumes.filter((r) => sel.includes(r.id));

  return (
    <div className="space-y-4">
      <ResumeUploader compact={resumes.length > 0} />
      {resumes.length === 0 ? (
        <EmptyState icon={<FileText className="size-8" />} title="No resumes yet" description="Upload your resume to get matched to jobs. We’ll read it so you can review the details." />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm"><Checkbox checked={allSelected} onChange={(e) => setSel(e.target.checked ? resumes.map((r) => r.id) : [])} aria-label="Select all resumes" /> Select all</label>
            <span className="text-sm text-muted-foreground">{resumes.length} resume{resumes.length === 1 ? "" : "s"}</span>
            {chosen.length > 0 && (
              <Button size="sm" variant="destructive" className="ml-auto" onClick={() => setConfirm(chosen)}><Trash2 /> Delete selected ({chosen.length})</Button>
            )}
          </div>
          <div className="space-y-3">
            {resumes.map((r) => (
              <ResumeCard
                key={r.id}
                r={r}
                selected={sel.includes(r.id)}
                onSelect={(v) => setSel((s) => (v ? [...s, r.id] : s.filter((x) => x !== r.id)))}
                onReview={() => onReview(r.id)}
                onDelete={() => setConfirm([r])}
                onPrimary={() => primary.mutate(r.id)}
                busyAction={primary.isPending}
              />
            ))}
          </div>
        </>
      )}
      <Dialog open={!!confirm} onOpenChange={(o) => !o && !del.isPending && setConfirm(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Delete {confirm && confirm.length > 1 ? `${confirm.length} resumes` : "this resume"}?</DialogTitle>
            <DialogDescription>This can’t be undone. Resumes attached to an application can’t be deleted.</DialogDescription>
          </DialogHeader>
          <ul className="max-h-48 space-y-1 overflow-y-auto rounded-2xl bg-muted/50 p-3 text-sm">
            {confirm?.map((r) => (
              <li key={r.id} className="flex items-center gap-2"><FileText className="size-4 shrink-0 text-muted-foreground" /><span className="truncate">{r.filename}</span>{(r.application_count ?? 0) > 0 && <Badge variant="warning" className="ml-auto">In use</Badge>}</li>
            ))}
          </ul>
          <DialogFooter>
            <Button variant="outline" disabled={del.isPending} onClick={() => setConfirm(null)}>Keep</Button>
            <Button variant="destructive" loading={del.isPending} onClick={() => confirm && del.mutate(confirm.map((r) => r.id))}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
