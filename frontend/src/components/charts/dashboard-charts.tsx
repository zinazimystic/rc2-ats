"use client";
import { useMemo } from "react";
import type { EChartsCoreOption } from "echarts/core";
import { EChart } from "@/components/charts/echart";
import { useTheme } from "@/components/theme-provider";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { STAGE_COLORS, STAGE_ORDER, chartTheme, horizontalGradient, verticalGradient } from "@/lib/chart-theme";
import { STATUS_LABEL as STAGE_LABELS } from "@/lib/format";

const STATUS_LABEL: Record<string, string> = STAGE_LABELS;
import type { AnalyticsOut } from "@/lib/types";

const reducedMotion = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const base = (animate = !reducedMotion()) => ({ animation: animate, animationDuration: 900, animationEasing: "cubicOut" as const, textStyle: { fontFamily: "inherit" } });

function useChartTheme() {
  const { resolvedTheme } = useTheme();
  return useMemo(() => chartTheme(resolvedTheme === "dark"), [resolvedTheme]);
}

/** 18 -> "18s", 95 -> "1.6 min", 5400 -> "1.5 h" */
export function fmtDuration(seconds: number | null | undefined, unit: "s" | "h" = "s") {
  if (seconds == null) return "—";
  if (unit === "h") return seconds < 1 ? `${Math.round(seconds * 60)} min` : seconds < 48 ? `${seconds.toFixed(1)} h` : `${(seconds / 24).toFixed(1)} d`;
  return seconds < 90 ? `${Math.round(seconds)}s` : seconds < 5400 ? `${(seconds / 60).toFixed(1)} min` : `${(seconds / 3600).toFixed(1)} h`;
}

function Empty({ text }: { text: string }) {
  return <p className="grid h-72 place-items-center text-center text-sm text-muted-foreground">{text}</p>;
}

// ----------------------------------------------------------------------------- hiring funnel
export function FunnelCard({ data }: { data: AnalyticsOut }) {
  const t = useChartTheme();
  const { option, total } = useMemo(() => {
    const counts = Object.fromEntries(data.stage_funnel.map((s) => [s.stage, s.count])) as Record<string, number>;
    // "reached this stage": applications currently at the stage or further along the happy path (rejected ones counted at the top)
    const reached = STAGE_ORDER.map((stage, i) => ({
      stage,
      value: STAGE_ORDER.slice(i).reduce((sum, s) => sum + (counts[s] ?? 0), 0) + (i === 0 ? counts.rejected ?? 0 : 0),
    }));
    const opt: EChartsCoreOption = {
      ...base(),
      tooltip: { ...t.tooltip, trigger: "item", formatter: (p: unknown) => { const x = p as { name: string; value: number; percent: number }; return `<b>${x.name}</b><br/>${x.value} applicants reached this stage`; } },
      series: [{
        type: "funnel", left: "4%", right: "4%", top: 8, bottom: 8, min: 0, sort: "descending", gap: 4,
        label: { show: true, position: "inside", color: "#fff", fontSize: 13, fontWeight: 600, formatter: "{b}  ·  {c}" },
        labelLine: { show: false },
        itemStyle: { borderWidth: 0, borderRadius: 10, shadowBlur: 14, shadowColor: "rgba(47,107,255,0.18)" },
        emphasis: { itemStyle: { shadowBlur: 24 }, label: { fontSize: 14 } },
        data: reached.map((r) => ({ name: STATUS_LABEL[r.stage] ?? r.stage, value: r.value, itemStyle: { color: horizontalGradient(STAGE_COLORS[r.stage], `${STAGE_COLORS[r.stage]}cc`) } })),
      }],
    };
    return { option: opt, total: reached[0].value };
  }, [data.stage_funnel, t]);
  return (
    <Card>
      <CardHeader><CardTitle>Hiring funnel</CardTitle><CardDescription>Applicants who reached each stage</CardDescription></CardHeader>
      <CardContent>{total === 0 ? <Empty text="No applications yet." /> : <EChart option={option} ariaLabel="Hiring funnel by stage" />}</CardContent>
    </Card>
  );
}

