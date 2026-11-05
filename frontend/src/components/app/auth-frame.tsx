import Link from "next/link";
import { CheckCircle2, Sparkles } from "lucide-react";
import { Wave } from "@/components/app/landing-art";

export function AuthFrame({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <div className="hero-gradient relative hidden flex-col justify-between overflow-hidden p-12 text-white lg:flex">
        <div className="absolute -right-24 -bottom-24 size-96 rounded-full bg-white/10 blur-3xl" aria-hidden />
        <Link href="/" className="relative flex items-center gap-2.5 font-semibold">
          <span className="grid size-9 place-items-center rounded-xl bg-white/15"><Sparkles className="size-[18px]" /></span>
          RC3 Talent Intelligence
        </Link>
        <div className="relative space-y-5">
          <h2 className="text-4xl leading-tight font-bold tracking-tight">Hiring decisions backed by evidence, not guesswork.</h2>
          <ul className="space-y-3 text-white/80">
            {["Every score is tied to verbatim resume quotes", "Deterministic, explainable, fairness-checked ranking", "From resume upload to interview scheduling in one place"].map((t) => (
              <li key={t} className="flex items-start gap-2.5"><CheckCircle2 className="mt-0.5 size-5 shrink-0 text-coral" />{t}</li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-white/60">AI extracts evidence, deterministic code scores it.</p>
        <Wave className="absolute inset-x-0 bottom-0 h-16 w-full opacity-10" fill="#fff" />
      </div>
      <div className="flex items-center justify-center bg-cream p-6 dark:bg-background">
        <div className="w-full max-w-sm space-y-6 rounded-3xl bg-card p-8 shadow-soft">
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
