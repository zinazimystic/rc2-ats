"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, Plus, Trash2, X } from "lucide-react";
import { api } from "@/lib/api";
import { fieldErrors } from "@/lib/errors";
import { notify } from "@/lib/toast";
import { fmtDate, fmtSize } from "@/lib/format";
import type {
  CandidateSkillOut, ContactInfo, EducationItem, ExperienceItem, ParsedPatchIn, ProjectItem, ResumeDetailOut, SkillAddIn, SkillPatchIn, Verification,
} from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Checkbox, Field, Input, Textarea } from "@/components/ui/input";
import { Notice } from "@/components/ui/notice";
import { Sheet, SheetBody, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/misc";
import { cn } from "@/lib/utils";

const nz = (s: string | null | undefined) => (s && s.trim() ? s.trim() : null);
const blankExp = (): ExperienceItem => ({ title: "", company: "", start_date: "", end_date: "", current: false, description: "", skills: [], evidence: null, start: null, end: null, verification: "self_reported" });
const blankEdu = (): EducationItem => ({ degree: "", level: null, field: "", institution: "", start_year: null, end_year: null, evidence: null, start: null, end: null, verification: "self_reported" });
const blankProj = (): ProjectItem => ({ name: "", description: "", tech: [], url: null, evidence: null, start: null, end: null, verification: "self_reported" });

interface Draft {
  contact: { name: string; email: string; phone: string; location: string; links: string };
  summary: string;
  exp: ExperienceItem[];
  edu: EducationItem[];
  proj: ProjectItem[];
  certs: string;
}
function toDraft(r: ResumeDetailOut): Draft {
  const p = r.parsed;
  return {
    contact: { name: p?.contact.name ?? "", email: p?.contact.email ?? "", phone: p?.contact.phone ?? "", location: p?.contact.location ?? "", links: (p?.contact.links ?? []).join("\n") },
    summary: p?.summary ?? "",
    exp: p?.experience ?? [],
    edu: p?.education ?? [],
    proj: p?.projects ?? [],
    certs: (p?.certifications ?? []).join("\n"),
  };
}

const CHIP: Record<Verification, string> = {
  verified: "border-success/30 bg-success/10",
  fuzzy: "border-warning/40 bg-warning/10",
  self_reported: "border-primary/30 bg-primary/8",
  unverified: "border-destructive/30 bg-destructive/8",
};
const CHIP_LABEL: Record<Verification, string> = { verified: "Found in resume", fuzzy: "Approximate match", self_reported: "Added by you", unverified: "Not found in resume" };

function SectionTitle({ children, hint }: { children: React.ReactNode; hint?: string }) {
  return (
    <div>
      <h3 className="text-sm font-semibold tracking-wide uppercase">{children}</h3>
      {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

function SkillsSection({ resume }: { resume: ResumeDetailOut }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const inv = () => {
    qc.invalidateQueries({ queryKey: ["resume", resume.id] });
    qc.invalidateQueries({ queryKey: ["resumes"] });
    qc.invalidateQueries({ queryKey: ["my-match"] });
  };
  const add = useMutation({
    mutationFn: (b: SkillAddIn) => api<CandidateSkillOut>(`/resumes/${resume.id}/skills`, { body: b }),
    onSuccess: (_r, v) => { setName(""); inv(); notify.success(v.presence === "absent" ? "Marked as not having this skill" : "Skill added"); },
    onError: (e) => notify.error(e),
  });
  const patch = useMutation({
    mutationFn: ({ id, b }: { id: string; b: SkillPatchIn }) => api<CandidateSkillOut>(`/skills/${id}`, { method: "PATCH", body: b }),
    onSuccess: inv,
    onError: (e) => notify.error(e),
  });
  const del = useMutation({
    mutationFn: (id: string) => api(`/skills/${id}`, { method: "DELETE" }),
    onSuccess: () => { inv(); notify.success("Skill removed"); },
    onError: (e) => notify.error(e),
  });
  const skills = resume.skills.filter((s) => !s.removed);
  const submit = (presence: "present" | "absent") => {
    const n = name.trim();
    if (!n) return;
    if (skills.some((s) => s.name.toLowerCase() === n.toLowerCase())) return void notify.info("That skill is already listed");
    add.mutate({ name: n, presence });
  };
  return (
    <section className="space-y-3">
      <SectionTitle hint="Confirm the right ones, remove the wrong ones, or add what we missed. Skills without evidence in your resume count for less.">Skills</SectionTitle>
      {skills.length === 0 && <p className="text-sm text-muted-foreground">No skills detected yet.</p>}
      <ul className="flex flex-wrap gap-2">
        {skills.map((s) => (
          <li key={s.id} className={cn("group inline-flex items-center gap-1 rounded-full border py-1 pr-1 pl-3 text-sm", CHIP[s.verification], s.presence === "absent" && "opacity-70")} title={`${CHIP_LABEL[s.verification]}${s.evidence ? `: “${s.evidence}”` : ""}`}>
            <span className={cn("font-medium", s.presence === "absent" && "line-through")}>{s.name}</span>
            {s.presence === "absent" && <span className="text-[11px] text-muted-foreground">not having</span>}
            {s.verification !== "verified" && s.presence === "present" && (
              <button type="button" aria-label={`Confirm ${s.name}`} title="I have this skill" onClick={() => patch.mutate({ id: s.id, b: { confirm: true } })} className="grid size-6 place-items-center rounded-full text-success hover:bg-success/15"><Check className="size-3.5" /></button>
            )}
            {s.presence === "present" ? (
              <button type="button" onClick={() => patch.mutate({ id: s.id, b: { presence: "absent" } })} className="rounded-full px-1.5 text-[11px] text-muted-foreground hover:bg-black/5 hover:text-foreground dark:hover:bg-white/10">I don’t have this</button>
            ) : (
              <button type="button" onClick={() => patch.mutate({ id: s.id, b: { presence: "present" } })} className="rounded-full px-1.5 text-[11px] text-primary hover:bg-primary/10">I have this</button>
            )}
            <button type="button" aria-label={`Remove ${s.name}`} onClick={() => del.mutate(s.id)} className="grid size-6 place-items-center rounded-full text-muted-foreground hover:bg-destructive/15 hover:text-destructive"><X className="size-3.5" /></button>
          </li>
        ))}
      </ul>
      <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); submit("present"); }}>
        <Input aria-label="Skill name" placeholder="Add a skill…" className="max-w-56" value={name} onChange={(e) => setName(e.target.value)} />
        <Button type="submit" variant="outline" loading={add.isPending && add.variables?.presence === "present"} disabled={!name.trim()}><Plus /> Add</Button>
        <Button type="button" variant="ghost" disabled={!name.trim() || add.isPending} onClick={() => submit("absent")}>I don’t have this</Button>
      </form>
    </section>
  );
}

function ItemBox({ children, onRemove, label }: { children: React.ReactNode; onRemove: () => void; label: string }) {
  return (
    <div className="space-y-2 rounded-2xl border bg-muted/30 p-3">
      {children}
      <Button type="button" size="sm" variant="ghost" onClick={onRemove} aria-label={label}><Trash2 /> Remove</Button>
    </div>
  );
}

function ReviewForm({ resume, onDirty, onClose, onSaved }: { resume: ResumeDetailOut; onDirty: (d: boolean) => void; onClose: () => void; onSaved: () => void }) {
  const qc = useQueryClient();
  const [d, setD] = useState<Draft>(() => toDraft(resume));
  const [base, setBase] = useState(() => JSON.stringify(toDraft(resume)));
  const [err, setErr] = useState<string | null>(null);
  const dirty = JSON.stringify(d) !== base;
  useEffect(() => { onDirty(dirty); }, [dirty, onDirty]);
  const upd = <T,>(arr: T[], i: number, patch: Partial<T>) => arr.map((x, idx) => (idx === i ? { ...x, ...patch } : x));
  const rm = <T,>(arr: T[], i: number) => arr.filter((_, idx) => idx !== i);

  const save = useMutation({
    mutationFn: (b: ParsedPatchIn) => api<ResumeDetailOut>(`/resumes/${resume.id}/parsed`, { method: "PATCH", body: b }),
    onSuccess: (r) => {
      qc.setQueryData(["resume", resume.id], r);
      qc.invalidateQueries({ queryKey: ["resumes"] });
      qc.invalidateQueries({ queryKey: ["my-applications"] });
      qc.invalidateQueries({ queryKey: ["candidate-dashboard"] });
      qc.invalidateQueries({ queryKey: ["my-match"] });
      setBase(JSON.stringify(d));
      onDirty(false);
      notify.success("Resume details saved", { description: "Your open applications will be re-checked with the changes." });
      onSaved();
    },
    onError: (e) => { setErr(fieldErrors(e) ?? "We couldn’t save your changes. Please try again."); notify.error(e); },
  });

  function submit() {
    for (const [i, x] of d.exp.entries()) {
      if (!nz(x.title) && !nz(x.company)) return setErr(`Experience ${i + 1}: add a job title or company, or remove it.`);
      if (!x.current && x.start_date && x.end_date && x.start_date > x.end_date) return setErr(`Experience ${i + 1}: the end date is before the start date.`);
    }
    for (const [i, x] of d.edu.entries()) {
      if (x.start_year && x.end_year && x.start_year > x.end_year) return setErr(`Education ${i + 1}: the end year is before the start year.`);
    }
    setErr(null);
    const contact: ContactInfo = { name: nz(d.contact.name), email: nz(d.contact.email), phone: nz(d.contact.phone), location: nz(d.contact.location), links: d.contact.links.split("\n").map((s) => s.trim()).filter(Boolean) };
    save.mutate({
      contact,
      summary: nz(d.summary),
      experience: d.exp.map((x) => ({ ...x, title: nz(x.title), company: nz(x.company), start_date: nz(x.start_date), end_date: x.current ? null : nz(x.end_date), description: nz(x.description) })),
      education: d.edu.map((x) => ({ ...x, degree: nz(x.degree), field: nz(x.field), institution: nz(x.institution) })),
      projects: d.proj.map((x) => ({ ...x, name: nz(x.name), description: nz(x.description) })),
      certifications: d.certs.split("\n").map((s) => s.trim()).filter(Boolean),
    });
  }

  return (
    <>
      <SheetBody>
        {err && <Notice tone="error" title="Can’t save yet" onDismiss={() => setErr(null)}>{err}</Notice>}
        {resume.parse_status === "failed" && <Notice tone="warning" title="This file couldn’t be read">You can still fill in your details by hand below.</Notice>}

        <section className="space-y-3">
          <SectionTitle hint="Shown to recruiters with your application.">Contact</SectionTitle>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Full name" htmlFor="rv-name"><Input id="rv-name" value={d.contact.name} onChange={(e) => setD({ ...d, contact: { ...d.contact, name: e.target.value } })} /></Field>
            <Field label="Email" htmlFor="rv-email"><Input id="rv-email" type="email" value={d.contact.email} onChange={(e) => setD({ ...d, contact: { ...d.contact, email: e.target.value } })} /></Field>
            <Field label="Phone" htmlFor="rv-phone"><Input id="rv-phone" value={d.contact.phone} onChange={(e) => setD({ ...d, contact: { ...d.contact, phone: e.target.value } })} /></Field>
            <Field label="Location" htmlFor="rv-loc"><Input id="rv-loc" value={d.contact.location} onChange={(e) => setD({ ...d, contact: { ...d.contact, location: e.target.value } })} /></Field>
            <Field label="Links (one per line)" htmlFor="rv-links" className="sm:col-span-2"><Textarea id="rv-links" rows={2} value={d.contact.links} onChange={(e) => setD({ ...d, contact: { ...d.contact, links: e.target.value } })} /></Field>
          </div>
        </section>

        <section className="space-y-3">
          <SectionTitle>Summary</SectionTitle>
          <Textarea aria-label="Summary" rows={4} value={d.summary} onChange={(e) => setD({ ...d, summary: e.target.value })} />
        </section>

        <SkillsSection resume={resume} />

        <section className="space-y-3">
          <SectionTitle>Experience</SectionTitle>
          {d.exp.map((x, i) => (
            <ItemBox key={i} label={`Remove experience ${i + 1}`} onRemove={() => setD({ ...d, exp: rm(d.exp, i) })}>
              <div className="grid gap-2 sm:grid-cols-2">
                <Input aria-label="Job title" placeholder="Title" value={x.title ?? ""} onChange={(e) => setD({ ...d, exp: upd(d.exp, i, { title: e.target.value }) })} />
                <Input aria-label="Company" placeholder="Company" value={x.company ?? ""} onChange={(e) => setD({ ...d, exp: upd(d.exp, i, { company: e.target.value }) })} />
                <Input aria-label="Start date" placeholder="Start (e.g. 2021-03)" value={x.start_date ?? ""} onChange={(e) => setD({ ...d, exp: upd(d.exp, i, { start_date: e.target.value }) })} />
                <Input aria-label="End date" placeholder="End (e.g. 2023-06)" disabled={x.current} value={x.end_date ?? ""} onChange={(e) => setD({ ...d, exp: upd(d.exp, i, { end_date: e.target.value }) })} />
              </div>
              <label className="flex items-center gap-2 text-sm"><Checkbox checked={x.current} onChange={(e) => setD({ ...d, exp: upd(d.exp, i, { current: e.target.checked }) })} /> I currently work here</label>
              <Textarea aria-label="Description" rows={2} placeholder="What you did…" value={x.description ?? ""} onChange={(e) => setD({ ...d, exp: upd(d.exp, i, { description: e.target.value }) })} />
            </ItemBox>
          ))}
          <Button type="button" size="sm" variant="outline" onClick={() => setD({ ...d, exp: [...d.exp, blankExp()] })}><Plus /> Add experience</Button>
        </section>

        <section className="space-y-3">
          <SectionTitle>Education</SectionTitle>
          {d.edu.map((x, i) => (
            <ItemBox key={i} label={`Remove education ${i + 1}`} onRemove={() => setD({ ...d, edu: rm(d.edu, i) })}>
              <div className="grid gap-2 sm:grid-cols-2">
                <Input aria-label="Degree" placeholder="Degree" value={x.degree ?? ""} onChange={(e) => setD({ ...d, edu: upd(d.edu, i, { degree: e.target.value }) })} />
                <Input aria-label="Field of study" placeholder="Field of study" value={x.field ?? ""} onChange={(e) => setD({ ...d, edu: upd(d.edu, i, { field: e.target.value }) })} />
                <Input aria-label="Institution" placeholder="Institution" value={x.institution ?? ""} onChange={(e) => setD({ ...d, edu: upd(d.edu, i, { institution: e.target.value }) })} />
                <div className="grid grid-cols-2 gap-2">
                  <Input aria-label="Start year" type="number" placeholder="Start" value={x.start_year ?? ""} onChange={(e) => setD({ ...d, edu: upd(d.edu, i, { start_year: e.target.value ? Number(e.target.value) : null }) })} />
                  <Input aria-label="End year" type="number" placeholder="End" value={x.end_year ?? ""} onChange={(e) => setD({ ...d, edu: upd(d.edu, i, { end_year: e.target.value ? Number(e.target.value) : null }) })} />
                </div>
              </div>
            </ItemBox>
          ))}
          <Button type="button" size="sm" variant="outline" onClick={() => setD({ ...d, edu: [...d.edu, blankEdu()] })}><Plus /> Add education</Button>
        </section>

        <section className="space-y-3">
          <SectionTitle>Projects</SectionTitle>
          {d.proj.map((x, i) => (
            <ItemBox key={i} label={`Remove project ${i + 1}`} onRemove={() => setD({ ...d, proj: rm(d.proj, i) })}>
              <Input aria-label="Project name" placeholder="Project name" value={x.name ?? ""} onChange={(e) => setD({ ...d, proj: upd(d.proj, i, { name: e.target.value }) })} />
              <Textarea aria-label="Project description" rows={2} placeholder="Description" value={x.description ?? ""} onChange={(e) => setD({ ...d, proj: upd(d.proj, i, { description: e.target.value }) })} />
              <Input aria-label="Technologies" placeholder="Technologies (comma separated)" value={x.tech.join(", ")} onChange={(e) => setD({ ...d, proj: upd(d.proj, i, { tech: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) }) })} />
            </ItemBox>
          ))}
          <Button type="button" size="sm" variant="outline" onClick={() => setD({ ...d, proj: [...d.proj, blankProj()] })}><Plus /> Add project</Button>
        </section>

        <section className="space-y-3">
          <SectionTitle>Certifications</SectionTitle>
          <Textarea aria-label="Certifications, one per line" rows={3} placeholder="One per line" value={d.certs} onChange={(e) => setD({ ...d, certs: e.target.value })} />
        </section>
      </SheetBody>
      <SheetFooter>
        {dirty && <span className="mr-auto text-xs text-muted-foreground">Unsaved changes</span>}
        <Button variant="outline" onClick={onClose}>Cancel</Button>
        <Button loading={save.isPending} disabled={!dirty} onClick={submit}>Save changes</Button>
      </SheetFooter>
    </>
  );
}

