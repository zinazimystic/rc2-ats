"use client";
import { useEffect, useMemo, useRef } from "react";
import { ExternalLink } from "lucide-react";
import type { Evidence, ResumeDetailOut } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FlagList, VerificationBadge } from "@/components/app/common";
import { Banner } from "@/components/ui/misc";
import { friendlyError } from "@/lib/errors";

export interface Range { start: number; end: number; key: string }

/** Resolve an evidence span to real offsets: trust start/end only if they match the quote, else search for it. */
export function resolveRange(text: string, e: { quote?: string | null; start: number | null; end: number | null }): [number, number] | null {
  const quote = e.quote;
  if (e.start != null && e.end != null && e.end > e.start && e.end <= text.length) {
    if (!quote || text.slice(e.start, e.end).trim() === quote.trim()) return [e.start, e.end];
  }
  if (quote && quote.trim().length >= 3) {
    const i = text.indexOf(quote.trim());
    if (i >= 0) return [i, i + quote.trim().length];
    const lower = text.toLowerCase().indexOf(quote.trim().toLowerCase());
    if (lower >= 0) return [lower, lower + quote.trim().length];
  }
  return null;
}

function HighlightedText({ text, ranges, active }: { text: string; ranges: Range[]; active: string | null }) {
  const ref = useRef<HTMLDivElement>(null);
  const parts = useMemo(() => {
    const sorted = [...ranges].sort((a, b) => a.start - b.start || b.end - a.end);
    const out: { s: number; e: number; hit: boolean; active: boolean }[] = [];
    let cur = 0;
    for (const r of sorted) {
      if (r.end <= cur) continue;
      const s = Math.max(r.start, cur);
      if (s > cur) out.push({ s: cur, e: s, hit: false, active: false });
      out.push({ s, e: r.end, hit: true, active: r.key === active });
      cur = r.end;
    }
    if (cur < text.length) out.push({ s: cur, e: text.length, hit: false, active: false });
    return out;
  }, [ranges, text, active]);
  useEffect(() => {
    ref.current?.querySelector("mark.ev-active")?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [active]);
  return (
    <div ref={ref} className="max-h-[70vh] overflow-y-auto rounded-lg border bg-muted/30 p-4 font-mono text-[13px] leading-relaxed whitespace-pre-wrap" tabIndex={0} aria-label="Resume text">
      {parts.map((p, i) => p.hit ? <mark key={i} className={p.active ? "ev ev-active" : "ev"}>{text.slice(p.s, p.e)}</mark> : <span key={i}>{text.slice(p.s, p.e)}</span>)}
    </div>
  );
}

export function ResumeView({ resume, evidence, activeKey }: { resume: ResumeDetailOut; evidence: (Evidence & { key: string })[]; activeKey: string | null }) {
  const text = resume.text ?? "";
  const ranges = useMemo(() => {
    const out: Range[] = [];
    for (const e of evidence) {
      const r = resolveRange(text, e);
      if (r) out.push({ start: r[0], end: r[1], key: e.key });
    }
    for (const s of resume.skills) {
      if (s.removed || s.presence !== "present") continue;
      const r = resolveRange(text, { quote: s.evidence, start: s.start, end: s.end });
      if (r) out.push({ start: r[0], end: r[1], key: `skill:${s.id}` });
    }
    return out;
  }, [evidence, resume.skills, text]);
  const p = resume.parsed;
  return (
    <div className="grid gap-4 lg:grid-cols-5">
      <div className="space-y-3 lg:col-span-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-muted-foreground">{resume.filename} · {resume.page_count ?? "?"} page(s) · <mark className="ev">highlighted</mark> = evidence used in scoring</p>
          <Button variant="outline" size="sm" asChild><a href={`/api/resumes/${resume.id}/file`} target="_blank" rel="noreferrer"><ExternalLink /> Original file</a></Button>
        </div>
        {resume.warnings.map((w, i) => <Banner key={i} tone="warning">{friendlyError(w, "Part of this file may not have been read perfectly.")}</Banner>)}
        <FlagList flags={resume.integrity_flags} />
        {text ? <HighlightedText text={text} ranges={ranges} active={activeKey} /> : <Banner tone="warning">No text could be extracted from this file (it may be a scanned image).</Banner>}
      </div>
      <div className="space-y-3 lg:col-span-2">
        <Card>
          <CardHeader><CardTitle>Parsed profile</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex items-center gap-2 text-[13px] text-muted-foreground">Read from the uploaded file{p?.total_years_claimed != null && ` · ${p.total_years_claimed} yrs claimed`}</div>
            {p?.summary && <p>{p.summary}</p>}
            {p?.experience.map((x, i) => (
              <div key={i} className="rounded-md border p-2">
                <div className="flex items-start justify-between gap-2"><p className="font-medium">{x.title ?? "Role"} <span className="font-normal text-muted-foreground">@ {x.company ?? "—"}</span></p><VerificationBadge v={x.verification} /></div>
                <p className="text-[13px] text-muted-foreground">{x.start_date ?? "?"} – {x.current ? "present" : (x.end_date ?? "?")}</p>
              </div>
            ))}
            {p?.education.map((x, i) => (
              <div key={i} className="rounded-md border p-2"><div className="flex items-start justify-between gap-2"><p className="font-medium">{x.degree ?? x.level ?? "Education"}{x.field && `, ${x.field}`}</p><VerificationBadge v={x.verification} /></div><p className="text-[13px] text-muted-foreground">{x.institution} {x.end_year && `· ${x.end_year}`}</p></div>
            ))}
            {p?.projects.map((x, i) => (
              <div key={i} className="rounded-md border p-2"><div className="flex items-start justify-between gap-2"><p className="font-medium">{x.name ?? "Project"}</p><VerificationBadge v={x.verification} /></div><p className="text-[13px] text-muted-foreground">{x.tech.join(", ")}</p></div>
            ))}
            {p && p.certifications.length > 0 && <div className="flex flex-wrap gap-1">{p.certifications.map((c) => <Badge key={c} variant="outline">{c}</Badge>)}</div>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Skills ({resume.skills.filter((s) => !s.removed).length})</CardTitle></CardHeader>
          <CardContent className="space-y-1.5">
            {resume.skills.filter((s) => !s.removed).map((s) => (
              <div key={s.id} className="flex items-center justify-between gap-2 text-sm">
                <span className={s.presence === "absent" ? "text-muted-foreground line-through" : ""}>{s.name}</span>
                <VerificationBadge v={s.verification} />
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
