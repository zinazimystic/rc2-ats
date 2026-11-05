"use client";
import { useEffect, useRef, useState } from "react";
import type { ECharts, EChartsCoreOption } from "echarts/core";
import { cn } from "@/lib/utils";

/** Thin wrapper around Apache ECharts: lazy-loads the library, resizes with its container, disposes on unmount. */
export function EChart({ option, className, ariaLabel }: { option: EChartsCoreOption; className?: string; ariaLabel: string }) {
  const host = useRef<HTMLDivElement>(null);
  const chart = useRef<ECharts | null>(null);
  const latest = useRef(option);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    latest.current = option;
    chart.current?.setOption(option, { replaceMerge: ["series"] });
  }, [option]);

  useEffect(() => {
    let disposed = false;
    let observer: ResizeObserver | undefined;
    import("@/lib/echarts").then(({ echarts }) => {
      if (disposed || !host.current) return;
      const instance = echarts.init(host.current, undefined, { renderer: "canvas" });
      chart.current = instance;
      instance.setOption(latest.current);
      observer = new ResizeObserver(() => instance.resize());
      observer.observe(host.current);
      setReady(true);
    });
    return () => {
      disposed = true;
      observer?.disconnect();
      chart.current?.dispose();
      chart.current = null;
    };
  }, []);

  return (
    <div className={cn("relative h-72 w-full", className)}>
      {!ready && <div aria-hidden className="skeleton absolute inset-0 rounded-2xl" />}
      <div ref={host} role="img" aria-label={ariaLabel} className={cn("h-full w-full transition-opacity duration-500", ready ? "opacity-100" : "opacity-0")} />
    </div>
  );
}
