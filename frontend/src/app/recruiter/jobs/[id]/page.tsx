"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { toast } from "@/lib/toast";
import { GitCompareArrows, Lock, Pencil, Unlock, UserPlus, Users } from "lucide-react";
import { api, qs } from "@/lib/api";
import type { ApplicationRowOut, JobApplicantsOut, JobOut, TalentPoolItem } from "@/lib/types";
import { STATUS_LABEL, STATUS_ORDER, fmtDate, fmtSalary, fmtScore, titleCase } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox, Input, Select } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Banner, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";
import { ProcessingBadge, ScoreBar, SkillChips, StatusBadge, notifyError } from "@/components/app/common";
import { useDebounced } from "@/lib/hooks";

const col = createColumnHelper<ApplicationRowOut>();

function Applicants({ jobId }: { jobId: string }) {
  const router = useRouter();
  const [status, setStatus] = useState("");
  const [minScore, setMinScore] = useState("");
  const [skill, setSkill] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("score");
  const [picked, setPicked] = useState<string[]>([]);
  const dSkill = useDebounced(skill), dSearch = useDebounced(search), dMin = useDebounced(minScore);

  const q = useQuery({
    queryKey: ["applicants", jobId, status, dMin, dSkill, dSearch, sort],
    queryFn: () => api<JobApplicantsOut>(`/jobs/${jobId}/applications${qs({ status, min_score: dMin, skill: dSkill, q: dSearch, sort })}`),
    placeholderData: (p) => p,
    refetchInterval: (query) => (query.state.data?.items.some((a) => a.processing_state === "queued" || a.processing_state === "processing") ? 2000 : false),
  });

  const toggle = (id: string) =>
    setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length >= 4 ? (toast.info("You can compare up to 4 candidates"), p) : [...p, id]));

  const columns = useMemo(
    () => [
      col.display({
        id: "pick",
        header: () => <span className="sr-only">Select</span>,
        cell: ({ row }) => (
          <Checkbox aria-label={`Select ${row.original.candidate.full_name} to compare`} checked={picked.includes(row.original.id)} onChange={() => toggle(row.original.id)} onClick={(e) => e.stopPropagation()} />
        ),
      }),
      col.display({ id: "rank", header: "#", cell: ({ row }) => <span className="text-muted-foreground">{row.index + 1}</span> }),
      col.accessor((r) => r.candidate.full_name, {
        id: "candidate",
        header: "Candidate",
        cell: ({ row }) => (
          <div className="min-w-40">
            <Link href={`/recruiter/applications/${row.original.id}`} className="font-medium hover:text-primary hover:underline" onClick={(e) => e.stopPropagation()}>{row.original.candidate.full_name}</Link>
            <p className="text-xs text-muted-foreground">{row.original.candidate.headline ?? row.original.candidate.email}</p>
            {row.original.is_duplicate && <Badge variant="warning" className="mt-1">Possible duplicate</Badge>}
          </div>
        ),
      }),
      col.accessor("effective_score", {
        header: "Score",
        cell: ({ row }) =>
          row.original.processing_state !== "done" && row.original.effective_score == null ? (
            <ProcessingBadge state={row.original.processing_state} error={row.original.processing_error} />
          ) : (
            <div>
              <ScoreBar value={row.original.effective_score} />
              {row.original.override_score != null && <span className="text-xs text-muted-foreground">overridden (AI {fmtScore(row.original.total_score)})</span>}
            </div>
          ),
      }),
      col.display({
        id: "components",
        header: "Skills · Exp · Proj · Qual",
        cell: ({ row }) => {
          const c = row.original.components;
          return <span className="text-xs whitespace-nowrap tabular-nums text-muted-foreground">{[c.skills, c.experience, c.projects, c.qualifications].map((v) => (v == null ? "–" : Math.round(v))).join(" · ")}</span>;
        },
      }),
      col.display({ id: "matched", header: "Matched", cell: ({ row }) => <SkillChips skills={row.original.matched_skills} tone="success" max={3} /> }),
      col.display({ id: "missing", header: "Missing", cell: ({ row }) => <SkillChips skills={row.original.missing_skills} tone="destructive" max={3} /> }),
      col.accessor("status", { header: "Status", cell: ({ row }) => <StatusBadge status={row.original.status} /> }),
      col.display({
        id: "flags",
        header: "Flags",
        cell: ({ row }) => (row.original.flags.length ? <Badge variant="warning" title={row.original.flags.map((f) => f.message).join("\n")}>{row.original.flags.length}</Badge> : null),
      }),
      col.accessor("applied_at", { header: "Applied", cell: (c) => <span className="text-xs whitespace-nowrap text-muted-foreground">{fmtDate(c.getValue())}</span> }),
    ],
    [picked],
  );
  const table = useReactTable({ data: q.data?.items ?? [], columns, getCoreRowModel: getCoreRowModel() });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Input aria-label="Search candidates" placeholder="Search name or email" className="w-48" value={search} onChange={(e) => setSearch(e.target.value)} />
        <Input aria-label="Filter by skill" placeholder="Has skill…" className="w-36" value={skill} onChange={(e) => setSkill(e.target.value)} />
        <Input aria-label="Minimum score" type="number" min={0} max={100} placeholder="Min score" className="w-28" value={minScore} onChange={(e) => setMinScore(e.target.value)} />
        <Select aria-label="Status" className="w-44" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {STATUS_ORDER.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}{q.data?.status_counts[s] ? ` (${q.data.status_counts[s]})` : ""}</option>)}
        </Select>
        <Select aria-label="Sort" className="w-36" value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="score">Sort: score</option><option value="date">Sort: date</option><option value="name">Sort: name</option>
        </Select>
        <div className="ml-auto flex items-center gap-2">
          {picked.length > 0 && <Button variant="ghost" size="sm" onClick={() => setPicked([])}>Clear</Button>}
          <Button disabled={picked.length < 2} onClick={() => router.push(`/recruiter/jobs/${jobId}/compare?ids=${picked.join(",")}`)}>
            <GitCompareArrows /> Compare{picked.length ? ` (${picked.length})` : ""}
          </Button>
        </div>
      </div>
      {picked.length === 1 && <p className="text-xs text-muted-foreground">Select 2–4 candidates to compare side-by-side.</p>}
      {q.isError ? <ErrorState error={q.error} retry={() => q.refetch()} /> : !q.data ? <Skeleton className="h-64" /> : q.data.items.length === 0 ? (
        <EmptyState icon={<Users className="size-8" />} title={status || dSkill || dSearch || dMin ? "No applicants match these filters" : "No applicants yet"} description="Applications appear here ranked by evidence-based score as soon as candidates apply." />
      ) : (
        <Card>
          <Table>
            <THead>{table.getHeaderGroups().map((hg) => <TR key={hg.id} className="hover:bg-transparent">{hg.headers.map((h) => <TH key={h.id}>{flexRender(h.column.columnDef.header, h.getContext())}</TH>)}</TR>)}</THead>
            <TBody>
              {table.getRowModel().rows.map((r) => (
                <TR key={r.id} className="cursor-pointer" onClick={() => router.push(`/recruiter/applications/${r.original.id}`)}>
                  {r.getVisibleCells().map((c) => <TD key={c.id}>{flexRender(c.column.columnDef.cell, c.getContext())}</TD>)}
                </TR>
              ))}
            </TBody>
          </Table>
          <p className="border-t px-4 py-2 text-xs text-muted-foreground">{q.data.total} applicant(s) total</p>
        </Card>
      )}
    </div>
  );
}

