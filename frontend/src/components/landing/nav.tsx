"use client";
import { useState } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";
import { Logo } from "@/components/app/logo";
import { Button } from "@/components/ui/button";

const LINKS = [["#home", "Home"], ["#features", "Features"], ["#how", "How it works"], ["#reviews", "Reviews"], ["#faq", "FAQ"]] as const;

export function LandingNav() {
  const [open, setOpen] = useState(false);
  return (
    <header className="glass sticky top-0 z-50 border-b border-border/50">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-5">
        <Logo href="/" />
        <nav aria-label="Primary" className="hidden items-center gap-1 md:flex">
          {LINKS.map(([h, l]) => <a key={h} href={h} className="rounded-full px-3.5 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">{l}</a>)}
        </nav>
        <div className="flex items-center gap-2">
          <Button asChild variant="ghost" className="hidden sm:inline-flex"><Link href="/login">Sign in</Link></Button>
          <Button asChild><Link href="/register">Get started</Link></Button>
          <Button variant="outline" size="icon" className="md:hidden" aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open} aria-controls="mobile-menu" onClick={() => setOpen((o) => !o)}>
            {open ? <X /> : <Menu />}
          </Button>
        </div>
      </div>
      {open && (
        <nav id="mobile-menu" aria-label="Mobile" className="border-t border-border/50 bg-background px-5 py-3 md:hidden">
          <ul className="flex flex-col">
            {LINKS.map(([h, l]) => <li key={h}><a href={h} onClick={() => setOpen(false)} className="block rounded-lg px-2 py-3 text-[15px] font-medium">{l}</a></li>)}
            <li><Link href="/login" className="block rounded-lg px-2 py-3 text-[15px] font-medium">Sign in</Link></li>
          </ul>
        </nav>
      )}
    </header>
  );
}
