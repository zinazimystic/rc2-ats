"use client";
import { useState, useSyncExternalStore, type ReactNode } from "react";
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
import { useCandidateDashboard, usePrefetch } from "@/lib/queries";
import type { NotificationOut, Role, UserOut } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/app/logo";
import { RouteSkeleton } from "@/components/app/route-skeleton";

// Dates/times format per viewer locale+timezone, so page content renders after hydration (data is already in the cache) to avoid server/client mismatches.
const noop = () => () => {};
function useHydrated() { return useSyncExternalStore(noop, () => true, () => false); }

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
    <Button variant="outline" size="icon" aria-label="Toggle dark mode" onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}>
      <Sun className="hidden dark:block" />
      <Moon className="dark:hidden" />
    </Button>
  );
}

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("") || "U";
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
  const isCand = user.role === "candidate";
  const prefetch = usePrefetch();
  const dash = useCandidateDashboard(isCand);
  const comp = dash.data?.profile.completion;
  // Server value only. While loading, reserve the card space (no pop-in); at 100% the card is gone.
  const showCompletion = isCand && ((!dash.data && !dash.isError) || (comp ? comp.percent < 100 : false));
  const pct = comp ? Math.round(comp.percent) : null;
  const unread = notifs?.length ?? 0;
  const items = NAV[user.role];
  const hydrated = useHydrated();

  const nav = (
    <nav aria-label="Main" className="flex flex-col gap-1.5 px-4 py-2">
      {items.map((it) => {
        const active = it.exact ? pathname === it.href : pathname.startsWith(it.href);
        return (
          <Link
            key={it.href}
            href={it.href}
            onClick={() => setOpen(false)}
            onMouseEnter={() => prefetch(it.href)}
            onFocus={() => prefetch(it.href)}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-full px-4 py-2.5 text-sm font-medium text-white/65 transition-all hover:bg-white/10 hover:text-white [&_svg]:size-[18px]",
              active && "bg-primary text-white shadow-lg shadow-primary/30 hover:bg-primary",
            )}
          >
            {it.icon}
            <span className="flex-1">{it.label}</span>
            {it.label === "Notifications" && unread > 0 && (
              <span className={cn("grid min-w-5 place-items-center rounded-full px-1.5 text-[13px] font-semibold", active ? "bg-white/25 text-white" : "bg-primary text-white")}>{unread}</span>
            )}
          </Link>
        );
      })}
    </nav>
  );

  const brand = (
    <div className="flex h-16 items-center px-6"><Logo href={`/${user.role}`} size={32} onDark /></div>
  );

  const sidebarFoot = (
    <div className="mt-auto space-y-3 p-4">
      {showCompletion && pct === null && <div className="h-[8.5rem] animate-pulse rounded-2xl bg-white/8" aria-hidden />}
      {showCompletion && pct !== null && (
        <Link href="/candidate/resume" onMouseEnter={() => prefetch("/candidate/resume")} className="block rounded-2xl bg-white/8 p-4 transition-colors hover:bg-white/12">
          <div className="flex items-center justify-between"><p className="text-sm font-semibold text-white">Complete your profile</p>{pct !== null && <span className="text-sm font-bold text-white tabular-nums">{pct}%</span>}</div>
          {pct !== null && <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/15" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Profile completion"><div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} /></div>}
          <p className="mt-1 text-[13px] text-white/60">{comp && comp.missing.length > 0 ? `Still to add: ${comp.missing.slice(0, 2).join(", ")}` : "Add a few details to improve your job matches."}</p>
          <span className="mt-3 inline-flex rounded-full bg-primary px-3.5 py-1.5 text-[13px] font-medium text-white">Finish profile</span>
        </Link>
      )}
      <div className="flex items-center gap-3 rounded-2xl bg-white/6 p-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-full bg-primary/90 text-[13px] font-semibold text-white">{initials(user.full_name)}</span>
        <div className="min-w-0 text-[13px] text-white/60">
          <p className="truncate font-medium text-white">{user.full_name}</p>
          <p className="truncate capitalize">{user.role}</p>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen gap-0 lg:p-3">
      <aside className="sticky top-3 hidden h-[calc(100vh-1.5rem)] w-64 shrink-0 flex-col rounded-3xl bg-sidebar text-white shadow-xl lg:flex">
        {brand}
        {nav}
        {sidebarFoot}
      </aside>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} />
          <div className="relative flex h-full w-72 flex-col rounded-r-3xl bg-sidebar text-white">
            <button className="absolute top-4 right-4 text-white/70" onClick={() => setOpen(false)} aria-label="Close menu">
              <X className="size-5" />
            </button>
            {brand}
            {nav}
            {sidebarFoot}
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col lg:pl-6">
        <header className="sticky top-0 z-30 flex min-h-16 items-center gap-3 bg-background/80 px-4 py-3 backdrop-blur lg:static lg:bg-transparent lg:px-0 lg:backdrop-blur-none">
          <Button variant="outline" size="icon" className="lg:hidden" aria-label="Open menu" onClick={() => setOpen(true)}>
            <Menu />
          </Button>
          <Logo href={`/${user.role}`} size={28} withWordmark={false} className="lg:hidden" />
          <div className="ml-auto flex items-center gap-2">
            <Button variant="outline" size="icon" asChild aria-label={`Notifications${unread ? ` (${unread} unread)` : ""}`}>
              <Link href={`/${user.role}/notifications`} className="relative">
                <Bell />
                {unread > 0 && <span className="absolute top-2 right-2.5 size-2 rounded-full bg-destructive ring-2 ring-card" />}
              </Link>
            </Button>
            <ThemeToggle />
            <div className="ml-1 hidden items-center gap-2.5 rounded-full border border-border/60 bg-card py-1 pr-4 pl-1 shadow-soft md:flex">
              <span className="grid size-8 place-items-center rounded-full bg-primary text-[13px] font-semibold text-white">{initials(user.full_name)}</span>
              <div className="min-w-0 text-[13px] leading-tight">
                <p className="max-w-36 truncate font-semibold">{user.full_name}</p>
                <p className="max-w-36 truncate text-muted-foreground">{user.email}</p>
              </div>
            </div>
            <Button variant="ghost" size="sm" onClick={logout}>
              <LogOut /> <span className="hidden sm:inline">Sign out</span>
            </Button>
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-7xl flex-1 p-4 pt-2 sm:p-6 sm:pt-2 lg:px-0">
          {hydrated ? children : <RouteSkeleton />}
        </main>
      </div>
    </div>
  );
}

export function AppShell({ role, children }: { role: Role; children: ReactNode }) {
  return <AuthGate role={role}>{(user) => <Shell user={user}>{children}</Shell>}</AuthGate>;
}
