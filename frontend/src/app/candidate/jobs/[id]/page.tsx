import { HydrationBoundary } from "@tanstack/react-query";
import { prefetched } from "@/lib/server";
import { qk } from "@/lib/query-keys";
import CandidateJob from "@/components/app/pages/candidate-job";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const state = await prefetched([
    [qk.job(id), `/jobs/${encodeURIComponent(id)}`],
    [qk.resumes, "/candidates/me/resumes"],
  ]);
  return <HydrationBoundary state={state}><CandidateJob /></HydrationBoundary>;
}
