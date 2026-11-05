"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "@/lib/toast";
import { AlertTriangle, Plus, Sparkles, Trash2 } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import type {
  EducationLevel, EmploymentType, JobExtractOut, JobIn, JobOut, JobWeights, RequirementIn, WorkMode,
} from "@/lib/types";
import { EDUCATION_LABEL, titleCase } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { Banner } from "@/components/ui/misc";
import { friendlyError } from "@/lib/errors";

const DEFAULT_WEIGHTS: JobWeights = { skills: 50, experience: 25, projects: 15, qualifications: 10 };

interface FormState {
  title: string; department: string; location: string;
  employment_type: EmploymentType; work_mode: WorkMode;
  salary_min: string; salary_max: string; currency: string;
  description: string; min_experience_years: string; education_level: EducationLevel;
  qualifications: string; requirements: RequirementIn[]; weights: JobWeights;
}

function fromJob(j?: JobOut): FormState {
  return {
    title: j?.title ?? "", department: j?.department ?? "", location: j?.location ?? "",
    employment_type: j?.employment_type ?? "full_time", work_mode: j?.work_mode ?? "onsite",
    salary_min: j?.salary_min?.toString() ?? "", salary_max: j?.salary_max?.toString() ?? "", currency: j?.currency ?? "USD",
    description: j?.description ?? "", min_experience_years: j?.min_experience_years.toString() ?? "0",
    education_level: j?.education_level ?? "none", qualifications: (j?.qualifications ?? []).join("\n"),
    requirements: j?.requirements.map((r) => ({ skill: r.skill, kind: r.kind, importance: r.importance })) ?? [],
    weights: j?.weights ?? DEFAULT_WEIGHTS,
  };
}

