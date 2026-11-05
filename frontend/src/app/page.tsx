import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { serverApi } from "@/lib/server";
import type { UserOut } from "@/lib/types";
import { LandingNav } from "@/components/landing/nav";
import { FinalCta, Faq, Features, Footer, Hero, HowItWorks, Reviews, Trusted } from "@/components/landing/sections";

export const metadata: Metadata = {
  title: "RC3 Talent | Hire on evidence, not guesswork",
  description: "Explainable AI recruitment: resume parsing, evidence-linked scores, interview scheduling and fairness checks in one place.",
  openGraph: {
    title: "RC3 Talent | Hire on evidence, not guesswork",
    description: "Every score links back to the exact resume quote behind it. Humans make the final call.",
    type: "website",
    siteName: "RC3 Talent",
  },
  twitter: { card: "summary", title: "RC3 Talent", description: "Explainable, evidence-linked AI recruitment." },
};

export default async function Home() {
  // Server-side session check: signed-in users never see the landing page flash.
  const me = await serverApi<UserOut>("/auth/me");
  if (me) redirect(me.role === "recruiter" ? "/recruiter" : "/candidate");
  return (
    <>
      <LandingNav />
      <main id="main">
        <Hero />
        <Trusted />
        <Features />
        <HowItWorks />
        <Reviews />
        <Faq />
        <FinalCta />
      </main>
      <Footer />
    </>
  );
}
