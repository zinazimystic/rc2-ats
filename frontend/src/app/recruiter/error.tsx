"use client";
import { RouteError } from "@/components/app/route-error";
export default function Error(p: { error: Error & { digest?: string }; reset: () => void }) {
  return <RouteError {...p} home="/recruiter" />;
}