export function JobForm({ job }: { job?: JobOut }) {
  const router = useRouter();
  const qc = useQueryClient();
  const [f, setF] = useState<FormState>(() => fromJob(job));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [extract, setExtract] = useState<JobExtractOut | null>(null);
  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setF((p) => ({ ...p, [k]: v }));

  const ex = useMutation({
    mutationFn: () => api<JobExtractOut>("/jobs/extract-requirements", { body: { title: f.title || null, description: f.description } }),
    onSuccess: (r) => {
      setExtract(r);
      setF((p) => {
        const existing = new Set(p.requirements.map((x) => x.skill.toLowerCase()));
        const add: RequirementIn[] = [
          ...r.required_skills.map((s) => ({ skill: s.skill, kind: "required" as const, importance: s.importance })),
          ...r.preferred_skills.map((s) => ({ skill: s.skill, kind: "preferred" as const, importance: s.importance })),
        ].filter((x) => !existing.has(x.skill.toLowerCase()));
        return {
          ...p,
          requirements: [...p.requirements, ...add],
          min_experience_years: r.min_experience_years != null ? String(r.min_experience_years) : p.min_experience_years,
          education_level: r.education_level ?? p.education_level,
          qualifications: r.qualifications.length && !p.qualifications.trim() ? r.qualifications.join("\n") : p.qualifications,
        };
      });
      toast.success(`Extracted ${r.required_skills.length + r.preferred_skills.length} requirements`);
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const save = useMutation({
    mutationFn: (body: JobIn) => (job ? api<JobOut>(`/jobs/${job.id}`, { method: "PATCH", body }) : api<JobOut>("/jobs", { body })),
    onSuccess: (j) => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["job", j.id] });
      qc.invalidateQueries({ queryKey: ["applicants", j.id] });
      toast.success(job ? "Job updated" : "Job created");
      router.push(`/recruiter/jobs/${j.id}`);
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const wsum = f.weights.skills + f.weights.experience + f.weights.projects + f.weights.qualifications;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const er: Record<string, string> = {};
    if (f.title.trim().length < 3) er.title = "Title must be at least 3 characters";
    if (f.description.trim().length < 20) er.description = "Describe the role (at least 20 characters)";
    const exp = Number(f.min_experience_years);
    if (!Number.isFinite(exp) || exp < 0 || exp > 50) er.min_experience_years = "Enter 0–50";
    const smin = f.salary_min ? Number(f.salary_min) : null;
    const smax = f.salary_max ? Number(f.salary_max) : null;
    if ((smin !== null && (isNaN(smin) || smin < 0)) || (smax !== null && (isNaN(smax) || smax < 0))) er.salary = "Salary must be a positive number";
    else if (smin !== null && smax !== null && smin > smax) er.salary = "Minimum salary exceeds maximum";
    if (Math.round(wsum) !== 100) er.weights = `Weights must total 100 (currently ${wsum})`;
    if (f.requirements.some((r) => !r.skill.trim())) er.requirements = "Remove or fill in empty skills";
    if (!f.requirements.some((r) => r.kind === "required")) er.requirements = "Add at least one required skill (use AI extraction or add manually)";
    setErrors(er);
    if (Object.keys(er).length) {
      toast.error("Please fix the highlighted fields");
      return;
    }
    const seen = new Set<string>();
    const reqs = f.requirements
      .map((r) => ({ ...r, skill: r.skill.trim() }))
      .filter((r) => (seen.has(r.skill.toLowerCase()) ? false : (seen.add(r.skill.toLowerCase()), true)));
    save.mutate({
      title: f.title.trim(), department: f.department.trim() || null, location: f.location.trim() || null,
      employment_type: f.employment_type, work_mode: f.work_mode,
      salary_min: smin, salary_max: smax, currency: f.currency.trim().toUpperCase() || "USD",
      description: f.description.trim(), min_experience_years: exp, education_level: f.education_level,
      qualifications: f.qualifications.split("\n").map((s) => s.trim()).filter(Boolean),
      requirements: reqs, weights: f.weights,
    });
  }

  const updReq = (i: number, patch: Partial<RequirementIn>) =>
    set("requirements", f.requirements.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));

  return (
    <form onSubmit={submit} className="space-y-6" noValidate>
      {job && (
        <Banner tone="warning">
          Changing requirements, weights, experience or education creates a new job version and re-scores all {job.applicant_count} applicant(s) in the background.
        </Banner>
      )}
      <Card>
        <CardHeader><CardTitle>Role details</CardTitle></CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <Field label="Job title *" htmlFor="title" error={errors.title} className="sm:col-span-2">
            <Input id="title" value={f.title} onChange={(e) => set("title", e.target.value)} placeholder="Backend Developer" aria-invalid={!!errors.title} />
          </Field>
          <Field label="Department" htmlFor="dept"><Input id="dept" value={f.department} onChange={(e) => set("department", e.target.value)} /></Field>
          <Field label="Location" htmlFor="loc"><Input id="loc" value={f.location} onChange={(e) => set("location", e.target.value)} /></Field>
          <Field label="Employment type" htmlFor="et">
            <Select id="et" value={f.employment_type} onChange={(e) => set("employment_type", e.target.value as EmploymentType)}>
              {(["full_time", "part_time", "contract", "internship"] as const).map((v) => <option key={v} value={v}>{titleCase(v)}</option>)}
            </Select>
          </Field>
          <Field label="Work mode" htmlFor="wm">
            <Select id="wm" value={f.work_mode} onChange={(e) => set("work_mode", e.target.value as WorkMode)}>
              {(["onsite", "hybrid", "remote"] as const).map((v) => <option key={v} value={v}>{titleCase(v)}</option>)}
            </Select>
          </Field>
          <div className="grid grid-cols-3 gap-2 sm:col-span-2">
            <Field label="Salary min" htmlFor="smin" error={errors.salary}><Input id="smin" inputMode="numeric" value={f.salary_min} onChange={(e) => set("salary_min", e.target.value)} /></Field>
            <Field label="Salary max" htmlFor="smax"><Input id="smax" inputMode="numeric" value={f.salary_max} onChange={(e) => set("salary_max", e.target.value)} /></Field>
            <Field label="Currency" htmlFor="cur"><Input id="cur" maxLength={3} value={f.currency} onChange={(e) => set("currency", e.target.value)} /></Field>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <CardTitle>Description</CardTitle>
              <CardDescription className="mt-1">Paste the full job description, then let AI pull out the requirements.</CardDescription>
            </div>
            <Button type="button" variant="outline" loading={ex.isPending} disabled={f.description.trim().length < 20} onClick={() => ex.mutate()}>
              <Sparkles /> Extract requirements with AI
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <Field label="Description *" htmlFor="desc" error={errors.description}>
            <Textarea id="desc" rows={9} value={f.description} onChange={(e) => set("description", e.target.value)} aria-invalid={!!errors.description} />
          </Field>
          {extract && (
            <div className="space-y-2">
              <Banner tone={extract.method === "llm" ? "success" : "warning"}>
                {extract.method === "llm"
                  ? "Requirements were suggested from your description and checked against it. Review and edit below."
                  : "We found requirements by matching keywords in your description. Review them carefully."}
              </Banner>
              {extract.warnings.map((w, i) => <Banner key={i} tone="warning"><AlertTriangle className="mr-1 inline size-4" />{friendlyError(w, "Some requirements may need a closer look.")}</Banner>)}
              {[...extract.required_skills, ...extract.preferred_skills].some((s) => !s.verified) && (
                <Banner tone="warning">Some skills could not be found verbatim in the description (marked “unverified” below). Remove any that are wrong.</Banner>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Requirements</CardTitle><CardDescription>Importance (1–5) scales how much each skill contributes to the score.</CardDescription></CardHeader>
        <CardContent className="space-y-3">
          {errors.requirements && <p role="alert" className="text-sm text-destructive">{errors.requirements}</p>}
          {f.requirements.length === 0 && <p className="text-sm text-muted-foreground">No requirements yet.</p>}
          {f.requirements.map((r, i) => {
            const unverified = extract && [...extract.required_skills, ...extract.preferred_skills].find((s) => s.skill.toLowerCase() === r.skill.toLowerCase() && !s.verified);
            return (
              <div key={i} className="flex flex-wrap items-center gap-2">
                <Input aria-label={`Skill ${i + 1}`} className="min-w-40 flex-1" value={r.skill} onChange={(e) => updReq(i, { skill: e.target.value })} placeholder="e.g. PostgreSQL" />
                <Select aria-label="Kind" className="w-32" value={r.kind} onChange={(e) => updReq(i, { kind: e.target.value as RequirementIn["kind"] })}>
                  <option value="required">Required</option><option value="preferred">Preferred</option>
                </Select>
                <Select aria-label="Importance" className="w-28" value={r.importance} onChange={(e) => updReq(i, { importance: Number(e.target.value) })}>
                  {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>Imp. {n}</option>)}
                </Select>
                {unverified && <Badge variant="warning">unverified</Badge>}
                <Button type="button" variant="ghost" size="icon" aria-label={`Remove ${r.skill || "skill"}`} onClick={() => set("requirements", f.requirements.filter((_, idx) => idx !== i))}><Trash2 /></Button>
              </div>
            );
          })}
          <Button type="button" variant="outline" size="sm" onClick={() => set("requirements", [...f.requirements, { skill: "", kind: "required", importance: 3 }])}><Plus /> Add skill</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Experience, education & scoring</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Minimum experience (years)" htmlFor="exp" error={errors.min_experience_years}>
              <Input id="exp" inputMode="decimal" value={f.min_experience_years} onChange={(e) => set("min_experience_years", e.target.value)} />
            </Field>
            <Field label="Education level" htmlFor="edu">
              <Select id="edu" value={f.education_level} onChange={(e) => set("education_level", e.target.value as EducationLevel)}>
                {(Object.keys(EDUCATION_LABEL) as EducationLevel[]).map((k) => <option key={k} value={k}>{EDUCATION_LABEL[k]}</option>)}
              </Select>
            </Field>
            <Field label="Qualifications / certifications (one per line)" htmlFor="qual" className="sm:col-span-2">
              <Textarea id="qual" rows={3} value={f.qualifications} onChange={(e) => set("qualifications", e.target.value)} />
            </Field>
          </div>
          <div>
            <p className="mb-2 text-sm font-medium">Score weights <span className={wsum === 100 ? "text-success" : "text-destructive"}>(total {wsum}/100)</span></p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {(Object.keys(f.weights) as (keyof JobWeights)[]).map((k) => (
                <Field key={k} label={titleCase(k)} htmlFor={`w-${k}`}>
                  <Input id={`w-${k}`} type="number" min={0} max={100} value={f.weights[k]} onChange={(e) => set("weights", { ...f.weights, [k]: Math.max(0, Number(e.target.value) || 0) })} />
                </Field>
              ))}
            </div>
            {errors.weights && <p role="alert" className="mt-1 text-xs text-destructive">{errors.weights}</p>}
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={() => router.back()}>Cancel</Button>
        <Button type="submit" loading={save.isPending}>{job ? "Save changes" : "Create job"}</Button>
      </div>
    </form>
  );
}
