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
  return <thead className="[&_tr]:border-b" {...p} />;
}
export function TBody(p: React.ComponentProps<"tbody">) {
  return <tbody className="[&_tr:last-child]:border-0" {...p} />;
}
export function TR({ className, ...p }: React.ComponentProps<"tr">) {
  return <tr className={cn("border-b transition-colors hover:bg-muted/50", className)} {...p} />;
}
export function TH({ className, ...p }: React.ComponentProps<"th">) {
  return (
    <th className={cn("h-10 px-3 text-left align-middle text-xs font-medium whitespace-nowrap text-muted-foreground", className)} {...p} />
  );
}
export function TD({ className, ...p }: React.ComponentProps<"td">) {
  return <td className={cn("p-3 align-middle", className)} {...p} />;
}
