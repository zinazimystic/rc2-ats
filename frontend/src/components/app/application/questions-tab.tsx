"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Pencil, Plus, RefreshCw, Sparkles, Trash2 } from "lucide-react";
import { api, ApiError, errMsg } from "@/lib/api";
import type { Difficulty, QuestionGenerateIn, QuestionIn, QuestionOut } from "@/lib/types";
import { titleCase } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Checkbox, Field, Input, Select, Textarea } from "@/components/ui/input";
import { Banner, EmptyState, ErrorState, Skeleton } from "@/components/ui/misc";
import { notifyError } from "../common";

const DIFFS: Difficulty[] = ["beginner", "intermediate", "advanced"];

function QuestionDialog({ appId, q, open, onOpenChange }: { appId: string; q?: QuestionOut; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const [f, setF] = useState<QuestionIn & { guidelines: string }>({
    difficulty: q?.difficulty ?? "intermediate", category: q?.category ?? "Technical", question: q?.question ?? "",
    answer_guidelines: [], related_skill: q?.related_skill ?? "", guidelines: (q?.answer_guidelines ?? []).join("\n"),
  });
  const [err, setErr] = useState<string | null>(null);
  const m = useMutation({
    mutationFn: () => {
      const body: QuestionIn = { difficulty: f.difficulty, category: f.category.trim() || "General", question: f.question.trim(), answer_guidelines: f.guidelines.split("\n").map((s) => s.trim()).filter(Boolean), related_skill: f.related_skill?.trim() || null };
      return q ? api<QuestionOut>(`/questions/${q.id}`, { method: "PATCH", body }) : api<QuestionOut>(`/applications/${appId}/questions`, { body });
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["questions", appId] }); onOpenChange(false); },
    onError: (e) => setErr(errMsg(e)),
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>{q ? "Edit question" : "Add question"}</DialogTitle></DialogHeader>
        {err && <Banner tone="danger">{err}</Banner>}
        <Field label="Question" htmlFor="q-text"><Textarea id="q-text" value={f.question} onChange={(e) => setF({ ...f, question: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Difficulty" htmlFor="q-diff"><Select id="q-diff" value={f.difficulty} onChange={(e) => setF({ ...f, difficulty: e.target.value as Difficulty })}>{DIFFS.map((d) => <option key={d} value={d}>{titleCase(d)}</option>)}</Select></Field>
          <Field label="Category" htmlFor="q-cat"><Input id="q-cat" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} /></Field>
        </div>
        <Field label="Related skill (optional)" htmlFor="q-skill"><Input id="q-skill" value={f.related_skill ?? ""} onChange={(e) => setF({ ...f, related_skill: e.target.value })} /></Field>
        <Field label="Answer guidelines (one per line)" htmlFor="q-guide"><Textarea id="q-guide" value={f.guidelines} onChange={(e) => setF({ ...f, guidelines: e.target.value })} /></Field>
        <DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button><Button loading={m.isPending} disabled={f.question.trim().length < 5} onClick={() => m.mutate()}>Save</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function QuestionsTab({ appId }: { appId: string }) {
  const qc = useQueryClient();
  const [gen, setGen] = useState<QuestionGenerateIn>({ beginner: 2, intermediate: 3, advanced: 2, include_projects: true, append: false });
  const [dlg, setDlg] = useState<{ open: boolean; q?: QuestionOut }>({ open: false });
  const q = useQuery({ queryKey: ["questions", appId], queryFn: () => api<QuestionOut[]>(`/applications/${appId}/questions`) });
  const inv = () => qc.invalidateQueries({ queryKey: ["questions", appId] });
  const generate = useMutation({
    mutationFn: () => api<QuestionOut[]>(`/applications/${appId}/questions/generate`, { body: gen }),
    onSuccess: (r) => { toast.success(`Generated ${r.length} questions`); inv(); },
  });
  const regen = useMutation({ mutationFn: (id: string) => api<QuestionOut>(`/questions/${id}/regenerate`, { method: "POST" }), onSuccess: inv, onError: notifyError });
  const del = useMutation({ mutationFn: (id: string) => api(`/questions/${id}`, { method: "DELETE" }), onSuccess: inv, onError: notifyError });
  const total = gen.beginner + gen.intermediate + gen.advanced;
  const unavailable = generate.error instanceof ApiError && generate.error.status === 503;
  const num = (k: "beginner" | "intermediate" | "advanced") => (
    <Field label={titleCase(k)} htmlFor={`g-${k}`}><Input id={`g-${k}`} type="number" min={0} max={10} value={gen[k]} onChange={(e) => setGen({ ...gen, [k]: Math.max(0, Math.min(10, Number(e.target.value) || 0)) })} /></Field>
  );
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Sparkles className="size-4 text-primary" />Generate tailored questions</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-3 gap-3 sm:max-w-md">{num("beginner")}{num("intermediate")}{num("advanced")}</div>
          <div className="flex flex-wrap items-center gap-4 text-sm">
            <label className="flex items-center gap-2"><Checkbox checked={gen.include_projects} onChange={(e) => setGen({ ...gen, include_projects: e.target.checked })} /> Include project-based questions</label>
            <label className="flex items-center gap-2"><Checkbox checked={gen.append} onChange={(e) => setGen({ ...gen, append: e.target.checked })} /> Append to existing</label>
          </div>
          {generate.isPending && <Banner tone="info">Generating — this can take up to a minute…</Banner>}
          {generate.error && <Banner tone={unavailable ? "warning" : "danger"}>{unavailable ? "The AI model is currently unavailable, so questions can’t be generated. You can still add questions manually." : errMsg(generate.error)}</Banner>}
          <div className="flex gap-2">
            <Button loading={generate.isPending} disabled={total === 0} onClick={() => generate.mutate()}><Sparkles /> Generate {total} question{total === 1 ? "" : "s"}</Button>
            <Button variant="outline" onClick={() => setDlg({ open: true })}><Plus /> Add manually</Button>
          </div>
        </CardContent>
      </Card>
      {q.isError ? <ErrorState error={q.error} retry={() => q.refetch()} /> : !q.data ? <Skeleton className="h-40" /> : q.data.length === 0 ? (
        <EmptyState title="No questions yet" description="Generate questions grounded in this candidate’s resume and the job requirements." />
      ) : DIFFS.map((d) => {
        const items = q.data.filter((x) => x.difficulty === d);
        if (!items.length) return null;
        return (
          <div key={d} className="space-y-2">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase">{d} ({items.length})</h3>
            {items.map((x) => (
              <Card key={x.id}>
                <CardContent className="space-y-2 pt-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <p className="font-medium">{x.question}</p>
                    <div className="flex shrink-0 gap-1">
                      <Button variant="ghost" size="icon" aria-label="Regenerate question" loading={regen.isPending && regen.variables === x.id} onClick={() => regen.mutate(x.id)}><RefreshCw /></Button>
                      <Button variant="ghost" size="icon" aria-label="Edit question" onClick={() => setDlg({ open: true, q: x })}><Pencil /></Button>
                      <Button variant="ghost" size="icon" aria-label="Delete question" onClick={() => del.mutate(x.id)}><Trash2 /></Button>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1"><Badge variant="outline">{x.category}</Badge>{x.related_skill && <Badge variant="secondary">{x.related_skill}</Badge>}{x.is_edited && <Badge variant="muted">edited</Badge>}</div>
                  {x.answer_guidelines.length > 0 && <ul className="list-disc pl-5 text-sm text-muted-foreground">{x.answer_guidelines.map((g, i) => <li key={i}>{g}</li>)}</ul>}
                  {x.source_quote && <p className="text-xs text-muted-foreground italic">Based on resume: “{x.source_quote}” {x.source_verified === false && <Badge variant="warning">quote unverified</Badge>}</p>}
                </CardContent>
              </Card>
            ))}
          </div>
        );
      })}
      {dlg.open && <QuestionDialog key={dlg.q?.id ?? "new"} appId={appId} q={dlg.q} open onOpenChange={(o) => setDlg({ open: o })} />}
    </div>
  );
}