function TalentPool({ jobId }: { jobId: string }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["talent-pool", jobId], queryFn: () => api<TalentPoolItem[]>(`/jobs/${jobId}/talent-pool`) });
  const invite = useMutation({
    mutationFn: (cid: string) => api(`/jobs/${jobId}/talent-pool/${cid}/invite`, { method: "POST" }),
    onSuccess: () => { toast.success("Invitation sent"); qc.invalidateQueries({ queryKey: ["talent-pool", jobId] }); },
    onError: notifyError,
  });
  if (q.isError) return <ErrorState error={q.error} retry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-40" />;
  if (!q.data.length) return <EmptyState title="Talent pool is empty" description="Candidates who opt in to the talent pool and match this role appear here." />;
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {q.data.map((t) => (
        <Card key={t.candidate.id} className="p-4">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="font-medium">{t.candidate.full_name}</p>
              <p className="text-xs text-muted-foreground">{t.candidate.headline ?? t.candidate.email}</p>
              {t.previously_applied_to && <p className="mt-1 text-xs text-muted-foreground">Previously applied to: {t.previously_applied_to}</p>}
            </div>
            <div className="w-28"><ScoreBar value={t.score} /></div>
          </div>
          <div className="mt-3 space-y-2">
            <SkillChips skills={t.matched_skills} tone="success" />
            <SkillChips skills={t.missing_skills} tone="destructive" />
          </div>
          <div className="mt-3 flex justify-between">
            <Button variant="link" size="sm" asChild className="px-0"><a href={`/api/resumes/${t.resume_id}/file`} target="_blank" rel="noreferrer">View resume</a></Button>
            <Button size="sm" variant={t.invited ? "secondary" : "default"} disabled={t.invited} loading={invite.isPending && invite.variables === t.candidate.id} onClick={() => invite.mutate(t.candidate.id)}>
              <UserPlus /> {t.invited ? "Invited" : "Invite to apply"}
            </Button>
          </div>
        </Card>
      ))}
    </div>
  );
}

