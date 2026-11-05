"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { CalendarDays, ChevronLeft, ChevronRight, List } from "lucide-react";
import { api, qs } from "@/lib/api";
import type { InterviewOut } from "@/lib/types";
import { fmtDateTime, fmtTime, titleCase } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DateTile } from "@/components/app/common";
import { InterviewDetailDialog, InterviewStatusPill } from "@/components/app/application/interview-detail";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";
import { cn } from "@/lib/utils";
import { FeedbackDialog, ScheduleDialog } from "@/components/app/application/interviews-tab";

function startOfWeek(d: Date) {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  x.setDate(x.getDate() - ((x.getDay() + 6) % 7));
  return x;
}

export default function InterviewsPage() {
  const [view, setView] = useState<"week" | "list">("week");
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const [resched, setResched] = useState<InterviewOut | null>(null);
  const [fb, setFb] = useState<InterviewOut | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const from = view === "week" ? weekStart : undefined;
  const to = useMemo(() => (from ? new Date(from.getTime() + 7 * 86_400_000) : undefined), [from]);
  const q = useQuery({
    queryKey: ["interviews", view, from?.toISOString()],
    queryFn: () => api<InterviewOut[]>(`/interviews${qs({ from: from?.toISOString(), to: to?.toISOString() })}`),
    refetchInterval: 30_000,
  });
  const days = Array.from({ length: 7 }, (_, i) => new Date(weekStart.getTime() + i * 86_400_000));
  const sorted = [...(q.data ?? [])].sort((a, b) => +new Date(a.start_at) - +new Date(b.start_at));
  const today = new Date().toDateString();
  const detail = q.data?.find((x) => x.id === detailId) ?? null;

  const card = (iv: InterviewOut) => (
    <div key={iv.id} className={cn("rounded-xl border p-2.5 text-xs", iv.status === "cancelled" ? "opacity-50" : "bg-primary/8", iv.has_conflict && "border-warning")}>
      <p className="font-medium">{fmtTime(iv.start_at)} · {iv.candidate_name}</p>
      <p className="text-muted-foreground">{iv.job_title} · {titleCase(iv.interview_type)}</p>
      <p className="text-muted-foreground">with {iv.interviewer_name}</p>
      <div className="mt-1 flex flex-wrap gap-1">
        {iv.status !== "scheduled" && <Badge variant="muted">{iv.status}</Badge>}{iv.has_conflict && <Badge variant="warning">conflict</Badge>}
        <button className="text-primary hover:underline" onClick={() => setDetailId(iv.id)}>Details</button>
        <Link href={`/recruiter/applications/${iv.application_id}`} className="text-primary hover:underline">Open</Link>
        {iv.status === "scheduled" && <button className="text-primary hover:underline" onClick={() => setResched(iv)}>Reschedule</button>}
        <button className="text-primary hover:underline" onClick={() => setFb(iv)}>Feedback</button>
      </div>
    </div>
  );

  return (
    <>
      <PageHeader title="Interviews" description="Schedule from a shortlisted candidate’s page; manage everything here." actions={
        <div className="flex gap-1 rounded-full bg-muted p-1">
          <Button size="sm" variant={view === "week" ? "outline" : "ghost"} onClick={() => setView("week")}><CalendarDays /> Week</Button>
          <Button size="sm" variant={view === "list" ? "outline" : "ghost"} onClick={() => setView("list")}><List /> List</Button>
        </div>} />
      {view === "week" && (
        <div className="mb-4 flex items-center gap-2">
          <Button variant="outline" size="icon" aria-label="Previous week" onClick={() => setWeekStart(new Date(weekStart.getTime() - 7 * 86_400_000))}><ChevronLeft /></Button>
          <Button variant="outline" onClick={() => setWeekStart(startOfWeek(new Date()))}>Today</Button>
          <Button variant="outline" size="icon" aria-label="Next week" onClick={() => setWeekStart(new Date(weekStart.getTime() + 7 * 86_400_000))}><ChevronRight /></Button>
          <span className="text-sm font-medium">{days[0].toLocaleDateString(undefined, { month: "short", day: "numeric" })} – {days[6].toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}</span>
        </div>
      )}
      {q.isError ? <ErrorState error={q.error} retry={() => q.refetch()} /> : !q.data ? <Skeleton className="h-96" /> : view === "week" ? (
        <div className="grid gap-2 md:grid-cols-7">
          {days.map((d) => {
            const items = sorted.filter((iv) => new Date(iv.start_at).toDateString() === d.toDateString());
            return (
              <Card key={d.toISOString()} className={cn("min-h-40 space-y-2 p-2", d.toDateString() === today && "border-primary")}>
                <p className={cn("text-xs font-semibold", d.toDateString() === today ? "text-primary" : "text-muted-foreground")}>{d.toLocaleDateString(undefined, { weekday: "short", day: "numeric" })}</p>
                {items.map(card)}
              </Card>
            );
          })}
        </div>
      ) : sorted.length === 0 ? <EmptyState title="No interviews" description="Shortlist a candidate and schedule an interview from their page." /> : (
        <div className="space-y-3">{sorted.map((iv) => (
          <Card key={iv.id} className="flex flex-wrap items-center gap-4 p-4 transition-shadow hover:shadow-md">
            <DateTile iso={iv.start_at} />
            <div className="min-w-0 flex-1">
              <p className="font-semibold">{iv.candidate_name} <span className="font-normal text-muted-foreground">· {iv.job_title}</span></p>
              <p className="text-sm text-muted-foreground">{fmtDateTime(iv.start_at)} · {titleCase(iv.interview_type)} with {iv.interviewer_name}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2"><InterviewStatusPill status={iv.status} />{iv.has_conflict && <Badge variant="warning">conflict</Badge>}
              {iv.status === "scheduled" && <Button size="sm" variant="outline" onClick={() => setResched(iv)}>Reschedule</Button>}
              <Button size="sm" variant="outline" onClick={() => setFb(iv)}>Feedback</Button>
              <Button size="sm" onClick={() => setDetailId(iv.id)}>Details</Button><Button size="sm" variant="ghost" asChild><Link href={`/recruiter/applications/${iv.application_id}`}>Open</Link></Button></div>
          </Card>))}</div>
      )}
      {detail && <InterviewDetailDialog iv={detail} open onOpenChange={(o) => !o && setDetailId(null)} onReschedule={() => { setDetailId(null); setResched(detail); }} onFeedback={() => { setDetailId(null); setFb(detail); }} />}
      {resched && <ScheduleDialog key={resched.id} appId={resched.application_id} existing={resched} open onOpenChange={(o) => !o && setResched(null)} />}
      {fb && <FeedbackDialog key={fb.id} iv={fb} open onOpenChange={(o) => !o && setFb(null)} />}
    </>
  );
}
