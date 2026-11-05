"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { homeFor, useMe } from "@/lib/auth";
import { Spinner } from "@/components/ui/misc";
import { Landing } from "@/components/app/landing";

export default function Home() {
  const { data: me, isLoading } = useMe();
  const router = useRouter();
  useEffect(() => {
    if (isLoading || !me) return;
    router.replace(homeFor(me.role));
  }, [me, isLoading, router]);
  if (isLoading || me) {
    return (
      <div className="grid min-h-screen place-items-center">
        <Spinner className="size-6" />
      </div>
    );
  }
  return <Landing />;
}
