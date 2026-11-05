"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { BriefcaseBusiness, CheckCircle2, MapPin, Search, Sparkles } from "lucide-react";
import type { CandidateDashboardOut, JobListItem } from "@/lib/types";
import { fmtDate, fmtDateTime, fmtSalary, titleCase } from "@/lib/format";
import { usePrefetch, useCandidateDashboard } from "@/lib/queries";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/misc";
import { Notice } from "@/components/ui/notice";
import { DateTile, MatchBadge, MiniCalendar, SkillChips } from "@/components/app/common";
import { useDebounced } from "@/lib/hooks";

function Logo({ name }: { name: string }) {
  return <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-primary/10 text-lg font-bold text-primary">{name.slice(0, 1).toUpperCase()}</span>;
}

/** Matches the final layout so the page swaps to content in one step, with no shifting. */
function HomeSkeleton() {
  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_340px]" aria-busy="true" aria-label="Loading jobs">
      <div className="min-w-0">
        <Skeleton className="mb-4 h-7 w-52" />
        <div className="mb-8 grid gap-4 md:grid-cols-2">{[0, 1].map((i) => <Skeleton key={i} className="h-48 rounded-3xl" />)}</div>
        <Skeleton className="mb-4 h-7 w-40" />
        <div className="grid gap-4 md:grid-cols-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-36 rounded-3xl" />)}</div>
      </div>
      <div className="space-y-6">
        <Skeleton className="h-64 rounded-3xl" />
        <Skeleton className="h-40 rounded-3xl" />
        <Skeleton className="h-48 rounded-3xl" />
      </div>
    </div>
  );
}

function matches(j: JobListItem, q: string) {
  const hay = [j.title, j.department, j.location, ...j.required_skills, ...j.preferred_skills].filter(Boolean).join(" ").toLowerCase();
  return q.split(/\s+/).every((t) => hay.includes(t));
}

