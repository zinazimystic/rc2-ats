"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { CopyCheck, Link2, X } from "lucide-react";
import { api } from "@/lib/api";
import type { CandidateBrief, DuplicateOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";
import { notifyError } from "@/components/app/common";
import { cn } from "@/lib/utils";

const Person = ({ c }: { c: CandidateBrief }) => (
  <div className="min-w-0 flex-1 rounded-md border p-3"><p className="truncate font-medium">{c.full_name}</p><p className="truncate text-xs text-muted-foreground">{c.email}</p><p className="truncate text-xs text-muted-foreground">{[c.headline, c.location].filter(Boolean).join(" · ")}</p></div>
);

export default function Duplicates() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("pending");
  const q = useQuery({ queryKey: ["duplicates", status], queryFn: () => api<DuplicateOut[]>(`/duplicates?status=${status}`) });
  const act = useMutation({
    mutationFn: ({ id, a }: { id: string; a: "confirm" | "dismiss" }) => api<DuplicateOut>(`/duplicates/${id}/${a}`, { method: "POST" }),
    onSuccess: (_, v) => { toast.success(v.a === "confirm" ? "Records linked (nothing was deleted)" : "Dismissed"); qc.invalidateQueries({ queryKey: ["duplicates"] }); qc.invalidateQueries({ queryKey: ["applicants"] }); },
    onError: notifyError,
  });
  return (
    <>
      <PageHeader title="Duplicate candidates" description="Likely duplicate profiles detected by email, phone, name and resume similarity. Confirming links the records — it never deletes data." />
      <div role="group" className="mb-4 flex w-fit gap-1 rounded-lg bg-muted p-1">
        {["pending", "confirmed", "dismissed"].map((s) => <button key={s} aria-pressed={status === s} onClick={() => setStatus(s)} className={cn("rounded-md px-3 py-1 text-sm font-medium capitalize", status === s ? "bg-card shadow-xs" : "text-muted-foreground")}>{s}</button>)}
      </div>
      {q.isError ? <ErrorState error={q.error} retry={() => q.refetch()} /> : !q.data ? <Skeleton className="h-40" /> : q.data.length === 0 ? <EmptyState icon={<CopyCheck className="size-8" />} title={`No ${status} duplicates`} /> : (
        <div className="space-y-3">
          {q.data.map((d) => (
            <Card key={d.id}><CardContent className="space-y-3 pt-4">
              <div className="flex flex-col gap-3 sm:flex-row"><Person c={d.candidate_a} /><Person c={d.candidate_b} /></div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-1">{d.similarity != null && <Badge variant="warning">{Math.round(d.similarity * 100)}% similar</Badge>}{d.reasons.map((r) => <Badge key={r} variant="secondary">{r}</Badge>)}</div>
                {d.status === "pending" && <div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => act.mutate({ id: d.id, a: "dismiss" })}><X /> Not a duplicate</Button><Button size="sm" onClick={() => act.mutate({ id: d.id, a: "confirm" })}><Link2 /> Confirm & link</Button></div>}
              </div>
            </CardContent></Card>
          ))}
        </div>
      )}
    </>
  );
}
