"use client";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Check, Plus, RefreshCw, Trash2 } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import type {
  CandidateSkillOut, EducationItem, ExperienceItem, ParsedPatchIn, ProjectItem, ResumeDetailOut, SkillAddIn, SkillPatchIn,
} from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox, Field, Input, Select, Textarea } from "@/components/ui/input";
import { Banner } from "@/components/ui/misc";
import { FlagList, VerificationBadge, notifyError } from "./common";

export function SkillsManager({ resume }: { resume: ResumeDetailOut }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [presence, setPresence] = useState<"present" | "absent">("present");
  const inv = () => qc.invalidateQueries({ queryKey: ["resume", resume.id] });
  const add = useMutation({ mutationFn: (b: SkillAddIn) => api<CandidateSkillOut>(`/resumes/${resume.id}/skills`, { body: b }), onSuccess: () => { setName(""); inv(); toast.success("Skill added"); }, onError: notifyError });
  const patch = useMutation({ mutationFn: ({ id, b }: { id: string; b: SkillPatchIn }) => api<CandidateSkillOut>(`/skills/${id}`, { method: "PATCH", body: b }), onSuccess: inv, onError: notifyError });
  const del = useMutation({ mutationFn: (id: string) => api(`/skills/${id}`, { method: "DELETE" }), onSuccess: inv, onError: notifyError });
  const skills = resume.skills.filter((s) => !s.removed);
  return (
    <Card>
      <CardHeader><CardTitle>Skills</CardTitle><CardDescription>Skills found in your resume. Confirm correct ones, remove wrong ones, or add skills the parser missed. Skills you add without resume evidence are marked self-reported and count for less.</CardDescription></CardHeader>
      <CardContent className="space-y-3">
        {skills.length === 0 && <p className="text-sm text-muted-foreground">No skills detected yet.</p>}
        <ul className="divide-y">
          {skills.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center gap-2 py-2">
              <span className={s.presence === "absent" ? "text-muted-foreground line-through" : "font-medium"}>{s.name}</span>
              <VerificationBadge v={s.verification} />
              {s.presence === "absent" && <Badge variant="muted">marked as not having</Badge>}
              {s.evidence && <span className="hidden max-w-xs truncate text-xs text-muted-foreground italic md:inline">“{s.evidence}”</span>}
              <span className="ml-auto flex gap-1">
                {s.verification !== "verified" && s.presence === "present" && <Button size="sm" variant="ghost" onClick={() => patch.mutate({ id: s.id, b: { confirm: true } })}><Check /> Confirm</Button>}
                <Button size="icon" variant="ghost" aria-label={`Remove ${s.name}`} onClick={() => del.mutate(s.id)}><Trash2 /></Button>
              </span>
            </li>
          ))}
        </ul>
        <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); const n = name.trim(); if (!n) return; if (skills.some((s) => s.name.toLowerCase() === n.toLowerCase())) return void toast.info("That skill is already listed"); add.mutate({ name: n, presence }); }}>
          <Input aria-label="Skill name" placeholder="Add a skill…" className="max-w-56" value={name} onChange={(e) => setName(e.target.value)} />
          <Select aria-label="Presence" className="w-44" value={presence} onChange={(e) => setPresence(e.target.value as "present" | "absent")}><option value="present">I have this skill</option><option value="absent">I don’t have this</option></Select>
          <Button type="submit" variant="outline" loading={add.isPending}><Plus /> Add</Button>
        </form>
      </CardContent>
    </Card>
  );
}

const blankExp = (): ExperienceItem => ({ title: "", company: "", start_date: "", end_date: "", current: false, description: "", skills: [], evidence: null, start: null, end: null, verification: "self_reported" });
const blankEdu = (): EducationItem => ({ degree: "", level: null, field: "", institution: "", start_year: null, end_year: null, evidence: null, start: null, end: null, verification: "self_reported" });
const blankProj = (): ProjectItem => ({ name: "", description: "", tech: [], url: null, evidence: null, start: null, end: null, verification: "self_reported" });
const nz = (s: string | null) => (s && s.trim() ? s.trim() : null);