// ----------------------------------------------------------------------------- shortlist gauge
export function ShortlistGauge({ data }: { data: AnalyticsOut }) {
  const t = useChartTheme();
  const pct = Math.round((data.shortlist_rate ?? 0) * 100);
  const option = useMemo<EChartsCoreOption>(() => ({
    ...base(),
    series: [{
      type: "gauge", startAngle: 220, endAngle: -40, min: 0, max: 100, radius: "92%", center: ["50%", "58%"],
      progress: { show: true, width: 16, roundCap: true, itemStyle: { color: horizontalGradient("#2f6bff", "#7c5cff") } },
      axisLine: { roundCap: true, lineStyle: { width: 16, color: [[1, t.grid]] } },
      axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false }, pointer: { show: false },
      anchor: { show: false },
      title: { show: true, offsetCenter: [0, "38%"], color: t.subtext, fontSize: 13 },
      detail: { valueAnimation: true, offsetCenter: [0, "-4%"], fontSize: 40, fontWeight: 700, color: t.text, formatter: "{value}%" },
      data: [{ value: pct, name: "Shortlist rate" }],
    }],
  }), [pct, t]);
  return (
    <Card>
      <CardHeader><CardTitle>Shortlist rate</CardTitle><CardDescription>Share of applicants moved past review</CardDescription></CardHeader>
      <CardContent>
        <EChart option={option} ariaLabel={`Shortlist rate ${pct} percent`} className="h-56" />
        <dl className="mt-2 grid grid-cols-2 gap-3 text-center">
          <div className="rounded-2xl bg-muted/60 p-3"><dt className="text-[13px] text-muted-foreground">AI processing</dt><dd className="text-lg font-semibold tabular-nums">{fmtDuration(data.avg_processing_seconds)}</dd></div>
          <div className="rounded-2xl bg-muted/60 p-3"><dt className="text-[13px] text-muted-foreground">Time to decision</dt><dd className="text-lg font-semibold tabular-nums">{fmtDuration(data.avg_time_to_decision_hours, "h")}</dd></div>
        </dl>
      </CardContent>
    </Card>
  );
}

// ----------------------------------------------------------------------------- score distribution
export function ScoreCard({ data }: { data: AnalyticsOut }) {
  const t = useChartTheme();
  const total = data.score_distribution.reduce((a, b) => a + b.count, 0);
  const option = useMemo<EChartsCoreOption>(() => ({
    ...base(),
    grid: { left: 8, right: 12, top: 28, bottom: 4, containLabel: true },
    tooltip: { ...t.tooltip, trigger: "axis", axisPointer: { type: "shadow", shadowStyle: { color: "rgba(47,107,255,0.06)" } } },
    xAxis: { type: "category", data: data.score_distribution.map((b) => b.bucket), axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: t.subtext, fontSize: 12, margin: 12 } },
    yAxis: { type: "value", minInterval: 1, splitLine: { lineStyle: { color: t.grid, type: "dashed" } }, axisLabel: { color: t.subtext, fontSize: 12 } },
    series: [
      {
        name: "Applicants", type: "bar", barWidth: "34%", itemStyle: { borderRadius: [12, 12, 4, 4], color: verticalGradient("#2f6bff", "#7c5cff") },
        emphasis: { itemStyle: { color: verticalGradient("#4d83ff", "#9a82ff") } },
        label: { show: true, position: "top", color: t.subtext, fontSize: 12, formatter: (p: unknown) => ((p as { value: number }).value ? String((p as { value: number }).value) : "") },
        data: data.score_distribution.map((b) => b.count),
      },
    ],
  }), [data.score_distribution, t]);
  return (
    <Card>
      <CardHeader><CardTitle>AI score distribution</CardTitle><CardDescription>How applicants score against the requirements</CardDescription></CardHeader>
      <CardContent>{total === 0 ? <Empty text="Scores appear once resumes are assessed." /> : <EChart option={option} ariaLabel="Distribution of AI scores" />}</CardContent>
    </Card>
  );
}

