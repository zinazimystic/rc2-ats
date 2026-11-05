"use client";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { JobOut } from "@/lib/types";
import { JobForm } from "@/components/app/job-form";
import { ErrorState, PageHeader, Skeleton } from "@/components/ui/misc";

export default function EditJob() {
  const { id } = useParams<{ id: string }>();
  const q = useQuery({ queryKey: ["job", id], queryFn: () => api<JobOut>(`/jobs/${id}`) });
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Edit job" />
      {q.isError ? <ErrorState error={q.error} retry={() => q.refetch()} /> : !q.data ? <Skeleton className="h-96" /> : <JobForm job={q.data} />}
    </div>
  );
}