export default function JobDetail() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const job = useQuery({ queryKey: ["job", id], queryFn: () => api<JobOut>(`/jobs/${id}`), staleTime: 45_000 });
  // Start the applicants request in parallel with the job instead of after it.
  useEffect(() => {
    qc.prefetchQuery({ queryKey: ["applicants", id, "", "", "", "", "score"], queryFn: () => api<JobApplicantsOut>(`/jobs/${id}/applications${qs({ sort: "score" })}`), staleTime: 45_000 });
  }, [id, qc]);
  const toggle = useMutation({
    mutationFn: (action: "close" | "reopen") => api<JobOut>(`/jobs/${id}/${action}`, { method: "POST" }),
    onSuccess: (j) => { qc.setQueryData(["job", id], j); qc.invalidateQueries({ queryKey: ["jobs"] }); toast.success(j.status === "closed" ? "Job closed — no new applications" : "Job reopened"); },
    onError: notifyError,
  });
  if (job.isError) return <ErrorState error={job.error} retry={() => job.refetch()} />;
  const j = job.data;
  if (!j) return (
    <div aria-busy="true" aria-label="Loading job">
      <Skeleton className="mb-2 h-8 w-72" /><Skeleton className="mb-6 h-4 w-96" />
      <Skeleton className="mb-4 h-10 w-80 rounded-full" /><Skeleton className="h-96 rounded-3xl" />
    </div>
  );
  return (
    <>
      <PageHeader
        title={<span className="flex items-center gap-3">{j.title}<Badge variant={j.status === "open" ? "success" : "muted"}>{titleCase(j.status)}</Badge></span>}
        description={[j.department, j.location, `${titleCase(j.employment_type)} · ${titleCase(j.work_mode)}`, fmtSalary(j.salary_min, j.salary_max, j.currency), `v${j.version}`].filter(Boolean).join(" · ")}
        actions={
          <>
            <Button variant="outline" asChild><Link href={`/recruiter/jobs/${id}/edit`}><Pencil /> Edit</Link></Button>
            <Button variant="outline" loading={toggle.isPending} onClick={() => toggle.mutate(j.status === "open" ? "close" : "reopen")}>
              {j.status === "open" ? <><Lock /> Close</> : <><Unlock /> Reopen</>}
            </Button>
          </>
        }
      />
      {j.status === "closed" && <Banner tone="warning" className="mb-4">This job is closed. Candidates can no longer apply, but you can still review existing applicants.</Banner>}
      <Tabs defaultValue="applicants">
        <TabsList>
          <TabsTrigger value="applicants">Applicants ({j.applicant_count})</TabsTrigger>
          <TabsTrigger value="pool">Talent pool</TabsTrigger>
          <TabsTrigger value="details">Job details</TabsTrigger>
        </TabsList>
        <TabsContent value="applicants"><Applicants jobId={id} /></TabsContent>
        <TabsContent value="pool"><TalentPool jobId={id} /></TabsContent>
        <TabsContent value="details">
          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2"><CardHeader><CardTitle>Description</CardTitle></CardHeader><CardContent><p className="text-sm whitespace-pre-wrap">{j.description}</p></CardContent></Card>
            <Card>
              <CardHeader><CardTitle>Requirements</CardTitle></CardHeader>
              <CardContent className="space-y-3 text-sm">
                {(["required", "preferred"] as const).map((k) => (
                  <div key={k}>
                    <p className="mb-1 text-xs font-medium text-muted-foreground uppercase">{k}</p>
                    <div className="flex flex-wrap gap-1">{j.requirements.filter((r) => r.kind === k).map((r) => <Badge key={r.id} variant={k === "required" ? "default" : "secondary"}>{r.skill} · {r.importance}</Badge>)}</div>
                  </div>
                ))}
                <p>Min. experience: <strong>{j.min_experience_years} yrs</strong></p>
                <p>Weights: {Object.entries(j.weights).map(([k, v]) => `${titleCase(k)} ${v}`).join(" · ")}</p>
                {j.qualifications.length > 0 && <ul className="list-disc pl-4">{j.qualifications.map((q) => <li key={q}>{q}</li>)}</ul>}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </>
  );
}
