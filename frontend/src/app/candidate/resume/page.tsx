"use client";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { FileText, Loader2, UploadCloud } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import type { ProfileIn, ProfileOut, ResumeDetailOut, ResumeOut } from "@/lib/types";
import { fmtDate, fmtSize } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox, Field, Input, Textarea } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Banner, ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";
import { ParsedEditor, ResumeStatusNotes, SkillsManager } from "@/components/app/resume-editor";
import { cn } from "@/lib/utils";

const MAX_MB = 5;
const OK_EXT = [".pdf", ".docx"];

function Uploader({ onDone }: { onDone: (r: ResumeOut) => void }) {
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const up = useMutation({
    mutationFn: (f: File) => { const fd = new FormData(); fd.append("file", f); return api<ResumeOut>("/candidates/me/resumes", { form: fd }); },
    onSuccess: (r) => { toast.success("Uploaded — analysing your resume…"); qc.invalidateQueries({ queryKey: ["resumes"] }); onDone(r); },
    onError: (e) => setErr(errMsg(e)),
  });
  function take(f: File | undefined) {
    if (!f) return;
    const ext = f.name.slice(f.name.lastIndexOf(".")).toLowerCase();
    if (!OK_EXT.includes(ext)) return setErr("Only PDF and DOCX files are supported");
    if (f.size === 0) return setErr("That file is empty");
    if (f.size > MAX_MB * 1024 * 1024) return setErr(`File is too large (max ${MAX_MB} MB)`);
    setErr(null);
    up.mutate(f);
  }
  return (
    <div className="space-y-2">
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); take(e.dataTransfer.files[0]); }}
        className={cn("flex flex-col items-center gap-2 rounded-xl border-2 border-dashed p-8 text-center transition-colors", drag && "border-primary bg-primary/5")}
      >
        {up.isPending ? <Loader2 className="size-8 animate-spin text-primary" /> : <UploadCloud className="size-8 text-muted-foreground" />}
        <p className="font-medium">{up.isPending ? "Uploading…" : "Drop your resume here"}</p>
        <p className="text-xs text-muted-foreground">PDF or DOCX · up to {MAX_MB} MB · text-based files work best</p>
        <Button variant="outline" disabled={up.isPending} onClick={() => input.current?.click()}>Choose file</Button>
        <input ref={input} type="file" hidden accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" aria-label="Upload resume" onChange={(e) => { take(e.target.files?.[0]); e.target.value = ""; }} />
      </div>
      {err && <Banner tone="danger">{err}</Banner>}
    </div>
  );
}

function ParseBadge({ r }: { r: ResumeOut }) {
  if (r.parse_status === "parsed") return <Badge variant="success">Parsed</Badge>;
  if (r.parse_status === "failed") return <Badge variant="destructive">Failed</Badge>;
  return <Badge variant="warning"><Loader2 className="animate-spin" />{r.parse_status === "pending" ? "Queued" : "Analysing"}</Badge>;
}

function ResumeDetail({ id }: { id: string }) {
  const q = useQuery({
    queryKey: ["resume", id],
    queryFn: () => api<ResumeDetailOut>(`/resumes/${id}`),
    refetchInterval: (query) => (["pending", "processing"].includes(query.state.data?.parse_status ?? "") ? 2000 : false),
  });
  if (q.isError) return <ErrorState error={q.error} retry={() => q.refetch()} />;
  const r = q.data;
  if (!r) return <Skeleton className="h-64" />;
  if (r.parse_status === "pending" || r.parse_status === "processing")
    return <Card><CardContent className="flex flex-col items-center gap-3 py-12"><Loader2 className="size-8 animate-spin text-primary" /><p className="font-medium">Analysing {r.filename}…</p><p className="text-sm text-muted-foreground">Extracting skills, experience and education. This usually takes a few seconds.</p></CardContent></Card>;
  return (
    <div className="space-y-4">
      <ResumeStatusNotes resume={r} />
      {r.parse_status === "parsed" && (
        <Tabs defaultValue="skills">
          <TabsList><TabsTrigger value="skills">Skills</TabsTrigger><TabsTrigger value="details">Details</TabsTrigger><TabsTrigger value="text">Extracted text</TabsTrigger></TabsList>
          <TabsContent value="skills"><SkillsManager resume={r} /></TabsContent>
          <TabsContent value="details"><ParsedEditor key={r.id + r.created_at + (r.parsed?.experience.length ?? 0)} resume={r} /></TabsContent>
          <TabsContent value="text"><pre className="max-h-[60vh] overflow-auto rounded-lg border bg-muted/30 p-4 text-xs whitespace-pre-wrap">{r.text || "No text extracted."}</pre></TabsContent>
        </Tabs>
      )}
    </div>
  );
}

