import Link from "next/link";
import { BadgeCheck, CalendarClock, LineChart, Quote, Scale, Sparkles, UploadCloud } from "lucide-react";
import { Button } from "@/components/ui/button";
import { HeroArt, Wave } from "@/components/app/landing-art";

const FEATURES = [
  { icon: <UploadCloud />, title: "Upload a resume", text: "Drop a PDF or DOCX. We parse it into structured, verifiable data in seconds.", label: "Match Resume" },
  { icon: <LineChart />, title: "Evidence-first scoring", text: "Every score is tied to verbatim resume quotes, so you can audit each decision.", label: "Dashboard" },
  { icon: <Scale />, title: "Fairness checked", text: "Deterministic, explainable ranking with built-in counterfactual fairness tests.", label: "Fair Ranking" },
  { icon: <CalendarClock />, title: "Interviews in one place", text: "Shortlist, schedule, collect feedback and send offers without leaving the app.", label: "Schedule" },
];

export function Landing() {
  return (
    <div className="min-h-screen bg-cream text-slate-800">
      <section className="hero-gradient relative overflow-hidden text-white">
        <div className="absolute -top-24 -right-24 size-96 rounded-full bg-white/10 blur-3xl" aria-hidden />
        <header className="relative mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
          <span className="flex items-center gap-2.5 font-semibold tracking-tight"><span className="grid size-9 place-items-center rounded-xl bg-white/15"><Sparkles className="size-[18px]" /></span>RC3 Talent</span>
          <nav className="flex items-center gap-6 text-sm text-white/85" aria-label="Site">
            <a href="#why" className="hidden hover:text-white sm:inline">Features</a>
            <a href="#clients" className="hidden hover:text-white sm:inline">Clients</a>
            <Link href="/login" className="hover:text-white">Sign in</Link>
          </nav>
        </header>
        <div className="relative mx-auto grid max-w-6xl items-center gap-8 px-6 pt-8 pb-40 md:grid-cols-2 md:pt-16">
          <div>
            <h1 className="text-4xl leading-tight font-bold tracking-tight sm:text-5xl">Boost your hiring with evidence, not guesswork.</h1>
            <p className="mt-5 max-w-md text-white/80"><strong className="text-white">RC3</strong> compares resumes to your job requirements, shows exactly which quotes back each score, and takes you from application to interview in one place.</p>
            <div className="mt-8 flex flex-wrap items-center gap-5">
              <Button asChild variant="coral" size="lg"><Link href="/register">Let&apos;s Start</Link></Button>
              <Link href="/login" className="text-sm text-white/85 underline-offset-4 hover:underline">I already have an account</Link>
            </div>
          </div>
          <HeroArt />
        </div>
        <Wave className="absolute inset-x-0 bottom-0 h-28 w-full" />
      </section>

      <section id="why" className="mx-auto max-w-6xl px-6 py-16">
        <div className="flex items-center gap-5">
          <span className="h-1 w-24 rounded-full bg-coral" aria-hidden />
          <h2 className="text-2xl font-semibold text-violet-1 sm:text-3xl">why use RC3?</h2>
        </div>
        <p className="mt-4 max-w-xl text-slate-600">Hiring decisions you can explain. AI extracts the evidence; deterministic code scores it, so recruiters and candidates both see the same story.</p>
        <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((f) => (
            <article key={f.title} className="flex flex-col overflow-hidden rounded-2xl bg-white shadow-soft transition-transform hover:-translate-y-1">
              <div className="flex-1 space-y-3 p-6">
                <span className="grid size-11 place-items-center rounded-xl bg-violet-2/10 text-violet-2 [&_svg]:size-6">{f.icon}</span>
                <h3 className="font-semibold text-violet-1">{f.title}</h3>
                <p className="text-sm text-slate-600">{f.text}</p>
              </div>
              <span className="bg-violet-2 py-2 text-center text-xs font-medium text-white">{f.label}</span>
            </article>
          ))}
        </div>
      </section>

      <section id="clients" className="mx-auto max-w-6xl px-6 pb-20">
        <div className="flex items-center justify-end gap-5">
          <h2 className="text-2xl font-semibold text-violet-1 sm:text-3xl">our happy clients</h2>
          <span className="h-1 w-24 rounded-full bg-coral" aria-hidden />
        </div>
        <figure className="mx-auto mt-10 flex max-w-xl items-center gap-6 rounded-3xl bg-white p-8 shadow-soft">
          <span className="grid size-20 shrink-0 place-items-center rounded-full bg-gradient-to-br from-violet-2 to-primary text-2xl font-bold text-white">JM</span>
          <div>
            <Quote className="size-5 text-coral" />
            <blockquote className="mt-2 text-sm text-slate-600">Every score pointed to a quote in the resume. We stopped arguing about gut feel and started discussing evidence.</blockquote>
            <figcaption className="mt-3 flex items-center gap-1.5 text-sm font-semibold text-violet-1"><BadgeCheck className="size-4" /> John May, Head of Talent</figcaption>
            <div className="mt-3 flex gap-1.5" aria-hidden>{[0, 1, 2, 3, 4].map((i) => <span key={i} className={i === 0 ? "size-2 rounded-full bg-violet-2" : "size-2 rounded-full bg-slate-200"} />)}</div>
          </div>
        </figure>
      </section>

      <footer className="hero-gradient text-white">
        <div className="mx-auto grid max-w-6xl gap-8 px-6 py-12 sm:grid-cols-4">
          <div><span className="flex items-center gap-2 font-semibold"><Sparkles className="size-5" /> RC3 Talent</span><p className="mt-3 text-sm text-white/70">Talent intelligence you can audit.</p></div>
          <FooterCol title="About" links={["Team", "Support", "Career", "Company"]} />
          <FooterCol title="Help" links={["FAQs", "Return Policy", "Terms and Conditions"]} />
          <div><p className="font-semibold">Find us on social media</p><div className="mt-3 flex gap-2">{["in", "X", "f"].map((s) => <span key={s} className="grid size-8 place-items-center rounded-md bg-white/15 text-xs font-bold">{s}</span>)}</div></div>
        </div>
      </footer>
    </div>
  );
}

function FooterCol({ title, links }: { title: string; links: string[] }) {
  return (
    <div>
      <p className="font-semibold">{title}</p>
      <ul className="mt-3 space-y-1.5 text-sm text-white/70">{links.map((l) => <li key={l}>{l}</li>)}</ul>
    </div>
  );
}
