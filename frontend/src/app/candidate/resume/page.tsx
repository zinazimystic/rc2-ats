"use client";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Target } from "lucide-react";
import { api } from "@/lib/api";
import { qk, useProfile, useResumes } from "@/lib/queries";
import { notify } from "@/lib/toast";
import type { ProfileIn, ProfileOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox, Field, Input, Textarea } from "@/components/ui/input";
import { ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";
import { Notice } from "@/components/ui/notice";
import { Progress } from "@/components/ui/misc";
import { ContactCard } from "@/components/app/contact";
import { ResumeManager } from "@/components/app/resume-manager";
import { ResumeReviewSheet } from "@/components/app/resume-review-sheet";

function ProfileForm({ p }: { p: ProfileOut }) {
  const qc = useQueryClient();
  const [f, setF] = useState({ headline: p.headline ?? "", phone: p.phone ?? "", location: p.location ?? "", links: p.links.join("\n"), interests: p.interests.join(", "), pool: p.talent_pool_opt_in, retention: p.retention_until?.slice(0, 10) ?? "" });
  const [err, setErr] = useState<string | null>(null);
  const m = useMutation({
    mutationFn: (b: ProfileIn) => api<ProfileOut>("/candidates/me/profile", { method: "PATCH", body: b }),
    onSuccess: (r) => {
      qc.setQueryData(qk.profile, r);
      qc.invalidateQueries({ queryKey: qk.dashboard });
      notify.success("Profile saved");
    },
    onError: (e) => notify.error(e),
  });
  function save() {
    const links = f.links.split("\n").map((s) => s.trim()).filter(Boolean);
    if (links.some((l) => !/^https?:\/\//i.test(l))) return setErr("Links must start with http:// or https://");
    if (f.phone && !/^[+\d][\d\s().-]{5,}$/.test(f.phone)) return setErr("Enter a valid phone number, for example +92 300 1234567.");
    setErr(null);
    m.mutate({ headline: f.headline.trim() || null, phone: f.phone.trim() || null, location: f.location.trim() || null, links, interests: f.interests.split(",").map((s) => s.trim()).filter(Boolean), talent_pool_opt_in: f.pool, retention_until: f.retention ? new Date(f.retention).toISOString() : null });
  }
  return (
    <Card>
      <CardHeader><CardTitle>Profile & privacy</CardTitle><CardDescription>{p.full_name}</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        {err && <Notice tone="error" onDismiss={() => setErr(null)}>{err}</Notice>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Headline" htmlFor="pf-h" className="sm:col-span-2"><Input id="pf-h" value={f.headline} onChange={(e) => setF({ ...f, headline: e.target.value })} placeholder="Backend developer · Python & Django" /></Field>
          <Field label="Phone" htmlFor="pf-p" hint="Include the country code, e.g. +92"><Input id="pf-p" inputMode="tel" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
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

function Completion({ p }: { p: ProfileOut }) {
  const c = p.completion;
  if (!c || c.percent >= 100) return null;
  return (
    <Card>
      <CardContent className="space-y-2 pt-5">
        <div className="flex items-center gap-2"><Target className="size-4 text-primary" /><p className="text-sm font-semibold">Complete your profile</p><span className="ml-auto text-sm font-bold tabular-nums">{Math.round(c.percent)}%</span></div>
        <Progress value={c.percent} />
        {c.missing.length > 0 && <p className="text-xs text-muted-foreground">Still to add: {c.missing.join(", ")}</p>}
      </CardContent>
    </Card>
  );
}

function PageSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-5" aria-busy="true" aria-label="Loading your profile">
      <div className="space-y-4 lg:col-span-3"><Skeleton className="h-44 rounded-3xl" /><Skeleton className="h-36 rounded-3xl" /><Skeleton className="h-36 rounded-3xl" /></div>
      <div className="space-y-4 lg:col-span-2"><Skeleton className="h-56 rounded-3xl" /><Skeleton className="h-96 rounded-3xl" /></div>
    </div>
  );
}

export default function ResumePage() {
  const profile = useProfile();
  const resumes = useResumes();
  const [review, setReview] = useState<string | null>(null);
  return (
    <>
      <PageHeader title="Resume & profile" description="Upload your resume, check what we read from it, and control your data." />
      {profile.isError && !profile.data ? <ErrorState error={profile.error} retry={() => profile.refetch()} /> : !profile.data || !resumes.data ? <PageSkeleton /> : (
        <div className="grid items-start gap-6 lg:grid-cols-5">
          <div className="space-y-4 lg:col-span-3">
            <h2 className="text-lg font-semibold">Your resumes</h2>
            <ResumeManager onReview={setReview} />
          </div>
          <div className="space-y-4 lg:col-span-2">
            <Completion p={profile.data} />
            <ContactCard profile={profile.data} />
            <ProfileForm key={profile.data.user_id} p={profile.data} />
          </div>
        </div>
      )}
      <ResumeReviewSheet resumeId={review} open={!!review} onOpenChange={(o) => !o && setReview(null)} />
    </>
  );
}
