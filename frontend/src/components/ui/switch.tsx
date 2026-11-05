"use client";
import * as React from "react";
import * as S from "@radix-ui/react-switch";
import { cn } from "@/lib/utils";

export function Switch({ className, ...p }: React.ComponentProps<typeof S.Root>) {
  return (
    <S.Root
      className={cn(
        "peer inline-flex h-6 w-11 shrink-0 items-center rounded-full border border-transparent bg-input transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary",
        className,
      )}
      {...p}
    >
      <S.Thumb className="pointer-events-none block size-5 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-[1.375rem]" />
    </S.Root>
  );
}
