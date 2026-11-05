"use client";
import { useEffect } from "react";
import Link from "next/link";
import { RefreshCw, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

export function RouteError({ error, reset, home }: { error: Error & { digest?: string }; reset: () => void; home: string }) {
  useEffect(() => { console.error(error); }, [error]);
  return (
    <div role="alert" className="mx-auto mt-16 flex max-w-md flex-col items-center gap-3 text-center">
      <span className="grid size-12 place-items-center rounded-2xl bg-destructive/10 text-destructive"><TriangleAlert className="size-6" /></span>
      <h1 className="text-xl font-semibold">Something went wrong</h1>
      <p className="text-[15px] text-muted-foreground">This page failed to load. Your data is safe; try again, and if it keeps happening, head back to the dashboard.</p>
      <div className="mt-2 flex gap-2">
        <Button onClick={reset}><RefreshCw /> Try again</Button>
        <Button asChild variant="outline"><Link href={home}>Go to dashboard</Link></Button>
      </div>
    </div>
  );
}

export function NotFoundView({ home }: { home: string }) {
  return (
    <div className="mx-auto mt-16 flex max-w-md flex-col items-center gap-3 text-center">
      <p className="text-5xl font-semibold tracking-tight text-brand">404</p>
      <h1 className="text-xl font-semibold">We couldn’t find that page</h1>
      <p className="text-[15px] text-muted-foreground">The link may be out of date, or the item was removed.</p>
      <Button asChild className="mt-2"><Link href={home}>Back to dashboard</Link></Button>
    </div>
  );
}
