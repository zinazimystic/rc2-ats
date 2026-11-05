"use client";
import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, CheckCircle2, Send } from "lucide-react";
import { useJob, useResumes } from "@/lib/queries";
import { EDUCATION_LABEL, fmtSalary, titleCase } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";
import { Notice } from "@/components/ui/notice";
import { ApplyDialog } from "@/components/app/apply-dialog";
import { MyMatchCard } from "@/components/app/job-match";

function JobSkeleton() {
  return (
    <div className="mx-auto max-w-5xl" aria-busy="true" aria-label="Loading job">
      <Skeleton className="mb-3 h-8 w-28" />
      <Skeleton className="mb-2 h-8 w-80" />
      <Skeleton className="mb-6 h-4 w-64" />
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2"><Skeleton className="h-52 rounded-3xl" /><Skeleton className="h-96 rounded-3xl" /></div>
        <div className="space-y-4"><Skeleton className="h-56 rounded-3xl" /><Skeleton className="h-32 rounded-3xl" /></div>
      </div>
    </div>
  );
}

export default function CandidateJob() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const job = useJob(id);
  const resumes = useResumes();
  const [pickedResume, setPickedResume] = useState<string | null>(null);
  const [applyOpen, setApplyOpen] = useState(false);

  if (job.isError && !job.data) return <ErrorState error={job.error} retry={() => job.refetch()} />;
  const j = job.data;
  if (!j || !resumes.data) return <JobSkeleton />;
  const list = resumes.data;
  const parsed = list.filter((r) => r.parse_status === "parsed");
  const selected = list.find((r) => r.id === pickedResume && r.parse_status === "parsed") ?? parsed.find((r) => r.is_current) ?? parsed[0] ?? list[0] ?? null;
  const closed = j.status === "closed";
  const req = j.requirements.filter((r) => r.kind === "required");
  const pref = j.requirements.filter((r) => r.kind === "preferred");

  return (
    <div className="mx-auto max-w-5xl">
      <Button variant="ghost" size="sm" asChild className="-ml-2 mb-2"><Link href="/candidate"><ArrowLeft /> All jobs</Link></Button>
      <PageHeader
        title={j.title}
        description={[j.department, j.location, `${titleCase(j.employment_type)} · ${titleCase(j.work_mode)}`, fmtSalary(j.salary_min, j.salary_max, j.currency)].filter(Boolean).join(" · ")}
        actions={j.has_applied ? <Badge variant="success"><CheckCircle2 /> Applied</Badge> : closed ? <Badge variant="muted">Closed</Badge> : <Button onClick={() => setApplyOpen(true)}><Send /> Apply now</Button>}
      />
      <div className="grid items-start gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card><CardHeader><CardTitle>About the role</CardTitle></CardHeader><CardContent><p className="text-sm whitespace-pre-wrap">{j.description}</p></CardContent></Card>
          <MyMatchCard jobId={j.id} resumes={list} resumeId={selected?.id ?? null} onResumeChange={setPickedResume} onUpload={() => router.push("/candidate/resume")} />
        </div>
        <div className="space-y-4 lg:sticky lg:top-4">
          <Card>
            <CardHeader><CardTitle>Requirements</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div><p className="mb-1 text-[13px] font-medium text-muted-foreground uppercase">Required</p><div className="flex flex-wrap gap-1">{req.map((r) => <Badge key={r.id}>{r.skill}</Badge>)}</div></div>
              {pref.length > 0 && <div><p className="mb-1 text-[13px] font-medium text-muted-foreground uppercase">Nice to have</p><div className="flex flex-wrap gap-1">{pref.map((r) => <Badge key={r.id} variant="secondary">{r.skill}</Badge>)}</div></div>}
              <p>Experience: <strong>{j.min_experience_years}+ years</strong></p>
              {j.education_level !== "none" && <p>Education: <strong>{EDUCATION_LABEL[j.education_level]}</strong></p>}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Apply for this role</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {j.has_applied ? (
                <Notice tone="success" title="You’ve applied">Track progress in <Link href="/candidate/applications" className="font-medium underline">My applications</Link>.</Notice>
              ) : closed ? (
                <Notice tone="warning" title="Applications closed">This position is no longer accepting applications.</Notice>
              ) : (
                <>
                  <p className="text-sm text-muted-foreground">{selected ? <>You’ll apply with <strong className="font-medium text-foreground">{selected.filename}</strong>. You can change it next.</> : "You’ll need a resume to apply. You can upload one in the next step."}</p>
                  <Button className="w-full" onClick={() => setApplyOpen(true)}><Send /> Apply for this role</Button>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
      {!j.has_applied && !closed && <ApplyDialog jobId={j.id} jobTitle={j.title} open={applyOpen} onOpenChange={setApplyOpen} />}
    </div>
  );
}