/** Right-hand drawer to review and correct what we read from a resume. Reused by the profile page and the apply dialog. */
export function ResumeReviewSheet({ resumeId, open, onOpenChange }: { resumeId: string | null; open: boolean; onOpenChange: (o: boolean) => void }) {
  const dirty = useRef(false);
  const [confirm, setConfirm] = useState(false);
  const setDirty = useCallback((v: boolean) => { dirty.current = v; }, []);
  const q = useQuery({
    queryKey: ["resume", resumeId],
    queryFn: () => api<ResumeDetailOut>(`/resumes/${resumeId}`),
    enabled: open && !!resumeId,
    staleTime: 30_000,
    refetchInterval: (query) => (["pending", "processing"].includes(query.state.data?.parse_status ?? "") ? 2000 : false),
  });
  const r = q.data;
  const finish = () => { dirty.current = false; setConfirm(false); onOpenChange(false); };
  const request = () => (dirty.current ? setConfirm(true) : finish());
  const busy = r && (r.parse_status === "pending" || r.parse_status === "processing");
  return (
    <>
      <Sheet open={open} onOpenChange={(o) => (o ? onOpenChange(true) : request())}>
        <SheetContent aria-describedby={undefined}>
          <SheetHeader>
            <SheetTitle>Review resume details</SheetTitle>
            <SheetDescription>{r ? `${r.filename} · ${fmtSize(r.size)} · uploaded ${fmtDate(r.created_at)}` : "Check what we read from your resume and fix anything that’s off."}</SheetDescription>
          </SheetHeader>
          {q.isError ? (
            <SheetBody><Notice tone="error" title="Couldn’t load this resume" action={{ label: "Try again", onClick: () => q.refetch() }}>Please try again in a moment.</Notice></SheetBody>
          ) : !r ? (
            <SheetBody>{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24 rounded-2xl" />)}</SheetBody>
          ) : busy ? (
            <SheetBody><div className="flex flex-col items-center gap-3 py-16 text-center"><Loader2 className="size-8 animate-spin text-primary" /><p className="font-medium">Reading your resume…</p><p className="text-sm text-muted-foreground">This usually takes a few seconds.</p></div></SheetBody>
          ) : (
            <ReviewForm key={r.id} resume={r} onDirty={setDirty} onClose={request} onSaved={finish} />
          )}
        </SheetContent>
      </Sheet>
      <Dialog open={confirm} onOpenChange={setConfirm}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>Discard your changes?</DialogTitle><DialogDescription>You have unsaved edits to this resume. If you close now they will be lost.</DialogDescription></DialogHeader>
          <DialogFooter><Button variant="outline" onClick={() => setConfirm(false)}>Keep editing</Button><Button variant="destructive" onClick={finish}>Discard</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
