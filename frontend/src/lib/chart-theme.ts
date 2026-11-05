// Colours for canvas charts (canvas cannot read CSS variables), in sync with the app's blue/violet palette.
export type ChartTheme = {
  dark: boolean;
  text: string;
  subtext: string;
  grid: string;
  surface: string;
  palette: string[];
  tooltip: { backgroundColor: string; borderColor: string; borderWidth: number; padding: number; textStyle: { color: string; fontSize: number }; extraCssText: string };
};

const PALETTE = ["#2f6bff", "#7c5cff", "#14b8a6", "#f59e0b", "#ec4899", "#38bdf8", "#84cc16", "#f97316"];

export function chartTheme(dark: boolean): ChartTheme {
  const text = dark ? "#e5e9f5" : "#0f172a";
  return {
    dark,
    text,
    subtext: dark ? "#94a3b8" : "#64748b",
    grid: dark ? "rgba(148,163,184,0.16)" : "rgba(100,116,139,0.16)",
    surface: dark ? "#161a26" : "#ffffff",
    palette: PALETTE,
    tooltip: {
      backgroundColor: dark ? "#1c2233" : "#ffffff",
      borderColor: dark ? "rgba(148,163,184,0.25)" : "rgba(100,116,139,0.2)",
      borderWidth: 1,
      padding: 12,
      textStyle: { color: text, fontSize: 13 },
      extraCssText: "border-radius:14px;box-shadow:0 12px 32px rgba(15,23,42,0.18);",
    },
  };
}

export const STAGE_ORDER = ["submitted", "parsed", "ai_assessed", "recruiter_review", "shortlisted", "interview", "selected"] as const;

export const STAGE_COLORS: Record<string, string> = {
  submitted: "#94a3b8",
  parsed: "#38bdf8",
  ai_assessed: "#2f6bff",
  recruiter_review: "#7c5cff",
  shortlisted: "#14b8a6",
  interview: "#f59e0b",
  selected: "#22c55e",
  rejected: "#ef4444",
  withdrawn: "#cbd5e1",
};

export const verticalGradient = (top: string, bottom: string) => ({
  type: "linear" as const, x: 0, y: 0, x2: 0, y2: 1,
  colorStops: [{ offset: 0, color: top }, { offset: 1, color: bottom }],
});

export const horizontalGradient = (left: string, right: string) => ({
  type: "linear" as const, x: 0, y: 0, x2: 1, y2: 0,
  colorStops: [{ offset: 0, color: left }, { offset: 1, color: right }],
});
