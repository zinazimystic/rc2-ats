import Link from "next/link";
import { ArrowRight, BadgeCheck, CalendarClock, CheckCircle2, ChevronDown, Eye, FileSearch, Layers, Quote, Scale, Star, UserCheck, XCircle } from "lucide-react";
import { Logo } from "@/components/app/logo";
import { Button } from "@/components/ui/button";
import { DashboardPreview, Ring } from "@/components/landing/dashboard-preview";

export function Hero() {
  return (
    <section id="home" className="hero-deep relative text-white">
      <div className="grid-texture pointer-events-none absolute inset-0" aria-hidden />
      <div className="relative mx-auto max-w-6xl px-5 pt-16 text-center sm:pt-24">
        <p className="mx-auto inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3.5 py-1.5 text-[13px] font-medium text-white/90">
          <span className="size-1.5 rounded-full bg-[#a5a4ff]" aria-hidden /> AI-powered recruitment
        </p>
        <h1 className="mx-auto mt-6 max-w-3xl text-[40px] leading-[1.05] font-semibold tracking-[-0.035em] sm:text-6xl">Hire on evidence, not guesswork</h1>
        <p className="mx-auto mt-5 max-w-xl text-base text-white/75 sm:text-lg">RC3 reads every resume, links each score to the exact words that earned it, and keeps the final call with your team.</p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Button asChild size="lg" className="bg-white text-[#2f2a9c] shadow-lg shadow-black/20 hover:bg-white/90"><Link href="/register">Get started free <ArrowRight /></Link></Button>
          <Button asChild size="lg" variant="ghost" className="border border-white/25 text-white hover:bg-white/10 hover:text-white"><Link href="/login">Sign in</Link></Button>
        </div>
      </div>
      <div className="relative mx-auto mt-14 max-w-5xl px-5 sm:mt-16">
        <div className="-mb-24 sm:-mb-32"><DashboardPreview /></div>
      </div>
    </section>
  );
}

