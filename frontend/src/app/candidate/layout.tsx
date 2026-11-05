import { redirect } from "next/navigation";
import { HydrationBoundary } from "@tanstack/react-query";
import { AppShell } from "@/components/app/shell";
import { prefetched, serverApi } from "@/lib/server";
import type { UserOut } from "@/lib/types";

// Stable shell: this layout never re-renders on in-segment navigation, so sidebar/topbar don't flash or re-mount.
export default async function Layout({ children }: { children: React.ReactNode }) {
  const me = await serverApi<UserOut>("/auth/me");
  if (me && (me.role as string) !== "candidate") redirect(me.role === "recruiter" ? "/recruiter" : "/candidate");
  const state = await prefetched([], (qc) => { if (me) qc.setQueryData(["me"], me); });
  return <HydrationBoundary state={state}><AppShell role="candidate">{children}</AppShell></HydrationBoundary>;
}