export function ParsedEditor({ resume }: { resume: ResumeDetailOut }) {
  const qc = useQueryClient();
  const p = resume.parsed;
  const [summary, setSummary] = useState(p?.summary ?? "");
  const [exp, setExp] = useState<ExperienceItem[]>(p?.experience ?? []);
  const [edu, setEdu] = useState<EducationItem[]>(p?.education ?? []);
  const [proj, setProj] = useState<ProjectItem[]>(p?.projects ?? []);
  const [certs, setCerts] = useState((p?.certifications ?? []).join("\n"));
  const [err, setErr] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (b: ParsedPatchIn) => api<ResumeDetailOut>(`/resumes/${resume.id}/parsed`, { method: "PATCH", body: b }),
    onSuccess: (r) => { qc.setQueryData(["resume", resume.id], r); qc.invalidateQueries({ queryKey: ["resumes"] }); qc.invalidateQueries({ queryKey: ["my-applications"] }); toast.success("Saved — your open applications are being re-assessed"); },
    onError: (e) => setErr(errMsg(e)),
  });
  function submit() {
    for (const [i, x] of exp.entries()) {
      if (!x.title?.trim() && !x.company?.trim()) return setErr(`Experience #${i + 1}: add a title or company, or remove it`);
      if (!x.current && x.start_date && x.end_date && x.start_date > x.end_date) return setErr(`Experience #${i + 1}: end date is before start date`);
    }
    for (const [i, x] of edu.entries()) {
      if (x.start_year && x.end_year && x.start_year > x.end_year) return setErr(`Education #${i + 1}: end year is before start year`);
    }
    setErr(null);
    save.mutate({
      summary: nz(summary),
      experience: exp.map((x) => ({ ...x, title: nz(x.title), company: nz(x.company), start_date: nz(x.start_date), end_date: x.current ? null : nz(x.end_date), description: nz(x.description) })),
      education: edu.map((x) => ({ ...x, degree: nz(x.degree), field: nz(x.field), institution: nz(x.institution) })),
      projects: proj.map((x) => ({ ...x, name: nz(x.name), description: nz(x.description) })),
      certifications: certs.split("\n").map((s) => s.trim()).filter(Boolean),
    });
  }
  const upd = <T,>(arr: T[], set: (a: T[]) => void, i: number, patch: Partial<T>) => set(arr.map((x, idx) => (idx === i ? { ...x, ...patch } : x)));
  const rm = <T,>(arr: T[], set: (a: T[]) => void, i: number) => set(arr.filter((_, idx) => idx !== i));
  return (
    <Card>
      <CardHeader><CardTitle>Review your parsed resume</CardTitle><CardDescription>Fix anything the parser got wrong. Saving re-assesses your open applications.</CardDescription></CardHeader>
      <CardContent className="space-y-6">
        {err && <Banner tone="danger">{err}</Banner>}
        <Field label="Summary" htmlFor="pe-sum"><Textarea id="pe-sum" value={summary} onChange={(e) => setSummary(e.target.value)} /></Field>

        <section className="space-y-3"><h3 className="font-medium">Experience</h3>
          {exp.map((x, i) => (
            <div key={i} className="space-y-2 rounded-lg border p-3">
              <div className="grid gap-2 sm:grid-cols-2">
                <Input aria-label="Job title" placeholder="Title" value={x.title ?? ""} onChange={(e) => upd(exp, setExp, i, { title: e.target.value })} />
                <Input aria-label="Company" placeholder="Company" value={x.company ?? ""} onChange={(e) => upd(exp, setExp, i, { company: e.target.value })} />
                <Input aria-label="Start date" placeholder="Start (e.g. 2021-03)" value={x.start_date ?? ""} onChange={(e) => upd(exp, setExp, i, { start_date: e.target.value })} />
                <Input aria-label="End date" placeholder="End (e.g. 2023-06)" disabled={x.current} value={x.end_date ?? ""} onChange={(e) => upd(exp, setExp, i, { end_date: e.target.value })} />
              </div>
              <label className="flex items-center gap-2 text-sm"><Checkbox checked={x.current} onChange={(e) => upd(exp, setExp, i, { current: e.target.checked })} /> I currently work here</label>
              <Textarea aria-label="Description" rows={2} placeholder="What you did…" value={x.description ?? ""} onChange={(e) => upd(exp, setExp, i, { description: e.target.value })} />
              <Button type="button" size="sm" variant="ghost" onClick={() => rm(exp, setExp, i)}><Trash2 /> Remove</Button>
            </div>
          ))}
          <Button type="button" size="sm" variant="outline" onClick={() => setExp([...exp, blankExp()])}><Plus /> Add experience</Button>
        </section>

        <section className="space-y-3"><h3 className="font-medium">Education</h3>
          {edu.map((x, i) => (
            <div key={i} className="space-y-2 rounded-lg border p-3">
              <div className="grid gap-2 sm:grid-cols-2">
                <Input aria-label="Degree" placeholder="Degree" value={x.degree ?? ""} onChange={(e) => upd(edu, setEdu, i, { degree: e.target.value })} />
                <Input aria-label="Field" placeholder="Field of study" value={x.field ?? ""} onChange={(e) => upd(edu, setEdu, i, { field: e.target.value })} />
                <Input aria-label="Institution" placeholder="Institution" value={x.institution ?? ""} onChange={(e) => upd(edu, setEdu, i, { institution: e.target.value })} />
                <div className="grid grid-cols-2 gap-2">
                  <Input aria-label="Start year" type="number" placeholder="Start" value={x.start_year ?? ""} onChange={(e) => upd(edu, setEdu, i, { start_year: e.target.value ? Number(e.target.value) : null })} />
                  <Input aria-label="End year" type="number" placeholder="End" value={x.end_year ?? ""} onChange={(e) => upd(edu, setEdu, i, { end_year: e.target.value ? Number(e.target.value) : null })} />
                </div>
              </div>
              <Button type="button" size="sm" variant="ghost" onClick={() => rm(edu, setEdu, i)}><Trash2 /> Remove</Button>
            </div>
          ))}
          <Button type="button" size="sm" variant="outline" onClick={() => setEdu([...edu, blankEdu()])}><Plus /> Add education</Button>
        </section>

        <section className="space-y-3"><h3 className="font-medium">Projects</h3>
          {proj.map((x, i) => (
            <div key={i} className="space-y-2 rounded-lg border p-3">
              <Input aria-label="Project name" placeholder="Project name" value={x.name ?? ""} onChange={(e) => upd(proj, setProj, i, { name: e.target.value })} />
              <Textarea aria-label="Project description" rows={2} placeholder="Description" value={x.description ?? ""} onChange={(e) => upd(proj, setProj, i, { description: e.target.value })} />
              <Input aria-label="Technologies" placeholder="Technologies (comma separated)" value={x.tech.join(", ")} onChange={(e) => upd(proj, setProj, i, { tech: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} />
              <Button type="button" size="sm" variant="ghost" onClick={() => rm(proj, setProj, i)}><Trash2 /> Remove</Button>
            </div>
          ))}
          <Button type="button" size="sm" variant="outline" onClick={() => setProj([...proj, blankProj()])}><Plus /> Add project</Button>
        </section>

        <Field label="Certifications (one per line)" htmlFor="pe-cert"><Textarea id="pe-cert" rows={3} value={certs} onChange={(e) => setCerts(e.target.value)} /></Field>
        <Button loading={save.isPending} onClick={submit}>Save corrections</Button>
      </CardContent>
    </Card>
  );
}

export function ResumeStatusNotes({ resume }: { resume: ResumeDetailOut }) {
  const qc = useQueryClient();
  const re = useMutation({ mutationFn: () => api(`/resumes/${resume.id}/reprocess`, { method: "POST" }), onSuccess: () => { toast.success("Re-processing started"); qc.invalidateQueries({ queryKey: ["resume", resume.id] }); qc.invalidateQueries({ queryKey: ["resumes"] }); }, onError: notifyError });
  return (
    <div className="space-y-2">
      {resume.parse_status === "failed" && (
        <Banner tone="danger"><div className="flex flex-wrap items-center justify-between gap-2"><span>We couldn’t read this resume{resume.parse_error ? `: ${resume.parse_error}` : "."} Try re-processing, or upload a text-based PDF/DOCX (scanned images aren’t supported).</span><Button size="sm" variant="outline" loading={re.isPending} onClick={() => re.mutate()}><RefreshCw /> Retry</Button></div></Banner>
      )}
      {resume.parse_status === "parsed" && resume.extraction_method === "rules" && <Banner tone="info">Parsed with the basic rule-based parser (AI parsing was unavailable). Please review the details carefully.</Banner>}
      {resume.warnings.map((w, i) => <Banner key={i} tone="warning">{w}</Banner>)}
      <FlagList flags={resume.integrity_flags} />
    </div>
  );
}
