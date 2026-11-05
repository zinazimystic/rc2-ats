"use client";
import * as React from "react";
import { cn } from "@/lib/utils";

/** Lightweight popover (no extra dependency): click-outside + Escape to close, anchored under the trigger. */
export function Popover({
  trigger,
  children,
  open: openProp,
  onOpenChange,
  align = "start",
  className,
}: {
  trigger: (p: { open: boolean; toggle: () => void }) => React.ReactNode;
  children: React.ReactNode | ((p: { close: () => void }) => React.ReactNode);
  open?: boolean;
  onOpenChange?: (o: boolean) => void;
  align?: "start" | "end";
  className?: string;
}) {
  const [inner, setInner] = React.useState(false);
  const open = openProp ?? inner;
  const ref = React.useRef<HTMLDivElement>(null);
  const set = React.useCallback(
    (o: boolean) => {
      setInner(o);
      onOpenChange?.(o);
    },
    [onOpenChange],
  );
  React.useEffect(() => {
    if (!open) return;
    const down = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) set(false);
    };
    const key = (e: KeyboardEvent) => e.key === "Escape" && set(false);
    document.addEventListener("mousedown", down);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("mousedown", down);
      document.removeEventListener("keydown", key);
    };
  }, [open, set]);
  return (
    <div ref={ref} className="relative inline-block">
      {trigger({ open, toggle: () => set(!open) })}
      {open && (
        <div
          role="dialog"
          className={cn(
            "absolute top-full z-40 mt-2 w-[min(26rem,calc(100vw-2rem))] rounded-2xl border bg-popover p-2 text-popover-foreground shadow-xl animate-in fade-in-0 zoom-in-95",
            align === "end" ? "right-0" : "left-0",
            className,
          )}
        >
          {typeof children === "function" ? children({ close: () => set(false) }) : children}
        </div>
      )}
    </div>
  );
}
