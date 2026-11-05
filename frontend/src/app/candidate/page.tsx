import { HydrationBoundary } from "@tanstack/react-query";
import { prefetched } from "@/lib/server";
import { qk } from "@/lib/query-keys";
import type { CandidateDashboardOut } from "@/lib/types";
import CandidateHome from "@/components/app/pages/candidate-home";

export default async function Page() {
  const state = await prefetched([[qk.dashboard, "/candidates/me/dashboard"]], (qc) => {
    // Mirror the client's hydrate(): seed the per-resource caches from the one dashboard payload.
    const d = qc.getQueryData<CandidateDashboardOut>(qk.dashboard);
    if (!d) return;
    qc.setQueryData(qk.profile, d.profile);
    qc.setQueryData(qk.resumes, d.resumes);
    qc.setQueryData(qk.applications, d.applications);
    qc.setQueryData(qk.recommendations, d.recommendations);
    qc.setQueryData(qk.openJobs, d.open_jobs);
  });
  return <HydrationBoundary state={state}><CandidateHome /></HydrationBoundary>;
}
