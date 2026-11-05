"use client";
import { Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AuthFrame } from "@/components/app/auth-frame";
import { api, errMsg } from "@/lib/api";
import type { LoginIn, UserOut } from "@/lib/types";
import { homeFor } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Banner } from "@/components/ui/misc";

const schema = z.object({ email: z.string().email("Enter a valid email"), password: z.string().min(1, "Password is required") });

function LoginForm() {
  const router = useRouter();
  const qc = useQueryClient();
  const next = useSearchParams().get("next");
  const form = useForm<LoginIn>({ resolver: zodResolver(schema), defaultValues: { email: "", password: "" } });
  const m = useMutation({
    mutationFn: (v: LoginIn) => api<UserOut>("/auth/login", { body: v }),
    onSuccess: (u) => {
      qc.setQueryData(["me"], u);
      const safe = next && next.startsWith(`/${u.role}`) ? next : homeFor(u.role);
      router.replace(safe);
    },
  });
  return (
    <AuthFrame title="Welcome back" subtitle="Sign in to continue">
      <form onSubmit={form.handleSubmit((v) => m.mutate(v))} className="space-y-4" noValidate>
        {m.error && <Banner tone="danger">{errMsg(m.error)}</Banner>}
        <Field label="Email" htmlFor="email" error={form.formState.errors.email?.message}>
          <Input id="email" type="email" autoComplete="email" aria-invalid={!!form.formState.errors.email} {...form.register("email")} />
        </Field>
        <Field label="Password" htmlFor="password" error={form.formState.errors.password?.message}>
          <Input id="password" type="password" autoComplete="current-password" aria-invalid={!!form.formState.errors.password} {...form.register("password")} />
        </Field>
        <Button type="submit" className="w-full" loading={m.isPending}>Sign in</Button>
      </form>
      <p className="text-center text-sm text-muted-foreground">
        New here? <Link href="/register" className="font-medium text-primary hover:underline">Create an account</Link>
      </p>
    </AuthFrame>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