function Content({ d, dq }: { d: CandidateDashboardOut; dq: string }) {
  const prefetch = usePrefetch();
  const needle = dq.trim().toLowerCase();
  const jobs = useMemo(() => (needle ? d.open_jobs.filter((j) => matches(j, needle)) : d.open_jobs), [d.open_jobs, needle]);
  const meetings = d.upcoming_interviews.slice(0, 3);
  const activity = d.applications.slice(0, 3);
  const recs = d.recommendations ?? [];
  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
      <div className="min-w-0">
        {recs.length > 0 && !needle && (
          <section className="mb-8" aria-labelledby="rec-h">
            <h2 id="rec-h" className="mb-4 flex items-center gap-2 text-xl font-semibold"><Sparkles className="size-5 text-primary" />Recommended jobs</h2>
            <div className="grid gap-4 md:grid-cols-2">
              {recs.map((r) => (
                <Card key={r.job.id} className="flex h-full flex-col gap-3 p-5 transition-shadow hover:shadow-lg" onMouseEnter={() => prefetch(`/candidate/jobs/${r.job.id}`)}>
                  <div className="flex items-start gap-3">
                    <Logo name={r.job.title} />
                    <div className="min-w-0 flex-1"><p className="font-semibold">{r.job.title}</p></div>
                    <MatchBadge score={r.score} />
                  </div>
                  <p className="text-sm text-muted-foreground">{r.reason}</p>
                  <SkillChips skills={r.matched_skills} tone="success" max={4} />
                  {r.missing_skills.length > 0 && <p className="text-xs text-muted-foreground">To strengthen: {r.missing_skills.slice(0, 3).join(", ")}</p>}
                  <div className="mt-auto flex items-center justify-end gap-2 pt-2">
                    <Button size="sm" variant="outline" asChild><Link href={`/candidate/jobs/${r.job.id}`}>Details</Link></Button>
                    <Button size="sm" asChild><Link href={`/candidate/jobs/${r.job.id}`}>Apply</Link></Button>
                  </div>
                </Card>
              ))}
            </div>
          </section>
        )}
        {d.resumes.length === 0 && !needle && (
          <Notice tone="info" title="Get personalised recommendations" className="mb-6" action={undefined}>Upload a resume to see jobs matched to you. <Link href="/candidate/resume" className="font-medium underline">Upload now</Link></Notice>
        )}
        <h2 className="mb-4 text-xl font-semibold">{needle ? `Search results (${jobs.length})` : "All open jobs"}</h2>
        {jobs.length === 0 ? (
          <EmptyState icon={<BriefcaseBusiness className="size-8" />} title={needle ? "No jobs match your search" : "No open positions right now"} description={needle ? "Try a different title, skill or location." : "Check back soon."} />
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {jobs.map((j) => {
              const salary = fmtSalary(j.salary_min, j.salary_max, j.currency);
              return (
                <Link key={j.id} href={`/candidate/jobs/${j.id}`} onMouseEnter={() => prefetch(`/candidate/jobs/${j.id}`)} onFocus={() => prefetch(`/candidate/jobs/${j.id}`)} className="rounded-3xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
                  <Card className="h-full transition-all hover:-translate-y-0.5 hover:shadow-lg"><CardContent className="space-y-3 pt-5">
                    <div className="flex items-start gap-3">
                      <Logo name={j.title} />
                      <div className="min-w-0 flex-1"><p className="font-semibold">{j.title}</p><p className="mt-0.5 flex flex-wrap gap-x-3 text-xs text-muted-foreground">{j.department && <span>{j.department}</span>}{j.location && <span className="inline-flex items-center gap-1"><MapPin className="size-3" />{j.location}</span>}<span>{titleCase(j.employment_type)} · {titleCase(j.work_mode)}</span></p></div>
                      {j.has_applied && <Badge variant="success"><CheckCircle2 /> Applied</Badge>}
                    </div>
                    <SkillChips skills={j.required_skills} max={5} />
                    <p className="text-xs text-muted-foreground">{salary}{salary ? " · " : ""}Posted {fmtDate(j.created_at)}</p>
                  </CardContent></Card>
                </Link>
              );
            })}
          </div>
        )}
        <p className="mt-8 text-center"><Button variant="link" asChild><Link href="/candidate/resume">Manage your resume</Link></Button></p>
      </div>

      <aside className="space-y-6" aria-label="Schedule and activity">
        <Card><CardContent className="pt-5"><MiniCalendar marked={meetings.map((m) => m.start_at)} /></CardContent></Card>
        <Card>
          <CardHeader><CardTitle>Upcoming meetings</CardTitle></CardHeader>
          <CardContent>
            {meetings.length === 0 ? <p className="py-4 text-center text-sm text-muted-foreground">No meetings scheduled.</p> : (
              <ul className="space-y-3">{meetings.map((m) => (
                <li key={m.id} className="flex items-center gap-3 rounded-2xl bg-muted/60 p-3">
                  <DateTile iso={m.start_at} className="size-12" />
                  <div className="min-w-0 text-sm"><p className="truncate font-semibold">{m.job_title}</p><p className="truncate text-xs text-muted-foreground">{titleCase(m.interview_type)} · {fmtDateTime(m.start_at)}</p></div>
                </li>))}</ul>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Job activity</CardTitle></CardHeader>
          <CardContent>
            {activity.length === 0 ? <p className="py-4 text-center text-sm text-muted-foreground">No applications yet.</p> : (
              <ul className="space-y-5">{activity.map((a) => {
                const steps = a.timeline.slice(-4);
                return (
                  <li key={a.id}>
                    <div className="flex items-center justify-between gap-2"><p className="truncate text-sm font-semibold">{a.job.title}</p><Badge variant="default">{a.status_label}</Badge></div>
                    <ol className="mt-3 flex items-center" aria-label="Progress">
                      {steps.map((t, i) => (
                        <li key={i} className="flex flex-1 items-center last:flex-none" title={t.label}>
                          <span className={i === steps.length - 1 ? "size-3 rounded-full bg-primary ring-4 ring-primary/20" : "size-3 rounded-full bg-primary"} />
                          {i < steps.length - 1 && <span className="h-0.5 flex-1 bg-primary/40" />}
                        </li>
                      ))}
                    </ol>
                    <p className="mt-2 truncate text-xs text-muted-foreground">{steps.length ? steps[steps.length - 1].label : ""}</p>
                  </li>
                );
              })}</ul>
            )}
          </CardContent>
        </Card>
      </aside>
    </div>
  );
}

export default function CandidateHome() {
  const [q, setQ] = useState("");
  const dq = useDebounced(q, 150);
  const dash = useCandidateDashboard();
  return (
    <>
      <section className="relative mb-8 overflow-hidden rounded-3xl bg-gradient-to-br from-[#14161c] via-[#1f2a4a] to-[#2f6bff] p-8 text-white shadow-soft sm:p-10">
        <div className="absolute -right-16 -bottom-20 size-72 rounded-full bg-primary/40 blur-3xl" aria-hidden />
        <h1 className="relative max-w-lg text-3xl leading-tight font-bold tracking-tight sm:text-4xl">Find your next role</h1>
        <p className="relative mt-2 max-w-md text-sm text-white/75">Open positions and jobs matched to your resume.</p>
        <div className="relative mt-6 flex max-w-xl items-center gap-2 rounded-full bg-white p-1.5 shadow-xl">
          <Search className="ml-3 size-5 shrink-0 text-slate-400" />
          <input aria-label="Search jobs" placeholder="Search by title, skill or location…" className="h-10 min-w-0 flex-1 bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400" value={q} onChange={(e) => setQ(e.target.value)} />
          <span className="inline-flex h-10 items-center rounded-full bg-primary px-6 text-sm font-medium text-white">Search</span>
        </div>
      </section>
      {dash.isError && !dash.data ? <ErrorState error={dash.error} retry={() => dash.refetch()} /> : !dash.data ? <HomeSkeleton /> : <Content d={dash.data} dq={dq} />}
    </>
  );
}
