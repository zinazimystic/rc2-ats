"use client";
import * as React from "react";
import { cn } from "@/lib/utils";

/** Six-box one-time-code entry with auto-advance, backspace and paste support. */
export function OtpInput({ value, onChange, length = 6, disabled, invalid }: { value: string; onChange: (v: string) => void; length?: number; disabled?: boolean; invalid?: boolean }) {
  const refs = React.useRef<(HTMLInputElement | null)[]>([]);
  const chars = Array.from({ length }, (_, i) => value[i] ?? "");
  const set = (i: number, c: string) => {
    const next = chars.slice();
    next[i] = c;
    onChange(next.join("").slice(0, length));
  };
  return (
    <div className="flex justify-center gap-2" role="group" aria-label="6-digit verification code">
      {chars.map((c, i) => (
        <input
          key={i}
          ref={(el) => {
            refs.current[i] = el;
          }}
          inputMode="numeric"
          autoComplete={i === 0 ? "one-time-code" : "off"}
          maxLength={1}
          disabled={disabled}
          aria-label={`Digit ${i + 1}`}
          aria-invalid={invalid || undefined}
          value={c}
          className={cn(
            "size-12 rounded-xl border bg-card text-center text-xl font-semibold tabular-nums shadow-xs transition-colors focus-visible:border-primary disabled:opacity-50",
            invalid && "border-destructive",
          )}
          onChange={(e) => {
            const d = e.target.value.replace(/\D/g, "").slice(-1);
            set(i, d);
            if (d && i < length - 1) refs.current[i + 1]?.focus();
          }}
          onKeyDown={(e) => {
            if (e.key === "Backspace" && !chars[i] && i > 0) refs.current[i - 1]?.focus();
            if (e.key === "ArrowLeft" && i > 0) refs.current[i - 1]?.focus();
            if (e.key === "ArrowRight" && i < length - 1) refs.current[i + 1]?.focus();
          }}
          onPaste={(e) => {
            const t = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, length);
            if (!t) return;
            e.preventDefault();
            onChange(t);
            refs.current[Math.min(t.length, length - 1)]?.focus();
          }}
        />
      ))}
    </div>
  );
}
