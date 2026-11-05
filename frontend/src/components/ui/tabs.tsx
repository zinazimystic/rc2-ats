"use client";
import * as React from "react";
import * as T from "@radix-ui/react-tabs";
import { cn } from "@/lib/utils";

export const Tabs = T.Root;
export function TabsList({ className, ...p }: React.ComponentProps<typeof T.List>) {
  return (
    <T.List
      className={cn("inline-flex h-11 w-fit max-w-full items-center gap-1 overflow-x-auto rounded-full bg-muted p-1", className)}
      {...p}
    />
  );
}
export function TabsTrigger({ className, ...p }: React.ComponentProps<typeof T.Trigger>) {
  return (
    <T.Trigger
      className={cn(
        "inline-flex h-9 items-center justify-center gap-1.5 rounded-full px-4 text-sm font-medium whitespace-nowrap text-muted-foreground transition-colors hover:text-foreground data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm",
        className,
      )}
      {...p}
    />
  );
}
export function TabsContent({ className, ...p }: React.ComponentProps<typeof T.Content>) {
  return <T.Content className={cn("mt-4 outline-none", className)} {...p} />;
}
