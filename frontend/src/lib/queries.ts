"use client";
import { keepPreviousData, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { api, ApiError, qs } from "./api";
import type {
  AnalyticsOut, CandidateApplicationOut, CandidateDashboardOut, JobListItem, JobOut, MyMatchOut, ProfileOut, RecommendationOut, ResumeOut, UpcomingInterview,
} from "./types";

export const STALE = 45_000;

export const qk = {
  dashboard: ["candidate-dashboard"] as const,
  profile: ["profile"] as const,
  resumes: ["resumes"] as const,
  applications: ["my-applications"] as const,
  recommendations: ["recommendations"] as const,
  openJobs: ["jobs", "open"] as const,
  job: (id: string) => ["job", id] as const,
  match: (jobId: string, resumeId: string | null) => ["my-match", jobId, resumeId ?? "default"] as const,
};

const processing = (r: ResumeOut) => r.parse_status === "pending" || r.parse_status === "processing";
const appBusy = (a: CandidateApplicationOut) => a.processing_state === "queued" || a.processing_state === "processing";

/** Seed the per-resource caches so other pages render instantly from the one dashboard payload. */
function hydrate(qc: QueryClient, d: CandidateDashboardOut) {
  qc.setQueryData(qk.profile, d.profile);
  qc.setQueryData(qk.resumes, d.resumes);
  qc.setQueryData(qk.applications, d.applications);
  qc.setQueryData(qk.recommendations, d.recommendations);
  qc.setQueryData(qk.openJobs, d.open_jobs);
}

async function fetchDashboard(qc: QueryClient): Promise<CandidateDashboardOut> {
  let d: CandidateDashboardOut;
  try {
    d = await api<CandidateDashboardOut>("/candidates/me/dashboard");
  } catch (e) {
    // Older backend without the aggregate endpoint: fetch the same pieces in parallel.
    if (!(e instanceof ApiError) || (e.status !== 404 && e.status !== 405)) throw e;
    const [profile, resumes, applications, recommendations, open_jobs] = await Promise.all([
      api<ProfileOut>("/candidates/me/profile"),
      api<ResumeOut[]>("/candidates/me/resumes"),
      api<CandidateApplicationOut[]>("/applications/me"),
      api<RecommendationOut[]>("/candidates/me/recommendations").catch(() => [] as RecommendationOut[]),
      api<JobListItem[]>(`/jobs${qs({ status: "open" })}`),
    ]);
    const now = Date.now();
    const upcoming_interviews: UpcomingInterview[] = applications
      .flatMap((a) => a.interviews.map((iv) => ({ ...iv, job_title: a.job.title })))
      .filter((iv) => iv.status === "scheduled" && new Date(iv.end_at).getTime() >= now)
      .sort((a, b) => a.start_at.localeCompare(b.start_at));
    d = { profile, resumes, applications, recommendations, open_jobs, upcoming_interviews, unread_notifications: 0 };
  }
  hydrate(qc, d);
  return d;
}

/** ONE request for the whole candidate home. */
export function useCandidateDashboard(enabled = true) {
  const qc = useQueryClient();
  return useQuery({
    queryKey: qk.dashboard,
    queryFn: () => fetchDashboard(qc),
    enabled,
    staleTime: STALE,
    placeholderData: keepPreviousData,
    refetchInterval: (q) => {
      const d = q.state.data;
      return d && (d.resumes.some(processing) || d.applications.some(appBusy)) ? 2500 : false;
    },
  });
}

export function useResumes() {
  return useQuery({
    queryKey: qk.resumes,
    queryFn: () => api<ResumeOut[]>("/candidates/me/resumes"),
    staleTime: STALE,
    placeholderData: keepPreviousData,
    refetchInterval: (q) => (q.state.data?.some(processing) ? 2000 : false),
  });
}
export function useProfile() {
  return useQuery({ queryKey: qk.profile, queryFn: () => api<ProfileOut>("/candidates/me/profile"), staleTime: STALE, placeholderData: keepPreviousData });
}
export function useMyApplications() {
  return useQuery({
    queryKey: qk.applications,
    queryFn: () => api<CandidateApplicationOut[]>("/applications/me"),
    staleTime: STALE,
    placeholderData: keepPreviousData,
    refetchInterval: (q) => (q.state.data?.some(appBusy) ? 2000 : 20_000),
  });
}
export function useOpenJobs() {
  return useQuery({ queryKey: qk.openJobs, queryFn: () => api<JobListItem[]>(`/jobs${qs({ status: "open" })}`), staleTime: STALE, placeholderData: keepPreviousData });
}
export function useJob(id: string) {
  return useQuery({ queryKey: qk.job(id), queryFn: () => api<JobOut>(`/jobs/${id}`), staleTime: STALE, placeholderData: keepPreviousData });
}

/** Estimated fit of a resume for a job (candidate's own view). Lazy: pass enabled=false until needed. */
export function useMyMatch(jobId: string, resumeId: string | null, enabled = true) {
  return useQuery({
    queryKey: qk.match(jobId, resumeId),
    queryFn: () => api<MyMatchOut>(`/jobs/${jobId}/my-match${qs({ resume_id: resumeId })}`),
    enabled,
    staleTime: 60_000,
    retry: false,
    placeholderData: keepPreviousData,
  });
}

/** Warm the cache for a route before the user gets there (hover / focus / login success). */
export function prefetchRoute(qc: QueryClient, href: string) {
  const pre = (key: readonly unknown[], fn: () => Promise<unknown>) => qc.prefetchQuery({ queryKey: key, queryFn: fn, staleTime: STALE });
  if (href === "/candidate") void pre(qk.dashboard, () => fetchDashboard(qc));
  else if (href === "/candidate/applications") void pre(qk.applications, () => api<CandidateApplicationOut[]>("/applications/me"));
  else if (href === "/candidate/resume") {
    void pre(qk.profile, () => api<ProfileOut>("/candidates/me/profile"));
    void pre(qk.resumes, () => api<ResumeOut[]>("/candidates/me/resumes"));
  } else if (href.startsWith("/candidate/jobs/")) {
    const id = href.split("/")[3];
    if (id) void pre(qk.job(id), () => api<JobOut>(`/jobs/${id}`));
  } else if (href === "/recruiter/jobs") void pre(["jobs", "all"], () => api<JobListItem[]>("/jobs"));
  else if (href === "/recruiter") {
    void pre(["jobs", "all"], () => api<JobListItem[]>("/jobs"));
    void pre(["analytics", ""], () => api<AnalyticsOut>("/analytics/overview"));
  }
}

export function usePrefetch() {
  const qc = useQueryClient();
  return useCallback((href: string) => prefetchRoute(qc, href), [qc]);
}
