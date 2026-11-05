"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import type { HistoryEventOut, NoteOut } from "@/lib/types";
import { fmtDateTime, titleCase } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/misc";
import { notifyError } from "../common";

export function NotesTab({ appId }: { appId: string }) {
  const qc = useQueryClient();
  const [body, setBody] = useState("");
  const q = useQuery({ queryKey: ["notes", appId], queryFn: () => api<NoteOut[]>(`/applications/${appId}/notes`) });
  const inv = () => { qc.invalidateQueries({ queryKey: ["notes", appId] }); qc.invalidateQueries({ queryKey: ["application", appId] }); };
  const add = useMutation({ mutationFn: () => api<NoteOut>(`/applications/${appId}/notes`, { body: { body: body.trim() } }), onSuccess: () => { setBody(""); inv(); }, onError: notifyError });
  const del = useMutation({ mutationFn: (id: string) => api(`/notes/${id}`, { method: "DELETE" }), onSuccess: inv, onError: notifyError });
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Textarea aria-label="New note" placeholder="Private note — never visible to the candidate" value={body} onChange={(e) => setBody(e.target.value)} />
        <Button loading={add.isPending} disabled={!body.trim()} onClick={() => add.mutate()}>Add note</Button>
      </div>
      {q.isError ? <ErrorState error={q.error} retry={() => q.refetch()} /> : !q.data ? <Skeleton className="h-24" /> : q.data.length === 0 ? <EmptyState title="No notes yet" /> : q.data.map((n) => (
        <Card key={n.id}><CardContent className="flex items-start justify-between gap-3 pt-4"><div><p className="text-sm whitespace-pre-wrap">{n.body}</p><p className="mt-1 text-[13px] text-muted-foreground">{n.author_name} · {fmtDateTime(n.created_at)}</p></div><Button variant="ghost" size="icon" aria-label="Delete note" onClick={() => del.mutate(n.id)}><Trash2 /></Button></CardContent></Card>
      ))}
    </div>
  );
}

export function HistoryTab({ appId }: { appId: string }) {
  const q = useQuery({ queryKey: ["history", appId], queryFn: () => api<HistoryEventOut[]>(`/applications/${appId}/history`) });
  if (q.isError) return <ErrorState error={q.error} retry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-40" />;
  if (!q.data.length) return <EmptyState title="No history yet" />;
  return (
    <ol className="relative space-y-4 border-l pl-6">
      {q.data.map((h) => (
        <li key={h.id} className="relative">
          <span className="absolute top-1.5 -left-[1.9rem] size-3 rounded-full border-2 border-primary bg-background" aria-hidden />
          <p className="text-sm font-medium">{titleCase(h.action)}{(h.from_value || h.to_value) && <span className="font-normal text-muted-foreground"> · {h.from_value ?? "—"} → {h.to_value ?? "—"}</span>}</p>
          {h.note && <p className="text-sm text-muted-foreground">“{h.note}”</p>}
          <p className="text-[13px] text-muted-foreground">{h.actor_name ?? "System"}{h.actor_role && ` (${h.actor_role})`} · {fmtDateTime(h.created_at)}</p>
        </li>
      ))}
    </ol>
  );
}