function ProfileForm({ p }: { p: ProfileOut }) {
  const qc = useQueryClient();
  const [f, setF] = useState({ headline: p.headline ?? "", phone: p.phone ?? "", location: p.location ?? "", links: p.links.join("\n"), interests: p.interests.join(", "), pool: p.talent_pool_opt_in, retention: p.retention_until?.slice(0, 10) ?? "" });
  const [err, setErr] = useState<string | null>(null);
  const m = useMutation({
    mutationFn: (b: ProfileIn) => api<ProfileOut>("/candidates/me/profile", { method: "PATCH", body: b }),
    onSuccess: (r) => { qc.setQueryData(["profile"], r); toast.success("Profile saved"); },
    onError: (e) => setErr(errMsg(e)),
  });
  function save() {
    const links = f.links.split("\n").map((s) => s.trim()).filter(Boolean);
    if (links.some((l) => !/^https?:\/\//i.test(l))) return setErr("Links must start with http:// or https://");
    if (f.phone && !/^[+\d][\d\s().-]{5,}$/.test(f.phone)) return setErr("Enter a valid phone number");
    setErr(null);
    m.mutate({ headline: f.headline.trim() || null, phone: f.phone.trim() || null, location: f.location.trim() || null, links, interests: f.interests.split(",").map((s) => s.trim()).filter(Boolean), talent_pool_opt_in: f.pool, retention_until: f.retention ? new Date(f.retention).toISOString() : null });
  }
  return (
    <Card>
      <CardHeader><CardTitle>Profile & privacy</CardTitle><CardDescription>{p.full_name} · {p.email}</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        {err && <Banner tone="danger">{err}</Banner>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Headline" htmlFor="pf-h" className="sm:col-span-2"><Input id="pf-h" value={f.headline} onChange={(e) => setF({ ...f, headline: e.target.value })} placeholder="Backend developer · Python & Django" /></Field>
          <Field label="Phone" htmlFor="pf-p"><Input id="pf-p" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
          <Field label="Location" htmlFor="pf-l"><Input id="pf-l" value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} /></Field>
          <Field label="Links (one per line)" htmlFor="pf-k"><Textarea id="pf-k" rows={2} value={f.links} onChange={(e) => setF({ ...f, links: e.target.value })} /></Field>
          <Field label="Interests (comma separated)" htmlFor="pf-i"><Textarea id="pf-i" rows={2} value={f.interests} onChange={(e) => setF({ ...f, interests: e.target.value })} /></Field>
        </div>
        <label className="flex items-start gap-2 text-sm"><Checkbox className="mt-0.5" checked={f.pool} onChange={(e) => setF({ ...f, pool: e.target.checked })} /><span><strong>Join the talent pool.</strong> Let recruiters consider me for other roles that fit my resume.</span></label>
        <Field label="Delete my data after" htmlFor="pf-r" hint="Optional data-retention date"><Input id="pf-r" type="date" className="max-w-48" value={f.retention} onChange={(e) => setF({ ...f, retention: e.target.value })} /></Field>
        <Button loading={m.isPending} onClick={save}>Save profile</Button>
      </CardContent>
    </Card>
  );
}

export default function ResumePage() {
  const [sel, setSel] = useState<string | null>(null);
  const list = useQuery({
    queryKey: ["resumes"],
    queryFn: () => api<ResumeOut[]>("/candidates/me/resumes"),
    refetchInterval: (query) => (query.state.data?.some((r) => r.parse_status === "pending" || r.parse_status === "processing") ? 2000 : false),
  });
  const profile = useQuery({ queryKey: ["profile"], queryFn: () => api<ProfileOut>("/candidates/me/profile") });
  const current = sel ?? list.data?.find((r) => r.is_current)?.id ?? list.data?.[0]?.id ?? null;
  return (
    <>
      <PageHeader title="Resume & profile" description="Upload your resume, check what we extracted, and control your data." />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-4">
          <Uploader onDone={(r) => setSel(r.id)} />
          {list.data && list.data.length > 0 && (
            <Card><CardHeader><CardTitle>Your resumes</CardTitle></CardHeader><CardContent className="space-y-1">
              {list.data.map((r) => (
                <button key={r.id} onClick={() => setSel(r.id)} aria-pressed={current === r.id} className={cn("flex w-full items-center gap-3 rounded-lg border p-2.5 text-left text-sm transition-colors hover:bg-muted", current === r.id && "border-primary bg-primary/5")}>
                  <FileText className="size-4 shrink-0 text-muted-foreground" />
                  <span className="min-w-0 flex-1"><span className="block truncate font-medium">{r.filename}</span><span className="text-xs text-muted-foreground">{fmtSize(r.size)} · {fmtDate(r.created_at)}{r.is_current && " · current"}</span></span>
                  <ParseBadge r={r} />
                </button>
              ))}
            </CardContent></Card>
          )}
        </div>
        <div className="space-y-6 lg:col-span-2">
          {list.isError ? <ErrorState error={list.error} retry={() => list.refetch()} /> : !list.data ? <Skeleton className="h-64" /> : current ? <ResumeDetail key={current} id={current} /> : <Banner tone="info">Upload a resume to get started — we’ll extract your skills and experience for you to review.</Banner>}
          {profile.data && <ProfileForm key={profile.dataUpdatedAt} p={profile.data} />}
        </div>
      </div>
    </>
  );
}
