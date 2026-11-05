import Link from "next/link";
import { Logo } from "@/components/app/logo";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main id="main" className="grid min-h-screen place-items-center p-6 text-center">
      <div className="flex max-w-md flex-col items-center gap-3">
        <Logo href="/" />
        <p className="mt-6 text-5xl font-semibold tracking-tight text-brand">404</p>
        <h1 className="text-xl font-semibold">This page doesn’t exist</h1>
        <p className="text-[15px] text-muted-foreground">Check the address, or go back to the start.</p>
        <Button asChild className="mt-2"><Link href="/">Back to home</Link></Button>
      </div>
    </main>
  );
}
