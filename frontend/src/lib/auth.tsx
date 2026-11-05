"use client";
import { useEffect, useSyncExternalStore, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { api, ApiError } from "./api";
import type { Role, UserOut } from "./types";
import { Skeleton } from "@/components/ui/misc";

export function useMe() {
  return useQuery<UserOut | null>({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        return await api<UserOut>("/auth/me");
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
    staleTime: 60_000,
  });
}

export function homeFor(role: Role) {
  return role === "recruiter" ? "/recruiter" : "/candidate";
}

export function useLogout() {
  const qc = useQueryClient();
  const router = useRouter();
  return async () => {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch {
      /* cookie may already be gone */
    }
    qc.clear();
    qc.setQueryData(["me"], null);
    router.replace("/login");
  };
}

const subscribeNoop = () => () => {};

export function AuthGate({ role, children }: { role: Role; children: (user: UserOut) => ReactNode }) {
  const { data: me, isLoading, error, refetch } = useMe();
  const mounted = useSyncExternalStore(subscribeNoop, () => true, () => false);
  const router = useRouter();
  const pathname = usePathname();
  useEffect(() => {
    if (isLoading) return;
    if (me === null) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    else if (me && me.role !== role) router.replace(homeFor(me.role));
  }, [me, isLoading, role, router, pathname]);

  if (error)
    return (
      <div className="mx-auto mt-24 max-w-md space-y-3 p-6 text-center">
        <h1 className="text-lg font-semibold">Can’t reach the server</h1>
        <p className="text-sm text-muted-foreground">{(error as Error).message}</p>
        <button className="text-sm font-medium text-primary underline" onClick={() => refetch()}>
          Retry
        </button>
      </div>
    );
  // The server never knows the session, so the first client render must match the server's skeleton exactly;
  // once mounted, the (already prefetched) user swaps in without a network wait.
  if (!mounted || isLoading || !me || me.role !== role)
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  return <>{children(me)}</>;
}
