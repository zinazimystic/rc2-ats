"use client";
import { useState } from "react";
import Link from "next/link";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { BriefcaseBusiness, CalendarCheck, ClipboardCheck, Plus, Star, Trophy, UserX, Users } from "lucide-react";
import { api, qs } from "@/lib/api";
import type { AnalyticsOut, InterviewOut, JobListItem } from "@/lib/types";
import { STATUS_LABEL, STATUS_ORDER, fmtDateTime, timeAgo, titleCase } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";
import { DateTile, MiniCalendar, Stat } from "@/components/app/common";
import { FunnelCard, GapsCard, JobFlowCard, ScoreCard, ShortlistGauge, fmtDuration } from "@/components/charts/dashboard-charts";

export default function Dashboard() {
  const [jobId, setJobId] = useState("");
  const [now] = useState(() => Date.now());
  const jobs = useQuery({ queryKey: ["jobs", "all"], queryFn: () => api<JobListItem[]>("/jobs"), staleTime: 45_000 });
  const q = useQuery({
    queryKey: ["analytics", jobId],
    queryFn: () => api<AnalyticsOut>(`/analytics/overview${qs({ job_id: jobId })}`),
    refetchInterval: 10_000,
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });
  const ivs = useQuery({ queryKey: ["interviews", "dash"], queryFn: () => api<InterviewOut[]>("/interviews"), retry: false });
  const upcoming = (ivs.data ?? []).filter((iv) => iv.status === "scheduled" && new Date(iv.end_at).getTime() >= now).sort((a, b) => a.start_at.localeCompare(b.start_at)).slice(0, 4);
  const d = q.data;
  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Pipeline health across your jobs, updated live."
        actions={
          <>
            <Select aria-label="Filter by job" value={jobId} onChange={(e) => setJobId(e.target.value)} className="w-56">
              <option value="">All jobs</option>
              {jobs.data?.map((j) => <option key={j.id} value={j.id}>{j.title}</option>)}
            </Select>
            <Button asChild><Link href="/recruiter/jobs/new"><Plus /> New job</Link></Button>
          </>
        }
      />
      {q.isError ? (
        <ErrorState error={q.error} retry={() => q.refetch()} />
      ) : !d || (ivs.isPending && !ivs.data) ? (
        <div className="space-y-6" aria-busy="true" aria-label="Loading dashboard">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-36 rounded-3xl" />)}</div>
          <div className="grid gap-4 lg:grid-cols-[1fr_340px]"><Skeleton className="h-72 rounded-3xl" /><Skeleton className="h-72 rounded-3xl" /></div>
        </div>
      ) : d.kpis.total_applications === 0 && d.kpis.total_jobs === 0 ? (
        <EmptyState title="No data yet" description="Create your first job and share it with candidates to see analytics." action={<Button asChild><Link href="/recruiter/jobs/new">Create a job</Link></Button>} />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat highlight label="Active jobs" value={d.kpis.active_jobs} icon={<BriefcaseBusiness />} hint={`${d.kpis.total_jobs} total`} />
            <Stat label="Applications" value={d.kpis.total_applications} icon={<Users />} />
            <Stat label="Pending review" value={d.kpis.pending_reviews} icon={<ClipboardCheck />} />
            <Stat label="Shortlisted" value={d.kpis.shortlisted} icon={<Star />} hint={d.shortlist_rate != null ? `${Math.round(d.shortlist_rate * 100)}% shortlist rate` : undefined} />
            <Stat label="Interviews scheduled" value={d.kpis.interviews_scheduled} icon={<CalendarCheck />} />
            <Stat label="Selected" value={d.kpis.selected} icon={<Trophy />} />
            <Stat label="Rejected" value={d.kpis.rejected} icon={<UserX />} />
            <Stat
              label="Avg. AI processing"
              value={fmtDuration(d.avg_processing_seconds)}
              hint={d.avg_time_to_decision_hours != null ? `${fmtDuration(d.avg_time_to_decision_hours, "h")} to decision` : undefined}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
            <Card>
              <CardHeader className="flex-row items-center justify-between"><CardTitle>Upcoming interviews</CardTitle><Button asChild variant="ghost" size="sm"><Link href="/recruiter/interviews">View all</Link></Button></CardHeader>
              <CardContent>
                {upcoming.length === 0 ? <p className="py-8 text-center text-sm text-muted-foreground">No upcoming interviews.</p> : (
                  <ul className="space-y-3">{upcoming.map((iv) => (
                    <li key={iv.id}>
                      <Link href={`/recruiter/applications/${iv.application_id}`} className="flex items-center gap-4 rounded-2xl border border-border/60 p-3 transition-colors hover:bg-muted/60">
                        <DateTile iso={iv.start_at} />
                        <div className="min-w-0 flex-1"><p className="truncate font-semibold">{iv.candidate_name}</p><p className="truncate text-sm text-muted-foreground">{iv.job_title} · {titleCase(iv.interview_type)}</p></div>
                        <span className="hidden shrink-0 text-[13px] text-muted-foreground sm:block">{fmtDateTime(iv.start_at)}</span>
                      </Link>
                    </li>))}</ul>
                )}
              </CardContent>
            </Card>
            <Card><CardHeader><CardTitle>Calendar</CardTitle></CardHeader><CardContent><MiniCalendar marked={(ivs.data ?? []).map((iv) => iv.start_at)} /></CardContent></Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
            <FunnelCard data={d} />
            <ShortlistGauge data={d} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <ScoreCard data={d} />
            <GapsCard data={d} />
          </div>

          {!jobId && <JobFlowCard data={d} />}

          <Card>
            <CardHeader><CardTitle>Recent activity</CardTitle></CardHeader>
            <CardContent>
              {d.recent_activity.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">Nothing yet.</p>
              ) : (
                <ul className="divide-y">
                  {d.recent_activity.map((a, i) => (
                    <li key={i} className="flex items-center justify-between gap-3 py-2 text-sm">
                      {a.application_id ? <Link className="hover:underline" href={`/recruiter/applications/${a.application_id}`}>{a.text}</Link> : <span>{a.text}</span>}
                      <span className="shrink-0 text-[13px] text-muted-foreground">{timeAgo(a.at)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