const LOGOS = ["Lumora", "Veridian", "Kestrel & Co", "Halcyon", "Brightpath", "Orbitly"];
export function Trusted() {
  return (
    <section aria-label="Teams using RC3" className="mx-auto max-w-6xl px-5 pt-36 pb-6 sm:pt-44">
      <p className="text-center text-sm font-medium text-muted-foreground">Trusted by fast-growing teams (fictional examples)</p>
      <ul className="mt-6 flex flex-wrap items-center justify-center gap-x-10 gap-y-5 text-muted-foreground/80">
        {LOGOS.map((n, i) => (
          <li key={n} className="flex items-center gap-2 text-xl font-semibold tracking-tight">
            <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden fill="currentColor">
              {i % 3 === 0 && <circle cx="11" cy="11" r="9" opacity=".85" />}
              {i % 3 === 1 && <path d="M11 1.5l9 16.5H2z" opacity=".85" />}
              {i % 3 === 2 && <rect x="2" y="2" width="18" height="18" rx="5" opacity=".85" />}
            </svg>
            {n}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Mock({ children }: { children: React.ReactNode }) {
  return <div aria-hidden className="rounded-3xl border border-border/60 bg-gradient-to-br from-[#eef0ff] to-[#f6f0ff] p-5 shadow-soft sm:p-7 dark:from-[#1b1c3a] dark:to-[#221b3d]">{children}</div>;
}
function Row({ flip, eyebrow, title, text, points, children }: { flip?: boolean; eyebrow: string; title: string; text: string; points: string[]; children: React.ReactNode }) {
  return (
    <div className="reveal grid items-center gap-10 lg:grid-cols-2 lg:gap-16">
      <div className={flip ? "lg:order-2" : ""}>
        <p className="text-sm font-semibold text-brand">{eyebrow}</p>
        <h3 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h3>
        <p className="mt-3 text-[15px] text-muted-foreground sm:text-base">{text}</p>
        <ul className="mt-5 space-y-2.5">
          {points.map((p) => <li key={p} className="flex items-start gap-2.5 text-[15px]"><CheckCircle2 className="mt-0.5 size-[18px] shrink-0 text-brand" />{p}</li>)}
        </ul>
      </div>
      <div className={flip ? "lg:order-1" : ""}>{children}</div>
    </div>
  );
}

function Avatar({ name, from, to, size = 40 }: { name: string; from: string; to: string; size?: number }) {
  const ini = name.split(" ").map((w) => w[0]).join("").slice(0, 2);
  return <span className="grid shrink-0 place-items-center rounded-full font-semibold text-white" style={{ width: size, height: size, fontSize: size * 0.36, background: `linear-gradient(135deg, ${from}, ${to})` }}>{ini}</span>;
}

export function Features() {
  return (
    <section id="features" className="mx-auto max-w-6xl px-5 py-20 sm:py-28">
      <div className="mx-auto max-w-2xl text-center">
        <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">Why teams choose RC3</h2>
        <p className="mt-3 text-[15px] text-muted-foreground sm:text-base">Decisions you can explain to a candidate, a hiring manager, or an auditor.</p>
      </div>
      <div className="mt-16 space-y-20 sm:space-y-28">
        <Row eyebrow="Evidence-linked scoring" title="Every score points back to the resume" text="The model extracts structured facts and the exact quote behind each one. Scores are computed by deterministic code, so the same resume always earns the same result." points={["Click any skill to see the sentence it came from", "Resume parsing for PDF and DOCX files", "Generated interview questions tied to gaps and strengths"]}>
          <Mock>
            <div className="rounded-2xl bg-card p-4 shadow-soft">
              <div className="flex items-center gap-3"><Avatar name="Amina Rahman" from="#818cf8" to="#7c3aed" /><div className="min-w-0 flex-1"><p className="text-sm font-semibold">Amina Rahman</p><p className="text-[13px] text-muted-foreground">Senior Backend Engineer</p></div><Ring value={92} color="#16a34a" size={44} /></div>
              <div className="mt-4 rounded-xl bg-muted/60 p-3.5 text-[13px] leading-relaxed text-foreground/85">
                <Quote className="mb-1 size-4 text-brand" />
                Led migration of a payments service to <mark className="rounded bg-amber-200/80 px-1 text-slate-900 dark:bg-amber-300/30 dark:text-amber-100">PostgreSQL and Kafka</mark>, cutting p95 latency by 40% across six regions.
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">{["PostgreSQL", "Kafka", "System design"].map((t) => <span key={t} className="rounded-full bg-accent px-2.5 py-1 text-[13px] font-medium text-accent-foreground">{t}</span>)}</div>
            </div>
          </Mock>
        </Row>
        <Row flip eyebrow="Semantic skill match" title="Matches meaning, not just keywords" text="Skills are compared by meaning, so “React.js” and “React” align, and related experience counts. You see what matched and what is missing at a glance." points={["Matched and missing skills side by side", "Required and nice-to-have skills weighted separately", "Talent search across every parsed resume"]}>
          <Mock>
            <div className="rounded-2xl bg-card p-4 shadow-soft">
              <div className="flex items-center gap-4"><Ring value={88} size={72} /><div><p className="text-sm font-semibold">Skill match</p><p className="text-[13px] text-muted-foreground">7 of 8 required skills found</p></div></div>
              <p className="mt-4 text-[13px] font-medium text-muted-foreground">Matched</p>
              <div className="mt-1.5 flex flex-wrap gap-1.5">{["React", "TypeScript", "Node.js", "REST APIs", "AWS", "SQL", "Testing"].map((t) => <span key={t} className="inline-flex items-center gap-1 rounded-full bg-emerald-500/12 px-2.5 py-1 text-[13px] font-medium text-emerald-700 dark:text-emerald-300"><CheckCircle2 className="size-3.5" />{t}</span>)}</div>
              <p className="mt-3 text-[13px] font-medium text-muted-foreground">Missing</p>
              <div className="mt-1.5 flex flex-wrap gap-1.5"><span className="inline-flex items-center gap-1 rounded-full bg-rose-500/10 px-2.5 py-1 text-[13px] font-medium text-rose-700 dark:text-rose-300"><XCircle className="size-3.5" />GraphQL</span></div>
            </div>
          </Mock>
        </Row>
        <Row eyebrow="Transparent breakdown" title="See exactly how the number was built" text="Each assessment splits into weighted sections, so a recruiter can explain why a candidate ranked where they did, and a candidate can see how to improve." points={["Skills, experience, projects and qualifications", "Shortlist, schedule, collect feedback and decide in one place", "Interview scheduling that flags conflicts"]}>
          <Mock>
            <div className="space-y-3.5 rounded-2xl bg-card p-5 shadow-soft">
              {[["Skills", 46, 50], ["Experience", 22, 25], ["Projects", 12, 15], ["Qualifications", 8, 10]].map(([l, v, m]) => (
                <div key={l as string}>
                  <div className="flex justify-between text-[13px]"><span className="font-medium">{l}</span><span className="text-muted-foreground tabular-nums">{v} / {m}</span></div>
                  <div className="mt-1.5 h-2 rounded-full bg-muted"><div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500" style={{ width: `${((v as number) / (m as number)) * 100}%` }} /></div>
                </div>
              ))}
              <div className="flex items-center justify-between border-t border-border pt-3 text-sm"><span className="font-semibold">Overall</span><span className="text-lg font-semibold text-brand tabular-nums">88 / 100</span></div>
            </div>
          </Mock>
        </Row>
        <Row flip eyebrow="Fairness checks" title="Built to keep bias out of the ranking" text="Review candidates blind, and run a counterfactual check that changes protected attributes to confirm the score does not move." points={["Blind review hides names and personal details", "Counterfactual test per application", "Duplicate detection across applicants"]}>
          <Mock>
            <div className="space-y-3 rounded-2xl bg-card p-5 shadow-soft">
              <div className="flex items-center gap-3 rounded-xl bg-muted/60 p-3"><Eye className="size-5 text-brand" /><div className="flex-1"><p className="text-sm font-medium">Blind review</p><p className="text-[13px] text-muted-foreground">Name and photo hidden</p></div><span className="relative h-6 w-10 rounded-full bg-brand"><span className="absolute top-0.5 right-0.5 size-5 rounded-full bg-white" /></span></div>
              <div className="flex items-center gap-3 rounded-xl bg-emerald-500/10 p-3"><Scale className="size-5 text-emerald-600" /><div className="flex-1"><p className="text-sm font-medium">Counterfactual test</p><p className="text-[13px] text-muted-foreground">Score unchanged: 88 → 88</p></div><span className="inline-flex items-center gap-1 text-[13px] font-semibold text-emerald-700 dark:text-emerald-300"><CheckCircle2 className="size-4" />Passed</span></div>
              <div className="flex items-center gap-3 rounded-xl bg-muted/60 p-3"><Layers className="size-5 text-brand" /><div className="flex-1"><p className="text-sm font-medium">Duplicate check</p><p className="text-[13px] text-muted-foreground">No matching applicant found</p></div></div>
            </div>
          </Mock>
        </Row>
      </div>
    </section>
  );
}

const STEPS = [
  { i: FileSearch, t: "Post a job", d: "Describe the role, skills and weights." },
  { i: UserCheck, t: "Candidates apply", d: "Resumes are parsed into structured data." },
  { i: BadgeCheck, t: "AI shows evidence", d: "Scores link to the exact resume quotes." },
  { i: CalendarClock, t: "You decide", d: "Shortlist, interview and select with full context." },
];
export function HowItWorks() {
  return (
    <section id="how" className="border-y border-border/60 bg-muted/40 py-20 sm:py-24">
      <div className="mx-auto max-w-6xl px-5">
        <h2 className="reveal text-center text-3xl font-semibold tracking-tight sm:text-4xl">How it works</h2>
        <ol className="reveal mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <li key={s.t} className="relative">
              <span className="grid size-12 place-items-center rounded-2xl bg-brand/10 text-brand"><s.i className="size-6" /></span>
              <p className="mt-4 text-sm font-medium text-muted-foreground">Step {i + 1}</p>
              <h3 className="mt-1 text-lg font-semibold">{s.t}</h3>
              <p className="mt-1 text-[15px] text-muted-foreground">{s.d}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

// SAMPLE CONTENT: illustrative testimonials from fictional people and companies, not real customers.
const REVIEWS = [
  { n: "Priya Nair", r: "Head of Talent", c: "Lumora", q: "Every score pointed to a quote in the resume. We stopped arguing about gut feel and started discussing evidence.", a: ["#818cf8", "#7c3aed"] },
  { n: "Marcus Webb", r: "Engineering Manager", c: "Veridian", q: "The skill breakdown made it obvious why one candidate ranked above another. Debriefs got shorter and clearer.", a: ["#38bdf8", "#4f46e5"] },
  { n: "Sofia Alvarez", r: "Recruiting Lead", c: "Halcyon", q: "Blind review and the fairness check gave our hiring panel a process we could actually explain to candidates.", a: ["#f472b6", "#8b5cf6"] },
];
export function Reviews() {
  return (
    <section id="reviews" className="mx-auto max-w-6xl px-5 py-20 sm:py-28">
      <h2 className="reveal text-center text-3xl font-semibold tracking-tight sm:text-4xl">What our customers say</h2>
      <p className="mt-2 text-center text-sm text-muted-foreground">Sample reviews for illustration.</p>
      <ul className="mt-12 grid gap-5 md:grid-cols-3">
        {REVIEWS.map((r) => (
          <li key={r.n} className="reveal flex flex-col rounded-3xl border border-border/60 bg-card p-6 shadow-soft">
            <div className="flex gap-0.5" role="img" aria-label="5 out of 5 stars">{[0, 1, 2, 3, 4].map((i) => <Star key={i} className="size-[18px] fill-amber-400 text-amber-400" />)}</div>
            <blockquote className="mt-4 flex-1 text-[15px] leading-relaxed">“{r.q}”</blockquote>
            <figcaption className="mt-6 flex items-center gap-3">
              <Avatar name={r.n} from={r.a[0]} to={r.a[1]} />
              <div><p className="text-sm font-semibold">{r.n}</p><p className="text-[13px] text-muted-foreground">{r.r}, {r.c}</p></div>
            </figcaption>
          </li>
        ))}
      </ul>
    </section>
  );
}

const FAQ = [
  ["How are candidates scored?", "An AI model extracts skills, experience and projects from the resume together with the supporting quote. A deterministic scoring engine then applies your job’s weights, so the same inputs always give the same score."],
  ["Does the AI make hiring decisions?", "No. RC3 ranks and explains; recruiters shortlist, schedule, and decide. Every status change is made by a person and recorded in the application history."],
  ["How does RC3 handle fairness?", "You can review applications blind, and a counterfactual check re-scores a resume with protected attributes changed to confirm the result does not move."],
  ["Is candidate data private?", "Candidates control their own resumes and profile, and recruiters see only the applications submitted to their jobs. Sessions use secure, httpOnly cookies."],
  ["Which resume formats are supported?", "PDF and DOCX files. Parsing results are shown to the candidate to review and correct before applying."],
  ["How are interviews scheduled?", "From an application you propose a time, interview type and location or link. RC3 flags conflicts with existing interviews and notifies the candidate."],
  ["Is there a free demo?", "Yes. Create an account as a recruiter or candidate and explore with your own data, no payment details needed."],
];
export function Faq() {
  return (
    <section id="faq" className="mx-auto max-w-3xl px-5 pb-20 sm:pb-28">
      <h2 className="reveal text-center text-3xl font-semibold tracking-tight sm:text-4xl">Frequently asked questions</h2>
      <div className="mt-10 divide-y divide-border rounded-3xl border border-border/60 bg-card shadow-soft">
        {FAQ.map(([q, a], i) => (
          <details key={q} name="faq" open={i === 0} className="group px-6 py-1">
            <summary className="flex cursor-pointer items-center justify-between gap-4 rounded-lg py-4 text-[15px] font-medium sm:text-base">
              {q}
              <ChevronDown className="size-5 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden />
            </summary>
            <p className="pb-4 text-[15px] leading-relaxed text-muted-foreground">{a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

export function FinalCta() {
  return (
    <section className="px-5 pb-20">
      <div className="hero-deep relative mx-auto max-w-6xl overflow-hidden rounded-[2rem] px-6 py-16 text-center text-white sm:py-20">
        <div className="grid-texture absolute inset-0" aria-hidden />
        <h2 className="relative text-3xl font-semibold tracking-tight sm:text-4xl">Ready to hire with confidence?</h2>
        <p className="relative mx-auto mt-3 max-w-lg text-white/75">Create a free account and see evidence-linked scores on your own roles.</p>
        <div className="relative mt-8 flex flex-wrap justify-center gap-3">
          <Button asChild size="lg" className="bg-white text-[#2f2a9c] hover:bg-white/90"><Link href="/register">Get started <ArrowRight /></Link></Button>
          <Button asChild size="lg" variant="ghost" className="border border-white/25 text-white hover:bg-white/10 hover:text-white"><Link href="/login">Sign in</Link></Button>
        </div>
      </div>
    </section>
  );
}

const COLS: [string, [string, string][]][] = [
  ["Product", [["Features", "#features"], ["How it works", "#how"], ["Reviews", "#reviews"], ["FAQ", "#faq"]]],
  ["Account", [["Sign in", "/login"], ["Create account", "/register"]]],
  ["Legal", [["Privacy", "#"], ["Terms", "#"], ["Security", "#"]]],
];
export function Footer() {
  return (
    <footer className="border-t border-border/60">
      <div className="mx-auto grid max-w-6xl gap-10 px-5 py-14 sm:grid-cols-2 lg:grid-cols-[1.5fr_1fr_1fr_1fr]">
        <div><Logo /><p className="mt-4 max-w-xs text-[15px] text-muted-foreground">Evidence-based, explainable AI recruitment.</p></div>
        {COLS.map(([t, links]) => (
          <nav key={t} aria-label={t}>
            <p className="text-sm font-semibold">{t}</p>
            <ul className="mt-3 space-y-2 text-[15px] text-muted-foreground">{links.map(([l, h]) => <li key={l}><Link href={h} className="rounded hover:text-foreground">{l}</Link></li>)}</ul>
          </nav>
        ))}
      </div>
      <p className="border-t border-border/60 px-5 py-5 text-center text-sm text-muted-foreground">© {new Date().getFullYear()} RC3 Talent. All rights reserved.</p>
    </footer>
  );
}
