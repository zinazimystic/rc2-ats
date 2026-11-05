"use client";
import { Toaster as Sonner } from "sonner";
import { useTheme } from "next-themes";
import { AlertTriangle, CheckCircle2, Info, Loader2, XCircle } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";

const chip = (tone: string, icon: ReactNode) => (
  <span className={`grid size-7 place-items-center rounded-full ${tone} [&_svg]:size-4`}>{icon}</span>
);

export function Toaster() {
  const { resolvedTheme } = useTheme();
  return (
    <Sonner
      theme={resolvedTheme === "dark" ? "dark" : "light"}
      position="top-right"
      duration={4000}
      closeButton
      visibleToasts={4}
      icons={{
        success: chip("bg-success/15 text-success", <CheckCircle2 />),
        error: chip("bg-destructive/15 text-destructive", <XCircle />),
        warning: chip("bg-warning/25 text-[color-mix(in_oklab,var(--warning)_60%,var(--foreground))]", <AlertTriangle />),
        info: chip("bg-primary/15 text-primary", <Info />),
        loading: chip("bg-primary/15 text-primary", <Loader2 className="animate-spin" />),
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--border-radius": "1rem",
        } as CSSProperties
      }
      toastOptions={{
        classNames: {
          toast: "!rounded-2xl !border !border-border/70 !bg-popover !text-popover-foreground !shadow-[0_10px_30px_-10px_rgb(0_0_0/0.25)] !gap-3 !p-4",
          title: "!text-sm !font-semibold",
          description: "!text-xs !text-muted-foreground",
          actionButton: "!rounded-full !bg-primary !px-3 !text-primary-foreground !text-xs !font-medium",
          cancelButton: "!rounded-full !bg-muted !text-foreground",
          closeButton: "!border-border !bg-popover !text-muted-foreground hover:!bg-muted",
          icon: "!m-0 !size-7",
        },
      }}
    />
  );
}
