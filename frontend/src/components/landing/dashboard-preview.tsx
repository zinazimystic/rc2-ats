import { Bell, BriefcaseBusiness, CalendarDays, CopyCheck, LayoutDashboard, Search } from "lucide-react";
import { LogoMark } from "@/components/app/logo";

/** Illustrative product preview built from JSX/SVG (sample figures, not real data). */
export function Ring({ value, size = 34, color = "#4f46e5" }: { value: number; size?: number; color?: string }) {
  const r = (size - 6) / 2;
  const c = 2 * Math.PI * r;
  return (
    <span className="relative inline-grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e8e8f5" strokeWidth="4" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="4" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - value / 100)} />
      </svg>
      <span className="absolute text-[10px] font-semibold text-slate-700 tabular-nums">{value}</span>
    </span>
  );
}

const STATS = [
  { l: "Open jobs", v: "12", d: "+2 this week" },
  { l: "Applicants", v: "348", d: "+18%" },
  { l: "Shortlisted", v: "46", d: "13% rate" },
  { l: "Interviews", v: "21", d: "6 this week" },
];
const ROWS = [
  { n: "Amina Rahman", r: "Senior Backend Engineer", s: 92, c: "#16a34a", st: "Shortlisted", g: "from-indigo-400 to-violet-500" },
  { n: "Daniel Okoye", r: "Data Analyst", s: 84, c: "#4f46e5", st: "Interview", g: "from-sky-400 to-indigo-500" },
  { n: "Mei Tanaka", r: "Product Designer", s: 77, c: "#4f46e5", st: "In review", g: "from-fuchsia-400 to-violet-500" },
  { n: "Lucas Ferreira", r: "Frontend Engineer", s: 61, c: "#d97706", st: "In review", g: "from-emerald-400 to-teal-500" },
];
const NAV = [
  [LayoutDashboard, "Dashboard", true],
  [BriefcaseBusiness, "Jobs", false],
  [CalendarDays, "Interviews", false],
  [Search, "Talent search", false],
  [CopyCheck, "Duplicates", false],
  [Bell, "Notifications", false],
] as const;

