import { LogoPulse } from "@/components/app/logo";
import { Skeleton } from "@/components/ui/misc";

/** Layout-matched placeholder for any app route: header row, stat cards, two content panes. */
export function RouteSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading page" className="space-y-6">
      <LogoPulse className="py-1" />
      <div className="flex items-center justify-between gap-3">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-10 w-32 rounded-full" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-32 rounded-2xl" />)}
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        <Skeleton className="h-72 rounded-2xl" />
        <Skeleton className="h-72 rounded-2xl" />
      </div>
    </div>
  );
}
