"use client";
import * as React from "react";
import * as D from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export const Sheet = D.Root;
export const SheetTrigger = D.Trigger;
export const SheetClose = D.Close;

/** Right-hand drawer built on Radix Dialog: wide, scrollable body, sticky footer slot. */
export function SheetContent({ className, children, ...p }: React.ComponentProps<typeof D.Content>) {
  return (
    <D.Portal>
      <D.Overlay className="fixed inset-0 z-50 bg-black/45 data-[state=open]:animate-in data-[state=open]:fade-in-0" />
      <D.Content
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col border-l bg-card shadow-2xl outline-none data-[state=open]:animate-in data-[state=open]:slide-in-from-right sm:rounded-l-3xl",
          className,
        )}
        {...p}
      >
        {children}
        <D.Close className="absolute top-4 right-4 rounded-full p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground" aria-label="Close">
          <X className="size-4" />
        </D.Close>
      </D.Content>
    </D.Portal>
  );
}
export function SheetHeader({ className, ...p }: React.ComponentProps<"div">) {
  return <div className={cn("flex flex-col gap-1 border-b px-6 py-5 pr-14", className)} {...p} />;
}
export function SheetBody({ className, ...p }: React.ComponentProps<"div">) {
  return <div className={cn("min-h-0 flex-1 space-y-6 overflow-y-auto px-6 py-5", className)} {...p} />;
}
export function SheetFooter({ className, ...p }: React.ComponentProps<"div">) {
  return <div className={cn("flex items-center justify-end gap-2 border-t bg-card px-6 py-4", className)} {...p} />;
}
export function SheetTitle({ className, ...p }: React.ComponentProps<typeof D.Title>) {
  return <D.Title className={cn("text-lg leading-tight font-semibold", className)} {...p} />;
}
export function SheetDescription({ className, ...p }: React.ComponentProps<typeof D.Description>) {
  return <D.Description className={cn("text-sm text-muted-foreground", className)} {...p} />;
}
