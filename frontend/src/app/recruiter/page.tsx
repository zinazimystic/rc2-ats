import { HydrationBoundary } from "@tanstack/react-query";
import { prefetched } from "@/lib/server";
import Dashboard from "@/components/app/pages/recruiter-dashboard";

export default async function Page() {
  const state = await prefetched([
    [["jobs", "all"], "/jobs"],
    [["analytics", ""], "/analytics/overview"],
    [["interviews", "dash"], "/interviews"],
  ]);
  return <HydrationBoundary state={state}><Dashboard /></HydrationBoundary>;
}