export function DashboardPreview() {
  return (
    <div aria-hidden className="select-none overflow-hidden rounded-2xl border border-white/20 bg-slate-50 text-left text-slate-800 shadow-[0_40px_90px_-20px_rgb(15_10_80/55%)] ring-1 ring-black/5">
      <div className="flex h-8 items-center gap-1.5 border-b border-slate-200 bg-white px-3">
        <span className="size-2.5 rounded-full bg-slate-200" />
        <span className="size-2.5 rounded-full bg-slate-200" />
        <span className="size-2.5 rounded-full bg-slate-200" />
        <span className="mx-auto h-4 w-56 max-w-[50%] rounded-full bg-slate-100" />
      </div>
      <div className="grid sm:grid-cols-[168px_1fr]">
        <aside className="hidden flex-col gap-1 border-r border-slate-200 bg-white p-3 sm:flex">
          <div className="mb-3 flex items-center gap-2 px-1.5">
            <LogoMark size={22} />
            <span className="text-[13px] font-semibold tracking-tight"><span className="text-[#4f46e5]">RC3</span> Talent</span>
          </div>
          {NAV.map(([Icon, l, a]) => (
            <span key={l} className={`flex items-center gap-2 rounded-full px-3 py-1.5 text-[12px] font-medium ${a ? "bg-[#4f46e5] text-white" : "text-slate-500"}`}>
              <Icon className="size-3.5" />
              {l}
            </span>
          ))}
          <div className="mt-6 rounded-xl bg-slate-50 p-2.5">
            <div className="h-1.5 w-16 rounded-full bg-slate-200" />
            <div className="mt-2 h-1.5 w-full rounded-full bg-slate-200"><div className="h-full w-2/3 rounded-full bg-[#4f46e5]" /></div>
          </div>
        </aside>
        <div className="space-y-3 p-4 sm:p-5">
          <div className="flex items-center justify-between">
            <span className="text-[15px] font-semibold">Dashboard</span>
            <span className="rounded-full bg-[#4f46e5] px-3 py-1 text-[11px] font-medium text-white">+ New job</span>
          </div>
          <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
            {STATS.map((s, i) => (
              <div key={s.l} className={`rounded-xl border p-3 ${i === 0 ? "border-transparent bg-[#4f46e5] text-white" : "border-slate-200 bg-white"}`}>
                <p className={`text-[11px] ${i === 0 ? "text-white/70" : "text-slate-500"}`}>{s.l}</p>
                <p className="mt-1 text-[26px] leading-none font-semibold tracking-tight tabular-nums">{s.v}</p>
                <p className={`mt-1.5 text-[11px] ${i === 0 ? "text-white/70" : "text-emerald-600"}`}>{s.d}</p>
              </div>
            ))}
          </div>
          <div className="grid gap-2.5 lg:grid-cols-[1.35fr_1fr]">
            <div className="rounded-xl border border-slate-200 bg-white p-3">
              <p className="text-[12px] font-semibold">Hiring pipeline</p>
              <svg viewBox="0 0 400 150" className="mt-1 w-full" role="presentation">
                <defs>
                  <linearGradient id="sk1" x1="0" x2="1"><stop offset="0" stopColor="#6366f1" stopOpacity=".85" /><stop offset="1" stopColor="#8b5cf6" stopOpacity=".55" /></linearGradient>
                  <linearGradient id="sk2" x1="0" x2="1"><stop offset="0" stopColor="#8b5cf6" stopOpacity=".6" /><stop offset="1" stopColor="#c4b5fd" stopOpacity=".4" /></linearGradient>
                  <linearGradient id="sk3" x1="0" x2="1"><stop offset="0" stopColor="#a5b4fc" stopOpacity=".7" /><stop offset="1" stopColor="#e0e7ff" stopOpacity=".5" /></linearGradient>
                </defs>
                <path d="M30 10 C 130 10, 130 20, 230 24 L 230 86 C 130 78, 130 82, 30 80 Z" fill="url(#sk1)" />
                <path d="M30 86 C 130 90, 130 100, 230 96 L 230 124 C 130 124, 130 122, 30 120 Z" fill="url(#sk2)" />
                <path d="M30 126 C 130 128, 130 136, 230 130 L 230 140 C 130 142, 130 144, 30 144 Z" fill="url(#sk3)" />
                <path d="M230 24 C 300 28, 300 30, 372 34 L 372 62 C 300 60, 300 62, 230 62 Z" fill="url(#sk1)" opacity=".9" />
                <path d="M230 70 C 300 72, 300 80, 372 80 L 372 98 C 300 98, 300 96, 230 90 Z" fill="url(#sk2)" />
                <rect x="26" y="8" width="5" height="138" rx="2.5" fill="#4f46e5" />
                <rect x="228" y="22" width="5" height="120" rx="2.5" fill="#4f46e5" />
                <rect x="370" y="32" width="5" height="68" rx="2.5" fill="#4f46e5" />
                <g fontSize="9" fill="#64748b"><text x="30" y="4">Applied 348</text><text x="236" y="18">Screened 190</text><text x="300" y="112">Shortlisted 46</text></g>
              </svg>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-3">
              <p className="text-[12px] font-semibold">Score distribution</p>
              <svg viewBox="0 0 220 150" className="mt-1 w-full" role="presentation">
                <defs><linearGradient id="ar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#6366f1" stopOpacity=".45" /><stop offset="1" stopColor="#6366f1" stopOpacity="0" /></linearGradient></defs>
                {[30, 70, 110].map((y) => <line key={y} x1="0" x2="220" y1={y} y2={y} stroke="#eef0f6" />)}
                <path d="M0 120 C30 110, 45 70, 80 62 S130 30, 160 56 S205 100, 220 112 L220 140 L0 140 Z" fill="url(#ar)" />
                <path d="M0 120 C30 110, 45 70, 80 62 S130 30, 160 56 S205 100, 220 112" fill="none" stroke="#4f46e5" strokeWidth="2.5" strokeLinecap="round" />
                <circle cx="130" cy="42" r="4" fill="#fff" stroke="#4f46e5" strokeWidth="2.5" />
              </svg>
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white">
            <p className="px-3 pt-3 pb-1.5 text-[12px] font-semibold">Top applicants</p>
            {ROWS.map((r) => (
              <div key={r.n} className="grid grid-cols-[1fr_auto] items-center gap-3 border-t border-slate-100 px-3 py-2 sm:grid-cols-[1.4fr_1.2fr_auto_auto]">
                <span className="flex items-center gap-2"><span className={`size-6 rounded-full bg-gradient-to-br ${r.g}`} /><span className="text-[12px] font-medium">{r.n}</span></span>
                <span className="hidden text-[12px] text-slate-500 sm:block">{r.r}</span>
                <span className="hidden rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600 sm:block">{r.st}</span>
                <Ring value={r.s} color={r.c} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
