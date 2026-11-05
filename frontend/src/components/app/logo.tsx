import Link from "next/link";
import { cn } from "@/lib/utils";

/**
 * RC3 mark: a geometric "R" (stem + bowl + leg) whose leg ends in a connected node,
 * i.e. a candidate flowing through a pipeline. Two colours only (brand indigo + white); `mono` draws it in currentColor.
 */
export function LogoMark({ size = 32, mono = false, className }: { size?: number; mono?: boolean; className?: string }) {
  const ink = mono ? "currentColor" : "#fff";
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" role="img" aria-label="RC3" className={cn("shrink-0", className)}>
      {!mono && <rect width="32" height="32" rx="9" fill="#4f46e5" />}
      <g stroke={ink} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
        <path d="M11 8.5v15" />
        <path d="M11 8.5h5.2a4.3 4.3 0 0 1 0 8.6H11" />
        <path d="M16 17.2l4.2 4.6" />
      </g>
      <circle cx="23" cy="23.6" r="2.7" fill={ink} />
    </svg>
  );
}

export function Logo({
  size = 32,
  withWordmark = true,
  mono = false,
  onDark = false,
  href,
  className,
}: {
  size?: number;
  withWordmark?: boolean;
  mono?: boolean;
  onDark?: boolean;
  href?: string;
  className?: string;
}) {
  const inner = (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark size={size} mono={mono} />
      {withWordmark && (
        <span className={cn("text-[17px] leading-none font-semibold tracking-[-0.03em]", onDark ? "text-white" : "text-foreground")}>
          <span className={onDark ? "text-[#a5a4ff]" : "text-brand"}>RC3</span> Talent
        </span>
      )}
    </span>
  );
  return href ? (
    <Link href={href} aria-label="RC3 Talent home" className="rounded-lg">
      {inner}
    </Link>
  ) : (
    inner
  );
}

/** Pulsing mark for route-level loading states. */
export function LogoPulse({ className }: { className?: string }) {
  return (
    <div className={cn("grid place-items-center", className)} role="status" aria-label="Loading">
      <span className="logo-pulse"><LogoMark size={44} /></span>
    </div>
  );
}
