import { HydrationBoundary } from "@tanstack/react-query";
import { prefetched } from "@/lib/server";
import JobsPage from "@/components/app/pages/recruiter-jobs";

export default async function Page() {
  const state = await prefetched([[["jobs", "all"], "/jobs"]]);
  return <HydrationBoundary state={state}><JobsPage /></HydrationBoundary>;
}
