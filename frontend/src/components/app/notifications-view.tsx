"use client";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck, Mail } from "lucide-react";
import { api } from "@/lib/api";
import type { NotificationOut, Role } from "@/lib/types";
import { timeAgo } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";
import { cn } from "@/lib/utils";
import { notifyError } from "./common";

function List({ outbox }: { outbox?: boolean }) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["notifications", outbox ? "outbox" : "all"],
    queryFn: () => api<NotificationOut[]>(outbox ? "/notifications/outbox" : "/notifications"),
    refetchInterval: 15_000,
  });
  const read = useMutation({
    mutationFn: (id: string) => api(`/notifications/${id}/read`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
    onError: notifyError,
  });
  if (q.isError) return <ErrorState error={q.error} retry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-48" />;
  if (!q.data.length) return <EmptyState icon={outbox ? <Mail className="size-8" /> : <Bell className="size-8" />} title={outbox ? "No emails sent yet" : "You’re all caught up"} description={outbox ? "Simulated emails sent to candidates (status changes, interview invites) appear here." : "New activity will show up here."} />;
  return (
    <Card className="divide-y">
      {q.data.map((n) => {
        const inner = (
          <div className={cn("flex items-start gap-3 p-4", !n.read && !outbox && "bg-primary/5")}>
            <span className={cn("mt-1.5 size-2 shrink-0 rounded-full", n.read || outbox ? "bg-transparent" : "bg-primary")} aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{n.title}</p>
              {n.body && <p className="mt-0.5 text-sm whitespace-pre-wrap text-muted-foreground">{n.body}</p>}
              <p className="mt-1 text-[13px] text-muted-foreground">{outbox && n.recipient_email ? `To ${n.recipient_email} · ` : ""}{timeAgo(n.created_at)}</p>
            </div>
            {!outbox && !n.read && <Button size="sm" variant="ghost" onClick={(e) => { e.preventDefault(); read.mutate(n.id); }}>Mark read</Button>}
          </div>
        );
        return n.link && !outbox ? <Link key={n.id} href={n.link} onClick={() => !n.read && read.mutate(n.id)} className="block hover:bg-muted/50">{inner}</Link> : <div key={n.id}>{inner}</div>;
      })}
    </Card>
  );
}

export function NotificationsView({ role }: { role: Role }) {
  const qc = useQueryClient();
  const all = useMutation({ mutationFn: () => api("/notifications/read-all", { method: "POST" }), onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }), onError: notifyError });
  return (
    <>
      <PageHeader title="Notifications" actions={<Button variant="outline" loading={all.isPending} onClick={() => all.mutate()}><CheckCheck /> Mark all read</Button>} />
      {role === "recruiter" ? (
        <Tabs defaultValue="inbox">
          <TabsList><TabsTrigger value="inbox">Inbox</TabsTrigger><TabsTrigger value="outbox">Email outbox</TabsTrigger></TabsList>
          <TabsContent value="inbox"><List /></TabsContent>
          <TabsContent value="outbox"><List outbox /></TabsContent>
        </Tabs>
      ) : <List />}
    </>
  );
}
