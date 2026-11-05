import { cookies } from "next/headers";
import { QueryClient, dehydrate } from "@tanstack/react-query";

const API_URL = process.env.API_URL ?? process.env.BACKEND_URL ?? "http://localhost:8000";

/** Fetch from the backend with the caller's session cookie. Returns null on ANY failure (callers fall back to the client fetch). */
export async function serverApi<T>(path: string): Promise<T | null> {
  try {
    const cookie = (await cookies()).toString();
    if (!cookie) return null;
    const res = await fetch(`${API_URL}/api${path}`, {
      headers: { Accept: "application/json", cookie },
      cache: "no-store",
      signal: AbortSignal.timeout(6000),
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

/** Prefetch several queries in parallel; failures are skipped so the client simply fetches them itself. */
export async function prefetched(entries: [readonly unknown[], string][], extra?: (qc: QueryClient) => void) {
  const qc = new QueryClient();
  await Promise.all(
    entries.map(async ([key, path]) => {
      const data = await serverApi<unknown>(path);
      if (data !== null) qc.setQueryData(key, data);
    }),
  );
  extra?.(qc);
  return dehydrate(qc);
}
