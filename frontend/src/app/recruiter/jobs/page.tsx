"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { BriefcaseBusiness, MapPin, Plus, Search } from "lucide-react";
import { api, qs } from "@/lib/api";
import type { JobListItem } from "@/lib/types";
import { fmtDate, fmtSalary, titleCase } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";
import { SkillChips } from "@/components/app/common";
import { cn } from "@/lib/utils";

export default function JobsPage() {
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const query = useQuery({
    queryKey: ["jobs", status, q],
    queryFn: () => api<JobListItem[]>(`/jobs${qs({ status, q })}`),
    placeholderData: (p) => p,
  });
  return (
    <>
      <PageHeader title="Jobs" description="Your postings and their applicant pipelines." actions={<Button asChild><Link href="/recruiter/jobs/new"><Plus /> New job</Link></Button>} />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-xs">
          <Search className="pointer-events-none absolute top-2.5 left-3 size-4 text-muted-foreground" />
          <Input aria-label="Search jobs" placeholder="Search jobs…" className="pl-9" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div role="group" aria-label="Status filter" className="flex gap-1 rounded-full bg-muted p-1">
          {[["", "All"], ["open", "Open"], ["closed", "Closed"]].map(([v, l]) => (
            <button key={v} onClick={() => setStatus(v)} aria-pressed={status === v} className={cn("rounded-full px-4 py-1.5 text-sm font-medium transition-colors", status === v ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground")}>{l}</button>
          ))}
        </div>
      </div>
      {query.isError ? <ErrorState error={query.error} retry={() => query.refetch()} /> : !query.data ? (
        <div className="grid gap-4 md:grid-cols-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-40 rounded-2xl" />)}</div>
      ) : query.data.length === 0 ? (
        <EmptyState icon={<BriefcaseBusiness className="size-8" />} title={q || status ? "No jobs match your filters" : "No jobs yet"} description="Post a job to start receiving evidence-ranked applications." action={<Button asChild><Link href="/recruiter/jobs/new">Create job</Link></Button>} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {query.data.map((j) => (
            <Link key={j.id} href={`/recruiter/jobs/${j.id}`} className="group rounded-2xl">
              <Card className="h-full space-y-3 p-5 transition-all group-hover:-translate-y-0.5 group-hover:shadow-lg">
                <div className="flex items-start justify-between gap-2">
                  <span className="grid size-11 shrink-0 place-items-center rounded-2xl bg-primary/10 text-lg font-bold text-primary">{j.title.slice(0, 1).toUpperCase()}</span>
                  <div className="min-w-0 flex-1">
                    <h2 className="truncate font-semibold group-hover:text-primary">{j.title}</h2>
                    <p className="mt-0.5 flex flex-wrap items-center gap-x-3 text-xs text-muted-foreground">
                      {j.department && <span>{j.department}</span>}
                      {j.location && <span className="inline-flex items-center gap-1"><MapPin className="size-3" />{j.location}</span>}
                      <span>{titleCase(j.employment_type)} · {titleCase(j.work_mode)}</span>
                    </p>
                  </div>
                  <Badge variant={j.status === "open" ? "success" : "muted"}>{titleCase(j.status)}</Badge>
                </div>
                <SkillChips skills={j.required_skills} max={5} />
                <div className="grid grid-cols-3 gap-2 border-t pt-3 text-center text-sm [&_strong]:block [&_strong]:text-xl [&_strong]:tabular-nums">
                  <span><strong>{j.applicant_count}</strong> applicants</span>
                  <span className="text-success"><strong>{j.shortlisted_count}</strong> shortlisted</span>
                  <span className="text-muted-foreground"><strong>{j.pending_review_count}</strong> to review</span>
                </div>
                <p className="text-xs text-muted-foreground">{fmtSalary(j.salary_min, j.salary_max, j.currency)} {fmtSalary(j.salary_min, j.salary_max, j.currency) && "·"} Posted {fmtDate(j.created_at)}</p>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
