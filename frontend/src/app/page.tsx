"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { homeFor, useMe } from "@/lib/auth";
import { Spinner } from "@/components/ui/misc";

export default function Home() {
  const { data: me, isLoading } = useMe();
  const router = useRouter();
  useEffect(() => {
    if (isLoading) return;
    router.replace(me ? homeFor(me.role) : "/login");
  }, [me, isLoading, router]);
  return (
    <div className="grid min-h-screen place-items-center">
      <Spinner className="size-6" />
    </div>
  );
}
