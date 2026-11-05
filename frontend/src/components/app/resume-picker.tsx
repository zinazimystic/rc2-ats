"use client";
import { ChevronDown, FileText, Loader2, UploadCloud } from "lucide-react";
import { useMyMatch } from "@/lib/queries";
import { fmtDate } from "@/lib/format";
import type { ResumeOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Popover } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { ResumeStatusChip, isBusy } from "./resume-manager";

export const BAND_LABEL = { strong: "Strong match", good: "Good match", partial: "Partial match", low: "Low match" } as const;
export const bandTone = (b: string | undefined) => (b === "strong" ? "text-success" : b === "good" ? "text-primary" : b === "partial" ? "text-warning" : "text-destructive");

function RowScore({ jobId, resumeId, enabled }: { jobId: string; resumeId: string; enabled: boolean }) {
  const m = useMyMatch(jobId, resumeId, enabled);
  if (!enabled) return null;
  if (m.isPending && !m.data) return <Loader2 className="size-3.5 animate-spin text-muted-foreground" aria-label="Checking fit" />;
  if (!m.data) return <span className="text-[13px] text-muted-foreground">—</span>;
  return <span className={cn("text-sm font-semibold tabular-nums", bandTone(m.data.band))}>{Math.round(m.data.score)}%</span>;
}

/** Choose which parsed resume to use. Fit scores load lazily when the list opens. */
export function ResumePicker({
  jobId, resumes, value, onChange, onUpload, label = "Change",
}: {
  jobId: string; resumes: ResumeOut[]; value: string | null; onChange: (id: string) => void; onUpload?: () => void; label?: string;
}) {
  return (
    <Popover
      trigger={({ open, toggle }) => (
        <Button type="button" size="sm" variant="outline" aria-haspopup="dialog" aria-expanded={open} onClick={toggle}>
          {label} <ChevronDown className={cn("transition-transform", open && "rotate-180")} />
        </Button>
      )}
    >
      {({ close }) => (
        <div role="radiogroup" aria-label="Choose a resume" className="space-y-1">
          <p className="px-2 pt-1 pb-0.5 text-[13px] font-medium tracking-wide text-muted-foreground uppercase">Your resumes</p>
          {resumes.length === 0 && <p className="px-2 py-3 text-sm text-muted-foreground">No resumes yet.</p>}
          {resumes.map((r) => {
            const usable = r.parse_status === "parsed";
            const reason = isBusy(r) ? "Still being read" : r.parse_status === "failed" ? "Couldn’t be read. Re-parse it from your profile." : null;
            const checked = r.id === value;
            return (
              <button
                key={r.id}
                type="button"
                role="radio"
                aria-checked={checked}
                disabled={!usable}
                onClick={() => { onChange(r.id); close(); }}
                className={cn("flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-left transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-transparent", checked && "bg-primary/8")}
              >
                <span className={cn("grid size-4 shrink-0 place-items-center rounded-full border-2", checked ? "border-primary" : "border-input")}>{checked && <span className="size-2 rounded-full bg-primary" />}</span>
                <FileText className="size-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{r.filename}</span>
                  <span className="block truncate text-[13px] text-muted-foreground">{reason ?? `Uploaded ${fmtDate(r.created_at)}`}</span>
                </span>
                {usable ? <RowScore jobId={jobId} resumeId={r.id} enabled /> : <ResumeStatusChip resume={r} />}
              </button>
            );
          })}
          {onUpload && (
            <button type="button" onClick={() => { close(); onUpload(); }} className="flex w-full items-center gap-3 rounded-xl border-t px-2.5 py-2.5 text-left text-sm font-medium text-primary hover:bg-muted">
              <UploadCloud className="size-4" /> Upload a new resume
            </button>
          )}
        </div>
      )}
    </Popover>
  );
}
