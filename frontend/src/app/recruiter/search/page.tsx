"use client";
import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ExternalLink, Quote, Search, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import type { JobListItem, TalentSearchOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Select, Textarea } from "@/components/ui/input";
import { Banner, EmptyState, PageHeader } from "@/components/ui/misc";
import { friendlyError } from "@/lib/errors";
import { ScoreBar, SkillChips, StatusBadge, notifyError } from "@/components/app/common";

export default function TalentSearch() {
  const [query, setQuery] = useState("");
  const [jobId, setJobId] = useState("");
  const jobs = useQuery({ queryKey: ["jobs", "all"], queryFn: () => api<JobListItem[]>("/jobs") });
  const m = useMutation({ mutationFn: () => api<TalentSearchOut>("/search/talent", { body: { query: query.trim(), job_id: jobId || null, limit: 20 } }), onError: notifyError });
  const r = m.data;
  return (
    <>
      <PageHeader title="Talent search" description="Describe who you’re looking for in natural language — results are ranked by how closely they match your description and by skill coverage, with evidence." />
      <form onSubmit={(e) => { e.preventDefault(); if (query.trim().length >= 3) m.mutate(); }} className="mb-6 space-y-3">
        <Textarea aria-label="Search query" rows={3} placeholder="e.g. Backend engineer with Django and PostgreSQL experience who has shipped Dockerized services" value={query} onChange={(e) => setQuery(e.target.value)} />
        <div className="flex flex-wrap gap-2">
          <Select aria-label="Restrict to job applicants" className="w-64" value={jobId} onChange={(e) => setJobId(e.target.value)}><option value="">All candidates</option>{jobs.data?.map((j) => <option key={j.id} value={j.id}>Applicants of: {j.title}</option>)}</Select>
          <Button type="submit" loading={m.isPending} disabled={query.trim().length < 3}><Search /> Search</Button>
        </div>
      </form>
      {r && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-sm"><Sparkles className="size-4 text-primary" />Detected skills: {r.detected_skills.length ? r.detected_skills.map((s) => <Badge key={s}>{s}</Badge>) : <span className="text-muted-foreground">none</span>}<Badge variant="outline">{r.mode}</Badge></div>
          {r.warning && <Banner tone="warning">{friendlyError(r.warning, "Results may be less precise than usual this time.")}</Banner>}
          {r.results.length === 0 ? <EmptyState title="No matching candidates" description="Try broader wording or fewer constraints." /> : r.results.map((x) => (
            <Card key={x.candidate.id}><CardContent className="space-y-3 pt-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><p className="font-semibold">{x.candidate.full_name} {x.in_talent_pool && <Badge variant="success">Talent pool</Badge>}</p><p className="text-xs text-muted-foreground">{[x.candidate.headline, x.candidate.location, x.candidate.email].filter(Boolean).join(" · ")}</p></div>
                <div className="w-36"><ScoreBar value={x.score} /></div>
              </div>
              <SkillChips skills={x.matched_skills} tone="success" max={10} />
              {x.evidence.slice(0, 2).map((e, i) => <p key={i} className="flex items-start gap-2 rounded-md border bg-muted/40 p-2 text-xs italic"><Quote className="mt-0.5 size-3 shrink-0" />“{e.quote}”</p>)}
              <div className="flex flex-wrap items-center gap-2">
                {x.applications.map((a) => <Link key={a.application_id} href={`/recruiter/applications/${a.application_id}`} className="inline-flex items-center gap-1 text-xs hover:underline">{a.job_title} <StatusBadge status={a.status} /></Link>)}
                <Button variant="link" size="sm" asChild className="ml-auto"><a href={`/api/resumes/${x.resume_id}/file`} target="_blank" rel="noreferrer"><ExternalLink /> Resume</a></Button>
              </div>
            </CardContent></Card>
          ))}
        </div>
      )}
    </>
  );
}
