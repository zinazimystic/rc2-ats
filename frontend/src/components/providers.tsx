"use client";
import { useState, type ReactNode } from "react";
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/sonner";
import { ApiError } from "@/lib/api";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(() => {
    const on401 = (e: unknown) => {
      // Session expired mid-use: clear the cached user; AuthGate redirects to /login.
      if (e instanceof ApiError && e.status === 401) client.setQueryData(["me"], null);
    };
    const client: QueryClient = new QueryClient({
      queryCache: new QueryCache({ onError: on401 }),
      mutationCache: new MutationCache({ onError: on401 }),
      defaultOptions: {
        queries: {
          staleTime: 45_000,
          gcTime: 15 * 60_000,
          refetchOnWindowFocus: false,
          retry: (n, e) => !(e instanceof ApiError && e.status < 500 && e.status !== 0) && n < 2,
        },
      },
    });
    return client;
  });
  return (
    <ThemeProvider>
      <QueryClientProvider client={client}>
        {children}
        <Toaster />
      </QueryClientProvider>
    </ThemeProvider>
  );
}
