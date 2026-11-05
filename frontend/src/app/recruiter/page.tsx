"use client";
import { useState } from "react";
import Link from "next/link";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BriefcaseBusiness, CalendarCheck, ClipboardCheck, Plus, Star, Trophy, UserX, Users } from "lucide-react";
import { api, qs } from "@/lib/api";
import type { AnalyticsOut, InterviewOut, JobListItem } from "@/lib/types";
import { STATUS_LABEL, STATUS_ORDER, fmtDateTime, timeAgo, titleCase } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";
import { DateTile, MiniCalendar, Stat } from "@/components/app/common";

const COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];
const STAGE_COLOR: Record<string, string> = {
  submitted: "var(--muted-foreground)", parsed: "var(--chart-2)", ai_assessed: "var(--chart-1)",
  recruiter_review: "var(--chart-4)", shortlisted: "var(--chart-3)", interview: "var(--chart-1)",
  selected: "var(--success)", rejected: "var(--destructive)", withdrawn: "var(--border)",
};

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
            <Stat label="Shortlisted" value={d.kpis.shortlisted} icon={<Star />} hint={d.shortlist_rate != null ? `${d.shortlist_rate.toFixed(0)}% shortlist rate` : undefined} />
            <Stat label="Interviews scheduled" value={d.kpis.interviews_scheduled} icon={<CalendarCheck />} />
            <Stat label="Selected" value={d.kpis.selected} icon={<Trophy />} />
            <Stat label="Rejected" value={d.kpis.rejected} icon={<UserX />} />
            <Stat
              label="Avg. AI processing"
              value={d.avg_processing_seconds != null ? `${d.avg_processing_seconds.toFixed(1)}s` : "—"}
              hint={d.avg_time_to_decision_hours != null ? `${d.avg_time_to_decision_hours.toFixed(1)}h to decision` : undefined}
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
                        <span className="hidden shrink-0 text-xs text-muted-foreground sm:block">{fmtDateTime(iv.start_at)}</span>
                      </Link>
                    </li>))}</ul>
                )}
              </CardContent>
            </Card>
            <Card><CardHeader><CardTitle>Calendar</CardTitle></CardHeader><CardContent><MiniCalendar marked={(ivs.data ?? []).map((iv) => iv.start_at)} /></CardContent></Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader><CardTitle>Hiring funnel</CardTitle><CardDescription>Applications by pipeline stage</CardDescription></CardHeader>
              <CardContent className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={d.stage_funnel} layout="vertical" margin={{ left: 20 }}>
                    <CartesianGrid horizontal={false} stroke="var(--border)" />
                    <XAxis type="number" allowDecimals={false} stroke="var(--muted-foreground)" fontSize={12} />
                    <YAxis type="category" dataKey="label" width={130} stroke="var(--muted-foreground)" fontSize={12} />
                    <Tooltip cursor={{ fill: "var(--muted)" }} contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 8 }} />
                    <Bar dataKey="count" radius={[0, 10, 10, 0]}>
                      {d.stage_funnel.map((s) => <Cell key={s.stage} fill={STAGE_COLOR[s.stage] ?? COLORS[0]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>AI score distribution</CardTitle><CardDescription>How applicants score against requirements</CardDescription></CardHeader>
              <CardContent className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={d.score_distribution}>
                    <CartesianGrid vertical={false} stroke="var(--border)" />
                    <XAxis dataKey="bucket" stroke="var(--muted-foreground)" fontSize={12} />
                    <YAxis allowDecimals={false} stroke="var(--muted-foreground)" fontSize={12} />
                    <Tooltip cursor={{ fill: "var(--muted)" }} contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 8 }} />
                    <Bar dataKey="count" fill="var(--chart-1)" radius={[10, 10, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
            {!jobId && d.applications_by_job.length > 0 && (
              <Card>
                <CardHeader><CardTitle>Applications by job</CardTitle><CardDescription>Stacked by stage</CardDescription></CardHeader>
                <CardContent className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={d.applications_by_job.map((j) => ({ title: j.title, ...j.by_stage }))}>
                      <CartesianGrid vertical={false} stroke="var(--border)" />
                      <XAxis dataKey="title" stroke="var(--muted-foreground)" fontSize={12} />
                      <YAxis allowDecimals={false} stroke="var(--muted-foreground)" fontSize={12} />
                      <Tooltip contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 8 }} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      {STATUS_ORDER.map((s) => <Bar key={s} dataKey={s} name={STATUS_LABEL[s]} stackId="a" fill={STAGE_COLOR[s]} />)}
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            )}
            <Card>
              <CardHeader><CardTitle>Top skill gaps</CardTitle><CardDescription>Required skills most often lacking evidence</CardDescription></CardHeader>
              <CardContent>
                {d.top_skill_gaps.length === 0 ? (
                  <p className="py-8 text-center text-sm text-muted-foreground">No gaps detected yet.</p>
                ) : (
                  <ul className="space-y-3">
                    {d.top_skill_gaps.map((g) => (
                      <li key={g.skill}>
                        <div className="mb-1 flex justify-between text-sm"><span className="font-medium">{g.skill}</span><span className="text-muted-foreground">{g.count} · {g.percent.toFixed(0)}%</span></div>
                        <div className="h-2 rounded-full bg-muted"><div className="h-full rounded-full bg-destructive/70" style={{ width: `${Math.min(100, g.percent)}%` }} /></div>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

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
                      <span className="shrink-0 text-xs text-muted-foreground">{timeAgo(a.at)}</span>
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