// ----------------------------------------------------------------------------- skill gaps (radar, or bars when there are few)
export function GapsCard({ data }: { data: AnalyticsOut }) {
  const t = useChartTheme();
  const gaps = data.top_skill_gaps.slice(0, 7);
  const option = useMemo<EChartsCoreOption>(() => gaps.length >= 3
    ? {
        ...base(),
        tooltip: { ...t.tooltip, trigger: "item" },
        radar: {
          radius: "56%", center: ["50%", "52%"], splitNumber: 4, shape: "polygon",
          axisName: { color: t.text, fontSize: 12, fontWeight: 500 },
          indicator: gaps.map((g) => ({ name: g.skill, max: 100 })),
          splitLine: { lineStyle: { color: t.grid } }, axisLine: { lineStyle: { color: t.grid } },
          splitArea: { areaStyle: { color: ["transparent"] } },
        },
        series: [{
          type: "radar", symbol: "circle", symbolSize: 7,
          lineStyle: { width: 2.5, color: "#ef4444" }, itemStyle: { color: "#ef4444", borderColor: t.surface, borderWidth: 2 },
          areaStyle: { color: "rgba(239,68,68,0.2)" },
          data: [{ name: "Applicants lacking evidence (%)", value: gaps.map((g) => Math.round(g.percent)) }],
        }],
      }
    : {
        ...base(),
        grid: { left: 4, right: 24, top: 8, bottom: 4, containLabel: true },
        tooltip: { ...t.tooltip, trigger: "item", formatter: (p: unknown) => { const x = p as { name: string; value: number }; return `<b>${x.name}</b><br/>${x.value}% of applicants lack evidence`; } },
        xAxis: { type: "value", max: 100, splitLine: { lineStyle: { color: t.grid, type: "dashed" } }, axisLabel: { color: t.subtext, formatter: "{value}%" } },
        yAxis: { type: "category", inverse: true, data: gaps.map((g) => g.skill), axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: t.text, fontSize: 13 } },
        series: [{
          type: "bar", barWidth: 16, itemStyle: { borderRadius: 10, color: horizontalGradient("#f97316", "#ef4444") },
          label: { show: true, position: "right", color: t.subtext, formatter: "{c}%" }, data: gaps.map((g) => Math.round(g.percent)),
        }],
      }, [gaps, t]);
  return (
    <Card>
      <CardHeader><CardTitle>Top skill gaps</CardTitle><CardDescription>Required skills most often lacking evidence</CardDescription></CardHeader>
      <CardContent>
        {gaps.length === 0 ? <Empty text="No gaps detected yet." /> : (
          <div className="grid gap-4 md:grid-cols-[1fr_190px] md:items-center">
            <EChart option={option} ariaLabel="Skills most often missing from applicants" />
            <ul className="space-y-2 text-sm">
              {gaps.slice(0, 5).map((g) => (
                <li key={g.skill} className="flex items-center justify-between gap-3 rounded-xl bg-muted/60 px-3 py-2">
                  <span className="truncate font-medium">{g.skill}</span><span className="shrink-0 tabular-nums text-muted-foreground">{g.count} · {g.percent.toFixed(0)}%</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ----------------------------------------------------------------------------- jobs -> stages sankey
export function JobFlowCard({ data }: { data: AnalyticsOut }) {
  const t = useChartTheme();
  const jobs = data.applications_by_job.filter((j) => j.total > 0);
  const option = useMemo<EChartsCoreOption>(() => {
    const stages = [...STAGE_ORDER, "rejected", "withdrawn"] as string[];
    const used = stages.filter((s) => jobs.some((j) => (j.by_stage[s] ?? 0) > 0));
    return {
      ...base(),
      tooltip: { ...t.tooltip, trigger: "item" },
      series: [{
        type: "sankey", left: 8, right: 170, top: 8, bottom: 8, nodeWidth: 16, nodeGap: 14, draggable: false, emphasis: { focus: "adjacency" },
        lineStyle: { color: "gradient", curveness: 0.5, opacity: 0.38 },
        label: { color: t.text, fontSize: 12 },
        data: [
          ...jobs.map((j, i) => ({ name: j.title, itemStyle: { color: t.palette[i % t.palette.length], borderRadius: 4 } })),
          ...used.map((s) => ({ name: STATUS_LABEL[s] ?? s, itemStyle: { color: STAGE_COLORS[s], borderRadius: 4 } })),
        ],
        links: jobs.flatMap((j) => used.filter((s) => (j.by_stage[s] ?? 0) > 0).map((s) => ({ source: j.title, target: STATUS_LABEL[s] ?? s, value: j.by_stage[s] }))),
      }],
    };
  }, [jobs, t]);
  if (jobs.length === 0) return null;
  return (
    <Card>
      <CardHeader><CardTitle>Where applicants are, by job</CardTitle><CardDescription>Flow from each job into its current pipeline stage</CardDescription></CardHeader>
      <CardContent><EChart option={option} ariaLabel="Applicants per job and stage" className={jobs.length > 5 ? "h-[28rem]" : "h-72"} /></CardContent>
    </Card>
  );
}
