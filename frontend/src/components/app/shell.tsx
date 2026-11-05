"use client";
import { useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useTheme } from "next-themes";
import {
  Bell, BriefcaseBusiness, CalendarDays, CopyCheck, FileText, LayoutDashboard, LogOut, Menu, Moon, Search,
  Send, Sparkles, Sun, X,
} from "lucide-react";
import { api } from "@/lib/api";
import { AuthGate, useLogout } from "@/lib/auth";
import type { HealthOut, NotificationOut, Role, UserOut } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface NavItem {
  href: string;
  label: string;
  icon: ReactNode;
  exact?: boolean;
}

const NAV: Record<Role, NavItem[]> = {
  recruiter: [
    { href: "/recruiter", label: "Dashboard", icon: <LayoutDashboard />, exact: true },
    { href: "/recruiter/jobs", label: "Jobs", icon: <BriefcaseBusiness /> },
    { href: "/recruiter/interviews", label: "Interviews", icon: <CalendarDays /> },
    { href: "/recruiter/search", label: "Talent search", icon: <Search /> },
    { href: "/recruiter/duplicates", label: "Duplicates", icon: <CopyCheck /> },
    { href: "/recruiter/notifications", label: "Notifications", icon: <Bell /> },
  ],
  candidate: [
    { href: "/candidate", label: "Jobs for you", icon: <Sparkles />, exact: true },
    { href: "/candidate/applications", label: "My applications", icon: <Send /> },
    { href: "/candidate/resume", label: "Resume & profile", icon: <FileText /> },
    { href: "/candidate/notifications", label: "Notifications", icon: <Bell /> },
  ],
};

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  return (
    <Button variant="ghost" size="icon" aria-label="Toggle dark mode" onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}>
      <Sun className="hidden dark:block" />
      <Moon className="dark:hidden" />
    </Button>
  );
}

function HealthDots() {
  const { data } = useQuery({ queryKey: ["health"], queryFn: () => api<HealthOut>("/health"), refetchInterval: 60_000 });
  if (!data) return null;
  const item = (label: string, ok: boolean, detail: string | null) => (
    <span title={detail ?? (ok ? "OK" : "Unavailable")} className="inline-flex items-center gap-1 text-xs text-muted-foreground">
      <span className={cn("size-2 rounded-full", ok ? "bg-success" : "bg-warning")} aria-hidden />
      {label}
      <span className="sr-only">{ok ? "available" : "degraded"}</span>
    </span>
  );
  return (
    <div className="hidden items-center gap-3 md:flex" aria-label="System status">
      {item("DB", data.database.ok, data.database.detail)}
      {item("LLM", data.llm.ok, data.llm.detail ?? data.llm_model)}
      {item("Embeddings", data.embeddings.ok, data.embeddings.detail ?? data.embedding_model)}
    </div>
  );
}

function Shell({ user, children }: { user: UserOut; children: ReactNode }) {
  const pathname = usePathname();
  const logout = useLogout();
  const [open, setOpen] = useState(false);
  const { data: notifs } = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => api<NotificationOut[]>("/notifications?unread=true"),
    refetchInterval: 15_000,
  });
  const unread = notifs?.length ?? 0;
  const items = NAV[user.role];

  const nav = (
    <nav aria-label="Main" className="flex flex-col gap-1 p-3">
      {items.map((it) => {
        const active = it.exact ? pathname === it.href : pathname.startsWith(it.href);
        return (
          <Link
            key={it.href}
            href={it.href}
            onClick={() => setOpen(false)}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-white/70 transition-colors hover:bg-white/10 hover:text-white [&_svg]:size-4",
              active && "bg-white/15 text-white",
            )}
          >
            {it.icon}
            <span className="flex-1">{it.label}</span>
            {it.label === "Notifications" && unread > 0 && (
              <Badge className="bg-primary text-primary-foreground">{unread}</Badge>
            )}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col bg-sidebar text-white lg:flex">
        <div className="flex h-14 items-center gap-2 px-5 font-semibold">
          <span className="grid size-7 place-items-center rounded-md bg-primary text-primary-foreground">
            <Sparkles className="size-4" />
          </span>
          RC3 Talent
        </div>
        {nav}
        <div className="mt-auto border-t border-white/10 p-4 text-xs text-white/60">
          <p className="truncate font-medium text-white">{user.full_name}</p>
          <p className="truncate">{user.email}</p>
          <Badge variant="secondary" className="mt-2 capitalize">{user.role}</Badge>
        </div>
      </aside>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} />
          <div className="relative h-full w-64 bg-sidebar text-white">
            <button className="absolute top-3 right-3 text-white/70" onClick={() => setOpen(false)} aria-label="Close menu">
              <X className="size-5" />
            </button>
            <div className="flex h-14 items-center px-5 font-semibold">RC3 Talent</div>
            {nav}
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/85 px-4 backdrop-blur">
          <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open menu" onClick={() => setOpen(true)}>
            <Menu />
          </Button>
          <HealthDots />
          <div className="ml-auto flex items-center gap-1">
            <Button variant="ghost" size="icon" asChild aria-label={`Notifications${unread ? ` (${unread} unread)` : ""}`}>
              <Link href={`/${user.role}/notifications`} className="relative">
                <Bell />
                {unread > 0 && <span className="absolute top-1.5 right-1.5 size-2 rounded-full bg-destructive" />}
              </Link>
            </Button>
            <ThemeToggle />
            <Button variant="ghost" size="sm" onClick={logout}>
              <LogOut /> <span className="hidden sm:inline">Sign out</span>
            </Button>
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-7xl flex-1 p-4 sm:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}

export function AppShell({ role, children }: { role: Role; children: ReactNode }) {
  return <AuthGate role={role}>{(user) => <Shell user={user}>{children}</Shell>}</AuthGate>;
}
