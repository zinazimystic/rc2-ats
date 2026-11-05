"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { BriefcaseBusiness, CheckCircle2, MapPin, Search, Sparkles } from "lucide-react";
import { api, qs } from "@/lib/api";
import type { JobListItem, RecommendationOut } from "@/lib/types";
import { fmtDate, fmtSalary, titleCase } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Banner, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";
import { SkillChips } from "@/components/app/common";
import { useDebounced } from "@/lib/hooks";

export default function CandidateHome() {
  const [q, setQ] = useState("");
  const dq = useDebounced(q);
  const jobs = useQuery({ queryKey: ["jobs", "open", dq], queryFn: () => api<JobListItem[]>(`/jobs${qs({ status: "open", q: dq })}`), placeholderData: (p) => p });
  const recs = useQuery({ queryKey: ["recommendations"], queryFn: () => api<RecommendationOut[]>("/candidates/me/recommendations"), retry: false });
  return (
    <>
      <PageHeader title="Find your next role" description="Open positions and jobs matched to your resume." />
      {recs.data && recs.data.length > 0 && !dq && (
        <section className="mb-8" aria-labelledby="rec-h">
          <h2 id="rec-h" className="mb-3 flex items-center gap-2 text-lg font-semibold"><Sparkles className="size-5 text-primary" />Recommended for you</h2>
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {recs.data.map((r) => (
              <Link key={r.job.id} href={`/candidate/jobs/${r.job.id}`}>
                <Card className="h-full space-y-2 p-4 transition-shadow hover:shadow-md">
                  <div className="flex items-start justify-between gap-2"><p className="font-semibold">{r.job.title}</p><Badge variant="success">{Math.round(r.score)}% match</Badge></div>
                  <p className="text-sm text-muted-foreground">{r.reason}</p>
                  <SkillChips skills={r.matched_skills} tone="success" max={4} />
                  {r.missing_skills.length > 0 && <p className="text-xs text-muted-foreground">To strengthen: {r.missing_skills.slice(0, 3).join(", ")}</p>}
                </Card>
              </Link>
            ))}
          </div>
        </section>
      )}
      {recs.isSuccess && recs.data.length === 0 && !dq && <Banner tone="info" className="mb-6">Upload a resume to get personalised job recommendations. <Link href="/candidate/resume" className="font-medium underline">Upload now</Link></Banner>}
      <div className="relative mb-4 max-w-sm">
        <Search className="pointer-events-none absolute top-2.5 left-3 size-4 text-muted-foreground" />
        <Input aria-label="Search jobs" placeholder="Search jobs…" className="pl-9" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {jobs.isError ? <ErrorState error={jobs.error} retry={() => jobs.refetch()} /> : !jobs.data ? (
        <div className="grid gap-4 md:grid-cols-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-36" />)}</div>
      ) : jobs.data.length === 0 ? <EmptyState icon={<BriefcaseBusiness className="size-8" />} title={dq ? "No jobs match your search" : "No open positions right now"} description="Check back soon." /> : (
        <div className="grid gap-4 md:grid-cols-2">
          {jobs.data.map((j) => (
            <Link key={j.id} href={`/candidate/jobs/${j.id}`}>
              <Card className="h-full transition-shadow hover:shadow-md"><CardContent className="space-y-3 pt-5">
                <div className="flex items-start justify-between gap-2">
                  <div><p className="font-semibold">{j.title}</p><p className="mt-0.5 flex flex-wrap gap-x-3 text-xs text-muted-foreground">{j.department && <span>{j.department}</span>}{j.location && <span className="inline-flex items-center gap-1"><MapPin className="size-3" />{j.location}</span>}<span>{titleCase(j.employment_type)} · {titleCase(j.work_mode)}</span></p></div>
                  {j.has_applied && <Badge variant="success"><CheckCircle2 /> Applied</Badge>}
                </div>
                <SkillChips skills={j.required_skills} max={5} />
                <p className="text-xs text-muted-foreground">{fmtSalary(j.salary_min, j.salary_max, j.currency)}{fmtSalary(j.salary_min, j.salary_max, j.currency) ? " · " : ""}Posted {fmtDate(j.created_at)}</p>
              </CardContent></Card>
            </Link>
          ))}
        </div>
      )}
      <p className="mt-8 text-center"><Button variant="link" asChild><Link href="/candidate/resume">Manage your resume</Link></Button></p>
    </>
  );
}
