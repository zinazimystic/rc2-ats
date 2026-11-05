import { Sparkles } from "lucide-react";

export function AuthFrame({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between bg-sidebar p-10 text-white lg:flex">
        <div className="flex items-center gap-2 font-semibold">
          <span className="grid size-8 place-items-center rounded-md bg-primary text-primary-foreground"><Sparkles className="size-4" /></span>
          RC3 Talent Intelligence
        </div>
        <div className="space-y-4">
          <h2 className="text-3xl leading-tight font-semibold">Hiring decisions backed by evidence, not guesswork.</h2>
          <ul className="space-y-2 text-white/70">
            <li>• Every score is tied to verbatim resume quotes</li>
            <li>• Deterministic, explainable, fairness-checked ranking</li>
            <li>• From resume upload to interview scheduling in one place</li>
          </ul>
        </div>
        <p className="text-xs text-white/50">AI extracts evidence — deterministic code scores it.</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm space-y-6">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
            <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}
