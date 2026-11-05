import * as React from "react";
import { cn } from "@/lib/utils";

const field =
  "w-full rounded-md border border-input bg-card px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive";

export const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(function Input(
  { className, type = "text", ...p },
  ref,
) {
  return <input ref={ref} type={type} className={cn(field, "h-9 py-1", className)} {...p} />;
});
export const Textarea = React.forwardRef<HTMLTextAreaElement, React.ComponentProps<"textarea">>(function Textarea(
  { className, ...p },
  ref,
) {
  return <textarea ref={ref} className={cn(field, "min-h-20 py-2", className)} {...p} />;
});
export const Select = React.forwardRef<HTMLSelectElement, React.ComponentProps<"select">>(function Select(
  { className, ...p },
  ref,
) {
  return <select ref={ref} className={cn(field, "h-9 py-1 pr-8", className)} {...p} />;
});
export function Label({ className, ...p }: React.ComponentProps<"label">) {
  return <label className={cn("text-sm leading-none font-medium", className)} {...p} />;
}
export function Field({
  label,
  error,
  hint,
  children,
  className,
  htmlFor,
}: {
  label: string;
  error?: string;
  hint?: string;
  children: React.ReactNode;
  className?: string;
  htmlFor?: string;
}) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && !error && <p className="text-xs text-muted-foreground">{hint}</p>}
      {error && (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
export const Checkbox = React.forwardRef<HTMLInputElement, Omit<React.ComponentProps<"input">, "type">>(
  function Checkbox({ className, ...p }, ref) {
    return <input ref={ref} type="checkbox" className={cn("size-4 rounded border-input accent-[var(--primary)]", className)} {...p} />;
  },
);
