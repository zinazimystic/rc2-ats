/** Query keys shared by server prefetch and client hooks (must not live in a "use client" module). */
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
