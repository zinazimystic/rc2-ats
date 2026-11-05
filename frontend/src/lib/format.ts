import type { ApplicationStatus, EducationLevel } from "./types";

export function fmtDate(s: string | null | undefined): string {
  if (!s) return "—";
  const d = new Date(s);
  return isNaN(+d) ? "—" : d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}
export function fmtDateTime(s: string | null | undefined): string {
  if (!s) return "—";
  const d = new Date(s);
  return isNaN(+d)
    ? "—"
    : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}
export function fmtTime(s: string): string {
  return new Date(s).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}
export function timeAgo(s: string): string {
  const diff = (new Date().getTime() - new Date(s).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`;
  return fmtDate(s);
}
export function fmtScore(n: number | null | undefined): string {
  return n === null || n === undefined ? "—" : n.toFixed(1);
}
export function fmtSize(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}
export function fmtSalary(min: number | null, max: number | null, cur: string): string | null {
  if (!min && !max) return null;
  const f = (n: number) => n.toLocaleString();
  if (min && max) return `${cur} ${f(min)} – ${f(max)}`;
  return `${cur} ${f((min ?? max) as number)}`;
}
export function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
export function toLocalInput(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

export const STATUS_LABEL: Record<ApplicationStatus, string> = {
  submitted: "Submitted",
  parsed: "Parsed",
  ai_assessed: "AI Assessment Available",
  recruiter_review: "Recruiter Review",
  shortlisted: "Shortlisted",
  interview: "Interview",
  selected: "Selected",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};
export const STATUS_ORDER: ApplicationStatus[] = [
  "submitted",
  "parsed",
  "ai_assessed",
  "recruiter_review",
  "shortlisted",
  "interview",
  "selected",
  "rejected",
  "withdrawn",
];
export const EDUCATION_LABEL: Record<EducationLevel, string> = {
  none: "No requirement",
  high_school: "High school",
  diploma: "Diploma",
  bachelor: "Bachelor's",
  master: "Master's",
  phd: "PhD",
};
export function scoreTone(n: number | null | undefined): string {
  if (n === null || n === undefined) return "text-muted-foreground";
  if (n >= 75) return "text-success";
  if (n >= 50) return "text-warning";
  return "text-destructive";
}
export function scoreBg(n: number | null | undefined): string {
  if (n === null || n === undefined) return "bg-muted-foreground/40";
  if (n >= 75) return "bg-success";
  if (n >= 50) return "bg-warning";
  return "bg-destructive";
}
