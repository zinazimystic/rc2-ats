"use client";
import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, CheckCircle2 } from "lucide-react";
import { api, ApiError, errMsg } from "@/lib/api";
import type { ApplyIn, CandidateApplicationOut, JobOut, ResumeOut } from "@/lib/types";
import { EDUCATION_LABEL, fmtSalary, titleCase } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Textarea } from "@/components/ui/input";
import { Banner, ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";

export default function CandidateJob() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const [note, setNote] = useState("");
  const job = useQuery({ queryKey: ["job", id], queryFn: () => api<JobOut>(`/jobs/${id}`) });
  const resumes = useQuery({ queryKey: ["resumes"], queryFn: () => api<ResumeOut[]>("/candidates/me/resumes") });
  const apply = useMutation({
    mutationFn: (b: ApplyIn) => api<CandidateApplicationOut>("/applications", { body: b }),
    onSuccess: () => { toast.success("Application submitted!"); qc.invalidateQueries({ queryKey: ["jobs"] }); qc.invalidateQueries({ queryKey: ["job", id] }); qc.invalidateQueries({ queryKey: ["my-applications"] }); router.push("/candidate/applications"); },
  });
  if (job.isError) return <ErrorState error={job.error} retry={() => job.refetch()} />;
  const j = job.data;
  if (!j) return <Skeleton className="h-96" />;
  const current = resumes.data?.find((r) => r.is_current) ?? resumes.data?.[0];
  const usable = current && current.parse_status !== "failed";
  const closed = j.status === "closed";
  const e = apply.error;
  return (
    <div className="mx-auto max-w-4xl">
      <Button variant="ghost" size="sm" asChild className="-ml-2 mb-2"><Link href="/candidate"><ArrowLeft /> All jobs</Link></Button>
      <PageHeader title={j.title} description={[j.department, j.location, `${titleCase(j.employment_type)} · ${titleCase(j.work_mode)}`, fmtSalary(j.salary_min, j.salary_max, j.currency)].filter(Boolean).join(" · ")} actions={j.has_applied ? <Badge variant="success"><CheckCircle2 /> Applied</Badge> : closed ? <Badge variant="muted">Closed</Badge> : null} />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2"><CardHeader><CardTitle>About the role</CardTitle></CardHeader><CardContent><p className="text-sm whitespace-pre-wrap">{j.description}</p></CardContent></Card>
        <Card>
          <CardHeader><CardTitle>Requirements</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div><p className="mb-1 text-xs font-medium text-muted-foreground uppercase">Required</p><div className="flex flex-wrap gap-1">{j.requirements.filter((r) => r.kind === "required").map((r) => <Badge key={r.id}>{r.skill}</Badge>)}</div></div>
            {j.requirements.some((r) => r.kind === "preferred") && <div><p className="mb-1 text-xs font-medium text-muted-foreground uppercase">Nice to have</p><div className="flex flex-wrap gap-1">{j.requirements.filter((r) => r.kind === "preferred").map((r) => <Badge key={r.id} variant="secondary">{r.skill}</Badge>)}</div></div>}
            <p>Experience: <strong>{j.min_experience_years}+ years</strong></p>
            {j.education_level !== "none" && <p>Education: <strong>{EDUCATION_LABEL[j.education_level]}</strong></p>}
          </CardContent>
        </Card>
      </div>
      {!j.has_applied && (
        <Card className="mt-4">
          <CardHeader><CardTitle>Apply for this role</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {closed ? <Banner tone="warning">This position is no longer accepting applications.</Banner> : !resumes.data ? <Skeleton className="h-10" /> : !current ? (
              <Banner tone="warning">You need to upload a resume first. <Link href="/candidate/resume" className="font-medium underline">Upload resume</Link></Banner>
            ) : (
              <>
                <p className="text-sm">Applying with <strong>{current.filename}</strong> {current.parse_status !== "parsed" && <Badge variant="warning">still being analysed</Badge>} · <Link href="/candidate/resume" className="text-primary hover:underline">change</Link></p>
                {current.parse_status === "failed" && <Banner tone="danger">Your latest resume could not be parsed. Please upload a different file.</Banner>}
                <Field label="Cover note (optional)" htmlFor="cover"><Textarea id="cover" maxLength={2000} value={note} onChange={(ev) => setNote(ev.target.value)} placeholder="Why are you a good fit?" /></Field>
                {e && <Banner tone="danger">{e instanceof ApiError && e.status === 409 ? e.message : errMsg(e)}</Banner>}
                <Button disabled={!usable} loading={apply.isPending} onClick={() => apply.mutate({ job_id: id, cover_note: note.trim() || null })}>Submit application</Button>
              </>
            )}
          </CardContent>
        </Card>
      )}
      {j.has_applied && <Banner tone="success" className="mt-4">You’ve applied. Track progress in <Link href="/candidate/applications" className="font-medium underline">My applications</Link>.</Banner>}
    </div>
  );
}
