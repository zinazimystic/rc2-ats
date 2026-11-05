"use client";
import { Suspense } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";
import type { CompareOut, RequirementResult } from "@/lib/types";
import { fmtScore } from "@/lib/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";
import { EvidenceBadge, FlagList, ScoreRing, StatusBadge } from "@/components/app/common";

function Compare() {
  const { id } = useParams<{ id: string }>();
  const ids = useSearchParams().get("ids") ?? "";
  const count = ids.split(",").filter(Boolean).length;
  const q = useQuery({ queryKey: ["compare", id, ids], queryFn: () => api<CompareOut>(`/jobs/${id}/compare?ids=${ids}`), enabled: count >= 2 && count <= 4 });
  if (count < 2 || count > 4) return <EmptyState title="Pick 2–4 candidates" description="Select applicants in the job’s applicant table, then press Compare." action={<Button asChild variant="outline"><Link href={`/recruiter/jobs/${id}`}>Back to applicants</Link></Button>} />;
  if (q.isError) return <ErrorState error={q.error} retry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-96" />;
  const { candidates, job } = q.data;
  const skills = new Map<string, { kind: string; importance: number }>();
  candidates.forEach((c) => c.requirements.forEach((r) => !skills.has(r.skill) && skills.set(r.skill, { kind: r.kind, importance: r.importance })));
  const find = (c: (typeof candidates)[number], s: string): RequirementResult | undefined => c.requirements.find((r) => r.skill === s);
  const best = Math.max(...candidates.map((c) => c.effective_score ?? -1));
  return (
    <>
      <PageHeader title={`Compare candidates — ${job.title}`} actions={<Button variant="outline" asChild><Link href={`/recruiter/jobs/${id}`}><ArrowLeft /> Back</Link></Button>} />
      <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${candidates.length}, minmax(0, 1fr))` }}>
        {candidates.map((c) => (
          <Card key={c.application_id} className={c.effective_score === best ? "border-success" : ""}>
            <CardContent className="flex flex-col items-center gap-2 pt-5 text-center">
              <ScoreRing value={c.effective_score} />
              <Link className="font-semibold hover:underline" href={`/recruiter/applications/${c.application_id}`}>{c.candidate.full_name}</Link>
              <StatusBadge status={c.status} />
              <p className="text-[13px] text-muted-foreground">Skills {fmtScore(c.components.skills)} · Exp {fmtScore(c.components.experience)} · Proj {fmtScore(c.components.projects)} · Qual {fmtScore(c.components.qualifications)}</p>
            </CardContent>
          </Card>
        ))}
      </div>
      <Card className="mt-4">
        <CardHeader><CardTitle>Requirement-by-requirement evidence</CardTitle></CardHeader>
        <Table>
          <THead><TR><TH>Requirement</TH>{candidates.map((c) => <TH key={c.application_id}>{c.candidate.full_name}</TH>)}</TR></THead>
          <TBody>
            {[...skills.entries()].map(([s, meta]) => (
              <TR key={s}>
                <TD className="align-top"><span className="font-medium">{s}</span><p className="text-[13px] text-muted-foreground">{meta.kind} · imp. {meta.importance}</p></TD>
                {candidates.map((c) => {
                  const r = find(c, s);
                  return (
                    <TD key={c.application_id} className="align-top">
                      {r ? (<>
                        <div className="flex items-center gap-2"><EvidenceBadge status={r.status} /><span className="text-[13px] text-muted-foreground">{Math.round(r.credit * 100)}%</span></div>
                        {r.evidence[0] && <blockquote className="mt-1 border-l-2 pl-2 text-[13px] text-muted-foreground italic">“{r.evidence[0].quote}”</blockquote>}
                      </>) : <span className="text-[13px] text-muted-foreground">—</span>}
                    </TD>
                  );
                })}
              </TR>
            ))}
          </TBody>
        </Table>
      </Card>
      <div className="mt-4 grid gap-4" style={{ gridTemplateColumns: `repeat(${candidates.length}, minmax(0, 1fr))` }}>
        {candidates.map((c) => (
          <Card key={c.application_id}>
            <CardContent className="space-y-3 pt-5 text-sm">
              <p className="font-semibold">{c.candidate.full_name}</p>
              <div><p className="text-[13px] font-medium text-success uppercase">Strengths</p><ul className="list-disc pl-4">{c.strengths.length ? c.strengths.map((s, i) => <li key={i}>{s}</li>) : <li className="list-none text-muted-foreground">—</li>}</ul></div>
              <div><p className="text-[13px] font-medium text-destructive uppercase">Gaps</p><ul className="list-disc pl-4">{c.gaps.length ? c.gaps.map((s, i) => <li key={i}>{s}</li>) : <li className="list-none text-muted-foreground">—</li>}</ul></div>
              {c.missing_information.length > 0 && <div><p className="text-[13px] font-medium text-warning uppercase">Missing information</p><ul className="list-disc pl-4">{c.missing_information.map((s, i) => <li key={i}>{s}</li>)}</ul></div>}
              <FlagList flags={c.flags} />
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}

export default function ComparePage() {
  return <Suspense fallback={<Skeleton className="h-96" />}><Compare /></Suspense>;
}
