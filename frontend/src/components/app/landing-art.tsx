import { CheckCircle2, Search } from "lucide-react";

/** Decorative hero illustration built from CSS/SVG shapes. */
export function HeroArt() {
  return (
    <div className="relative mx-auto h-[340px] w-full max-w-[520px]" aria-hidden>
      <div className="absolute inset-x-6 top-10 h-60 rounded-[2rem] bg-white/10 blur-2xl" />
      <div className="float-slow absolute top-6 left-6 w-60 -rotate-6 rounded-2xl bg-white p-4 shadow-2xl shadow-black/30">
        <div className="flex items-center gap-3">
          <span className="size-10 rounded-full bg-gradient-to-br from-violet-2 to-primary" />
          <div className="space-y-1.5"><div className="h-2.5 w-24 rounded-full bg-violet-1/80" /><div className="h-2 w-16 rounded-full bg-slate-200" /></div>
        </div>
        <div className="mt-4 space-y-2">
          {[90, 75, 82, 60].map((w, i) => <div key={i} className="h-2 rounded-full bg-slate-200" style={{ width: `${w}%` }} />)}
        </div>
        <div className="mt-4 flex gap-1.5">
          {["React", "SQL", "AWS"].map((t) => <span key={t} className="rounded-full bg-violet-2/15 px-2 py-0.5 text-[10px] font-semibold text-violet-2">{t}</span>)}
        </div>
      </div>
      <div className="float-slow absolute top-20 right-4 w-56 rotate-3 rounded-2xl bg-white/95 p-4 shadow-2xl shadow-black/30 [animation-delay:1.2s]">
        <p className="text-[11px] font-semibold tracking-wide text-slate-400 uppercase">Match score</p>
        <div className="mt-2 flex items-center gap-3">
          <svg width="64" height="64" viewBox="0 0 64 64" className="-rotate-90">
            <circle cx="32" cy="32" r="26" fill="none" stroke="#e8e4f7" strokeWidth="8" />
            <circle cx="32" cy="32" r="26" fill="none" stroke="#7d46e6" strokeWidth="8" strokeLinecap="round" strokeDasharray="163" strokeDashoffset="26" />
          </svg>
          <div><p className="text-2xl font-bold text-violet-1">84%</p><p className="text-[11px] text-slate-500">Evidence-backed</p></div>
        </div>
        <p className="mt-3 flex items-center gap-1.5 text-[11px] text-emerald-600"><CheckCircle2 className="size-3.5" /> 7 of 8 requirements verified</p>
      </div>
      <div className="float-slow absolute right-24 bottom-6 grid size-20 place-items-center rounded-full bg-coral shadow-xl shadow-black/30 [animation-delay:2.4s]">
        <Search className="size-9 text-white" />
      </div>
    </div>
  );
}

export function Wave({ className, fill = "var(--cream)" }: { className?: string; fill?: string }) {
  return (
    <svg viewBox="0 0 1440 120" preserveAspectRatio="none" className={className} aria-hidden>
      <path fill={fill} d="M0,64 C240,120 480,0 720,40 C960,80 1200,120 1440,50 L1440,120 L0,120 Z" />
    </svg>
  );
}
