"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errMsg } from "@/lib/api";
import type { RegisterIn, UserOut } from "@/lib/types";
import { homeFor } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Banner } from "@/components/ui/misc";
import { AuthFrame } from "@/components/app/auth-frame";
import { cn } from "@/lib/utils";

const schema = z.object({
  full_name: z.string().trim().min(2, "Enter your full name"),
  email: z.string().email("Enter a valid email"),
  password: z
    .string()
    .min(8, "At least 8 characters")
    .regex(/[A-Za-z]/, "Include a letter")
    .regex(/\d/, "Include a digit"),
  role: z.enum(["recruiter", "candidate"]),
  invite_code: z.string().optional(),
});

export default function RegisterPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { full_name: "", email: "", password: "", role: "candidate", invite_code: "" },
  });
  const role = useWatch({ control: form.control, name: "role" });
  const e = form.formState.errors;
  const m = useMutation({
    mutationFn: (v: z.infer<typeof schema>) => {
      const body: RegisterIn = { ...v, invite_code: v.role === "recruiter" && v.invite_code ? v.invite_code : null };
      return api<UserOut>("/auth/register", { body });
    },
    onSuccess: (u) => {
      qc.setQueryData(["me"], u);
      router.replace(homeFor(u.role));
    },
  });
  return (
    <AuthFrame title="Create your account" subtitle="Choose how you’ll use the platform">
      <form onSubmit={form.handleSubmit((v) => m.mutate(v))} className="space-y-4" noValidate>
        {m.error && <Banner tone="danger">{errMsg(m.error)}</Banner>}
        <div role="radiogroup" aria-label="Account type" className="grid grid-cols-2 gap-2">
          {(["candidate", "recruiter"] as const).map((r) => (
            <button
              key={r}
              type="button"
              role="radio"
              aria-checked={role === r}
              onClick={() => form.setValue("role", r)}
              className={cn("rounded-lg border p-3 text-left text-sm transition-colors", role === r ? "border-primary bg-primary/8" : "hover:bg-muted")}
            >
              <span className="block font-medium capitalize">{r}</span>
              <span className="text-[13px] text-muted-foreground">{r === "candidate" ? "Apply to jobs" : "Post & review"}</span>
            </button>
          ))}
        </div>
        <Field label="Full name" htmlFor="full_name" error={e.full_name?.message}>
          <Input id="full_name" autoComplete="name" {...form.register("full_name")} />
        </Field>
        <Field label="Email" htmlFor="email" error={e.email?.message}>
          <Input id="email" type="email" autoComplete="email" {...form.register("email")} />
        </Field>
        <Field label="Password" htmlFor="password" error={e.password?.message} hint="8+ characters with a letter and a digit">
          <Input id="password" type="password" autoComplete="new-password" {...form.register("password")} />
        </Field>
        {role === "recruiter" && (
          <Field label="Recruiter invite code" htmlFor="invite_code" hint="Required only if your administrator set one">
            <Input id="invite_code" {...form.register("invite_code")} />
          </Field>
        )}
        <Button type="submit" className="w-full" loading={m.isPending}>Create account</Button>
      </form>
      <p className="text-center text-sm text-muted-foreground">
        Already registered? <Link href="/login" className="font-medium text-primary hover:underline">Sign in</Link>
      </p>
    </AuthFrame>
  );
}
