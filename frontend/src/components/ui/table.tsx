import * as React from "react";
import { cn } from "@/lib/utils";

export function Table({ className, ...p }: React.ComponentProps<"table">) {
  return (
    <div className="w-full overflow-x-auto">
      <table className={cn("w-full caption-bottom text-sm", className)} {...p} />
    </div>
  );
}
export function THead(p: React.ComponentProps<"thead">) {
  return <thead className="[&_tr]:border-b bg-muted/40" {...p} />;
}
export function TBody(p: React.ComponentProps<"tbody">) {
  return <tbody className="[&_tr:last-child]:border-0" {...p} />;
}
export function TR({ className, ...p }: React.ComponentProps<"tr">) {
  return <tr className={cn("border-b border-border/60 transition-colors hover:bg-primary/5", className)} {...p} />;
}
export function TH({ className, ...p }: React.ComponentProps<"th">) {
  return (
    <th className={cn("h-11 px-4 text-left align-middle text-[11px] font-semibold tracking-wider whitespace-nowrap uppercase text-muted-foreground", className)} {...p} />
  );
}
export function TD({ className, ...p }: React.ComponentProps<"td">) {
  return <td className={cn("px-4 py-3.5 align-middle", className)} {...p} />;
}
