import { CheckCircle2 } from "lucide-react";
import { Logo } from "@/components/app/logo";

export function AuthFrame({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <div className="hero-deep relative hidden flex-col justify-between overflow-hidden p-12 text-white lg:flex">
        <div className="grid-texture absolute inset-0" aria-hidden />
        <Logo href="/" onDark size={34} className="relative" />
        <div className="relative space-y-6">
          <h2 className="max-w-md text-4xl leading-tight font-semibold tracking-tight">Hire on evidence, not guesswork.</h2>
          <ul className="space-y-3 text-[15px] text-white/80">
            {["Every score is tied to verbatim resume quotes", "Deterministic, explainable, fairness-checked ranking", "From resume upload to interview scheduling in one place"].map((t) => (
              <li key={t} className="flex items-start gap-2.5"><CheckCircle2 className="mt-0.5 size-5 shrink-0 text-[#a5a4ff]" />{t}</li>
            ))}
          </ul>
        </div>
        <p className="relative text-[13px] text-white/60">AI extracts the evidence. Deterministic code scores it.</p>
      </div>
      <main id="main" className="flex items-center justify-center bg-background p-6">
        <div className="w-full max-w-sm space-y-6 rounded-3xl border border-border/60 bg-card p-8 shadow-soft">
          <Logo href="/" size={30} className="lg:hidden" />
          <div>
            <h1 className="text-[28px] leading-tight font-semibold tracking-tight">{title}</h1>
            <p className="mt-1.5 text-[15px] text-muted-foreground">{subtitle}</p>
          </div>
          {children}
        </div>
      </main>
    </div>
  );
}
